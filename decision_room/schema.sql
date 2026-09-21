-- Product metadata only. Customer CSV rows live in private Parquet files.
CREATE TABLE IF NOT EXISTS schema_versions (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS businesses (
    id uuid PRIMARY KEY,
    name text NOT NULL CHECK (length(trim(name)) > 0),
    description text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS analyses (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES businesses(id),
    title text NOT NULL,
    batch_sha256 text NOT NULL,
    status text NOT NULL CHECK (status IN ('importing','ready','partial','failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id, batch_sha256),
    UNIQUE (business_id, id)
);
CREATE TABLE IF NOT EXISTS sources (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    original_names jsonb NOT NULL,
    sha256 text NOT NULL,
    byte_count bigint NOT NULL CHECK (byte_count >= 0),
    original_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('staged','ready','failed')),
    preparation jsonb NOT NULL,
    issue jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id),
    UNIQUE (analysis_id, sha256),
    UNIQUE (business_id, analysis_id, id)
);
CREATE TABLE IF NOT EXISTS prepared_tables (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    source_id uuid NOT NULL UNIQUE,
    parquet_key text NOT NULL,
    parquet_sha256 text NOT NULL,
    row_count bigint NOT NULL CHECK (row_count >= 0),
    columns jsonb NOT NULL,
    profile jsonb NOT NULL,
    lineage_column text NOT NULL,
    engine_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id, analysis_id, source_id) REFERENCES sources(business_id, analysis_id, id)
);
CREATE INDEX IF NOT EXISTS analyses_business_date ON analyses(business_id, created_at DESC);
CREATE INDEX IF NOT EXISTS sources_business_hash ON sources(business_id, sha256);
CREATE INDEX IF NOT EXISTS prepared_analysis ON prepared_tables(business_id, analysis_id);
INSERT INTO schema_versions(version) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS executions (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    code_sha256 text NOT NULL,
    code_key text NOT NULL,
    inputs jsonb NOT NULL,
    definitions jsonb NOT NULL,
    limits jsonb NOT NULL,
    environment jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('preparing','running','completed','failed','timed_out','interrupted','invalid_output','resource_limit')),
    result jsonb,
    logs jsonb NOT NULL DEFAULT '{}',
    runtime jsonb NOT NULL DEFAULT '{}',
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    duration_seconds double precision,
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id),
    UNIQUE (business_id, analysis_id, request_key),
    UNIQUE (business_id, id)
);
CREATE TABLE IF NOT EXISTS execution_artifacts (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    execution_id uuid NOT NULL,
    name text NOT NULL,
    storage_key text NOT NULL,
    sha256 text NOT NULL,
    byte_count bigint NOT NULL CHECK (byte_count >= 0),
    FOREIGN KEY (business_id, execution_id) REFERENCES executions(business_id, id),
    UNIQUE (execution_id, name)
);
CREATE INDEX IF NOT EXISTS executions_analysis_date ON executions(business_id, analysis_id, created_at DESC);
INSERT INTO schema_versions(version) VALUES (2) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS agent_sessions (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    source_snapshot jsonb NOT NULL,
    model_settings jsonb NOT NULL,
    graph_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('new','running','waiting','ready','limited','failed')),
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id),
    UNIQUE (business_id, analysis_id, request_key),
    UNIQUE (business_id, id)
);
CREATE TABLE IF NOT EXISTS agent_revisions (
    session_id uuid NOT NULL REFERENCES agent_sessions(id),
    revision integer NOT NULL CHECK (revision > 0),
    proposal jsonb NOT NULL,
    inspected_table_ids jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, revision)
);
CREATE TABLE IF NOT EXISTS agent_questions (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES agent_sessions(id),
    revision integer NOT NULL,
    key text NOT NULL,
    question jsonb NOT NULL,
    UNIQUE (session_id, key),
    FOREIGN KEY (session_id, revision) REFERENCES agent_revisions(session_id, revision)
);
CREATE TABLE IF NOT EXISTS agent_answers (
    id uuid PRIMARY KEY,
    question_id uuid NOT NULL UNIQUE REFERENCES agent_questions(id),
    disposition text NOT NULL CHECK (disposition IN ('answered','unknown','declined')),
    text text NOT NULL,
    request_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_calls (
    id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES agent_sessions(id),
    call_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('running','completed','failed','interrupted')),
    prompt_version text NOT NULL,
    output jsonb,
    usage jsonb NOT NULL DEFAULT '{}',
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS agent_calls_session ON agent_calls(session_id, call_key);
INSERT INTO schema_versions(version) VALUES (3) ON CONFLICT DO NOTHING;

ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS supersedes_session_id uuid REFERENCES agent_sessions(id);
ALTER TABLE agent_sessions ADD COLUMN IF NOT EXISTS superseded_by uuid REFERENCES agent_sessions(id);
ALTER TABLE agent_calls ADD COLUMN IF NOT EXISTS phase text NOT NULL DEFAULT 'planning';
ALTER TABLE agent_calls ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS agent_research (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    session_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    plan_revision integer NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    knowledge_sha256 text NOT NULL,
    snapshot jsonb NOT NULL,
    options jsonb NOT NULL,
    graph_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('new','running','completed','partial','failed','stale')),
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,session_id) REFERENCES agent_sessions(business_id,id),
    FOREIGN KEY (business_id,analysis_id) REFERENCES analyses(business_id,id),
    FOREIGN KEY (session_id,plan_revision) REFERENCES agent_revisions(session_id,revision),
    UNIQUE (session_id,request_key),
    UNIQUE (business_id,id)
);
CREATE TABLE IF NOT EXISTS agent_research_steps (
    research_id uuid NOT NULL REFERENCES agent_research(id),
    step integer NOT NULL CHECK (step>0),
    business_id uuid NOT NULL,
    action jsonb NOT NULL,
    execution_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (research_id,step),
    FOREIGN KEY (business_id,research_id) REFERENCES agent_research(business_id,id),
    FOREIGN KEY (business_id,execution_id) REFERENCES executions(business_id,id)
);
CREATE TABLE IF NOT EXISTS agent_research_findings (
    research_id uuid NOT NULL,
    investigation_key text NOT NULL,
    step integer NOT NULL,
    status text NOT NULL CHECK (status IN ('candidate','blocked')),
    summary text NOT NULL,
    metric_keys jsonb NOT NULL,
    PRIMARY KEY (research_id,investigation_key),
    FOREIGN KEY (research_id,step) REFERENCES agent_research_steps(research_id,step)
);
INSERT INTO schema_versions(version) VALUES (4) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS agent_reviews (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    session_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    research_id uuid NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    knowledge_sha256 text NOT NULL,
    snapshot jsonb NOT NULL,
    reviewer_settings jsonb NOT NULL,
    options jsonb NOT NULL,
    graph_version text NOT NULL,
    status text NOT NULL CHECK (status IN ('new','running','waiting','approved','rejected','withdrawn','limited','failed','stale')),
    issue text,
    approved_sha256 text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,session_id) REFERENCES agent_sessions(business_id,id),
    FOREIGN KEY (business_id,analysis_id) REFERENCES analyses(business_id,id),
    FOREIGN KEY (business_id,research_id) REFERENCES agent_research(business_id,id),
    UNIQUE (session_id,request_key),
    UNIQUE (business_id,id)
);
CREATE TABLE IF NOT EXISTS agent_review_events (
    review_id uuid NOT NULL REFERENCES agent_reviews(id),
    step integer NOT NULL CHECK (step>0),
    business_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('analyst','reviewer')),
    action jsonb NOT NULL,
    knowledge_sha256 text NOT NULL,
    execution_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (review_id,step),
    FOREIGN KEY (business_id,review_id) REFERENCES agent_reviews(business_id,id),
    FOREIGN KEY (business_id,execution_id) REFERENCES executions(business_id,id)
);
CREATE TABLE IF NOT EXISTS agent_review_answers (
    id uuid PRIMARY KEY,
    review_id uuid NOT NULL,
    step integer NOT NULL,
    disposition text NOT NULL CHECK (disposition IN ('answered','unknown','declined')),
    text text NOT NULL,
    request_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (review_id,step) REFERENCES agent_review_events(review_id,step),
    UNIQUE (review_id,step),
    UNIQUE (review_id,request_key)
);
CREATE INDEX IF NOT EXISTS agent_reviews_session ON agent_reviews(session_id);
INSERT INTO schema_versions(version) VALUES (5) ON CONFLICT DO NOTHING;

-- Independent operator validation can block an otherwise model-approved report.
-- Keep the model's historical decision intact; corrections require a new review.
CREATE TABLE IF NOT EXISTS agent_review_holds (
    review_id uuid PRIMARY KEY REFERENCES agent_reviews(id),
    reason text NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 4000),
    created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_versions(version) VALUES (6) ON CONFLICT DO NOTHING;
