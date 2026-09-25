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

-- Local web workspace; private uploads and graph checkpoints remain separate.
CREATE TABLE IF NOT EXISTS web_jobs (
    id uuid PRIMARY KEY,
    request_key uuid NOT NULL UNIQUE,
    request_sha256 text NOT NULL,
    business_id uuid NOT NULL REFERENCES businesses(id),
    analysis_id uuid,
    session_id uuid,
    research_id uuid,
    review_id uuid,
    title text NOT NULL,
    context text NOT NULL,
    goal text NOT NULL,
    filename text NOT NULL,
    upload_key text NOT NULL,
    byte_count bigint NOT NULL,
    model_settings jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','running','waiting','completed','blocked','failed')),
    phase text NOT NULL DEFAULT 'upload' CHECK (phase IN ('upload','planning','research','review','done')),
    issue text,
    pending_answer jsonb,
    retry_uncertain boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,analysis_id) REFERENCES analyses(business_id,id),
    FOREIGN KEY (business_id,session_id) REFERENCES agent_sessions(business_id,id),
    FOREIGN KEY (business_id,research_id) REFERENCES agent_research(business_id,id),
    FOREIGN KEY (business_id,review_id) REFERENCES agent_reviews(business_id,id)
);
-- A staged CSV can be retried before a batch is committed. Files keep their
-- original order so the first table remains the default preview.
CREATE TABLE IF NOT EXISTS web_job_files (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES businesses(id),
    job_id uuid REFERENCES web_jobs(id) ON DELETE CASCADE,
    position integer,
    filename text NOT NULL,
    upload_key text NOT NULL,
    byte_count bigint NOT NULL CHECK (byte_count > 0),
    sha256 text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_id, position)
);
CREATE INDEX IF NOT EXISTS web_job_files_job ON web_job_files(job_id, position);
CREATE TABLE IF NOT EXISTS web_replies (
    job_id uuid NOT NULL REFERENCES web_jobs(id),
    request_key uuid NOT NULL,
    answer jsonb NOT NULL,
    PRIMARY KEY (job_id,request_key)
);
INSERT INTO schema_versions(version) VALUES (7) ON CONFLICT DO NOTHING;

-- A local owner may explicitly select an existing web business. CLI evaluation
-- businesses are never enrolled implicitly. Backfill only once, transactionally.
CREATE TABLE IF NOT EXISTS web_businesses (
    business_id uuid PRIMARY KEY REFERENCES businesses(id),
    profile_revision integer NOT NULL DEFAULT 1 CHECK (profile_revision > 0),
    onboarding_status text NOT NULL DEFAULT 'context_saved'
        CHECK (onboarding_status IN ('context_saved','analysis_started')),
    creation_key uuid UNIQUE,
    creation_sha256 text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS web_workspace (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    active_business_id uuid REFERENCES web_businesses(business_id)
);
INSERT INTO web_workspace(singleton) VALUES (true) ON CONFLICT DO NOTHING;
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS business_name text;
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS business_revision integer;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_versions WHERE version=8) THEN
        INSERT INTO web_businesses(business_id,onboarding_status)
            SELECT DISTINCT business_id,'analysis_started' FROM web_jobs
            ON CONFLICT DO NOTHING;
        UPDATE web_jobs w SET business_name=b.name FROM businesses b
            WHERE b.id=w.business_id AND w.business_name IS NULL;
        -- A single historical web business is unambiguous. With several, leave
        -- selection empty: names are not identities, including identical names.
        UPDATE web_workspace SET active_business_id=(SELECT business_id FROM web_businesses LIMIT 1)
            WHERE active_business_id IS NULL AND (SELECT count(*) FROM web_businesses)=1;
        INSERT INTO schema_versions(version) VALUES (8);
    END IF;
END $$;
ALTER TABLE web_jobs ALTER COLUMN business_name SET NOT NULL;
CREATE INDEX IF NOT EXISTS web_jobs_business_date ON web_jobs(business_id,created_at DESC);

-- Durable original text and append-only memory revisions. No checkpoint dependency.
CREATE TABLE IF NOT EXISTS memory_heads (
    business_id uuid PRIMARY KEY REFERENCES businesses(id),
    revision integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS memory_sources (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES businesses(id),
    origin_key text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','extracting','extracted','applied','failed','uncertain','superseded')),
    response jsonb,
    context_revision integer,
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id,origin_key),
    UNIQUE (business_id,id)
);
CREATE TABLE IF NOT EXISTS memory_facts (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES businesses(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id,id)
);
CREATE TABLE IF NOT EXISTS memory_revisions (
    business_id uuid NOT NULL,
    fact_id uuid NOT NULL,
    revision integer NOT NULL,
    business_revision integer NOT NULL,
    content jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('proposed','declared','conflicted','withdrawn','superseded')),
    source_id uuid NOT NULL,
    quote text NOT NULL,
    alternatives jsonb NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (fact_id,revision),
    FOREIGN KEY (business_id,fact_id) REFERENCES memory_facts(business_id,id),
    FOREIGN KEY (business_id,source_id) REFERENCES memory_sources(business_id,id)
);
CREATE TABLE IF NOT EXISTS memory_commands (
    business_id uuid NOT NULL REFERENCES businesses(id),
    request_key text NOT NULL,
    signature text NOT NULL,
    result jsonb NOT NULL,
    PRIMARY KEY (business_id,request_key)
);
CREATE TABLE IF NOT EXISTS memory_calls (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    source_id uuid NOT NULL,
    model_settings jsonb NOT NULL,
    prompt_version text NOT NULL,
    context jsonb NOT NULL,
    response jsonb,
    usage jsonb,
    status text NOT NULL CHECK (status IN ('running','completed','failed','uncertain')),
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    FOREIGN KEY (business_id,source_id) REFERENCES memory_sources(business_id,id)
);
CREATE INDEX IF NOT EXISTS memory_sources_pending ON memory_sources(status,created_at);
CREATE INDEX IF NOT EXISTS memory_revisions_business ON memory_revisions(business_id,fact_id,revision DESC);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_versions WHERE version=9) THEN
        INSERT INTO memory_sources(id,business_id,origin_key,payload)
            SELECT b.id,b.id,'profile:' || w.profile_revision,
                jsonb_build_object('kind','profile','text',b.description,'question','',
                    'disposition','answered','default_scope','business','scope_id',NULL,
                    'allow_business',true,'profile_revision',w.profile_revision)
            FROM web_businesses w JOIN businesses b ON b.id=w.business_id;
        INSERT INTO schema_versions(version) VALUES (9);
    END IF;
END $$;

-- Shared, immutable starting context plus append-only retrieval observations.
ALTER TABLE memory_revisions ADD COLUMN IF NOT EXISTS change_kind text NOT NULL DEFAULT 'historical'
    CHECK (change_kind IN ('historical','future'));
CREATE TABLE IF NOT EXISTS context_manifests (
    session_id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    selection jsonb NOT NULL,
    initial_context jsonb NOT NULL,
    stale_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,session_id) REFERENCES agent_sessions(business_id,id)
);
CREATE TABLE IF NOT EXISTS context_retrievals (
    session_id uuid NOT NULL REFERENCES context_manifests(session_id),
    decision_key text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    request jsonb NOT NULL,
    response jsonb NOT NULL,
    dependencies jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id,decision_key,ordinal)
);
CREATE INDEX IF NOT EXISTS context_manifests_business ON context_manifests(business_id);
ALTER TABLE agent_calls ADD COLUMN IF NOT EXISTS context_payload jsonb;
INSERT INTO schema_versions(version) VALUES (10) ON CONFLICT DO NOTHING;

-- Derived semantic cache. Originals and their current applicability remain authoritative.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS semantic_chunks (
    business_id uuid NOT NULL REFERENCES businesses(id),
    kind text NOT NULL CHECK (kind IN ('dataset','memory','report')),
    object_key text NOT NULL,
    content_hash text NOT NULL,
    model text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions BETWEEN 256 AND 3072),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    fragment text NOT NULL,
    embedding vector NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (vector_dims(embedding)=dimensions),
    PRIMARY KEY (business_id,kind,object_key,content_hash,model,dimensions,ordinal)
);
CREATE TABLE IF NOT EXISTS semantic_calls (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES businesses(id),
    model text NOT NULL,
    dimensions integer NOT NULL,
    purpose text NOT NULL CHECK (purpose IN ('documents','query')),
    input_hash text NOT NULL,
    input_count integer NOT NULL,
    status text NOT NULL CHECK (status IN ('running','completed','failed')),
    usage jsonb,
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
INSERT INTO schema_versions(version) VALUES (11) ON CONFLICT DO NOTHING;

-- Durable business conversations. A turn stores the owner message and its validated reply.
CREATE UNIQUE INDEX IF NOT EXISTS web_jobs_business_identity ON web_jobs(business_id,id);
CREATE TABLE IF NOT EXISTS chat_conversations (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES businesses(id),
    request_key uuid NOT NULL,
    title text NOT NULL,
    analysis_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(business_id,id), UNIQUE(business_id,request_key),
    FOREIGN KEY(business_id,analysis_id) REFERENCES analyses(business_id,id)
);
CREATE TABLE IF NOT EXISTS chat_turns (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    ordinal integer NOT NULL,
    request_key uuid NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL CHECK(status IN ('queued','routing','processing','waiting','completed','failed','blocked')),
    model_settings jsonb NOT NULL,
    memory_source_id uuid,
    job_id uuid,
    snapshot jsonb,
    response jsonb,
    issue text,
    attempt integer NOT NULL DEFAULT 0,
    report_requested boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(conversation_id,ordinal), UNIQUE(conversation_id,request_key),
    FOREIGN KEY(business_id,job_id) REFERENCES web_jobs(business_id,id),
    FOREIGN KEY(business_id,conversation_id) REFERENCES chat_conversations(business_id,id),
    FOREIGN KEY(business_id,memory_source_id) REFERENCES memory_sources(business_id,id)
);
CREATE TABLE IF NOT EXISTS chat_calls (
    turn_id uuid NOT NULL REFERENCES chat_turns(id),
    attempt integer NOT NULL,
    ordinal integer NOT NULL,
    prompt_version text NOT NULL,
    context jsonb NOT NULL,
    response jsonb,
    usage jsonb,
    status text NOT NULL CHECK(status IN ('running','completed','failed','uncertain')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(turn_id,attempt,ordinal)
);
CREATE TABLE IF NOT EXISTS chat_retrievals (
    turn_id uuid NOT NULL REFERENCES chat_turns(id),
    attempt integer NOT NULL,
    ordinal integer NOT NULL,
    request jsonb NOT NULL,
    response jsonb NOT NULL,
    dependencies jsonb NOT NULL,
    PRIMARY KEY(turn_id,attempt,ordinal)
);
ALTER TABLE chat_turns ADD COLUMN IF NOT EXISTS response_history jsonb NOT NULL DEFAULT '[]';
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS origin text NOT NULL DEFAULT 'upload';
ALTER TABLE semantic_chunks DROP CONSTRAINT IF EXISTS semantic_chunks_kind_check;
ALTER TABLE semantic_chunks ADD CONSTRAINT semantic_chunks_kind_check CHECK(kind IN ('dataset','memory','report','chat'));
CREATE INDEX IF NOT EXISTS chat_turns_pending ON chat_turns(status,created_at);
INSERT INTO schema_versions(version) VALUES (12) ON CONFLICT DO NOTHING;

-- Immutable imported batches, grouped into explicit owner-selected versions.
-- Batches imported before this feature remain implicit standalone version 1.
CREATE TABLE IF NOT EXISTS dataset_versions (
    business_id uuid NOT NULL,
    analysis_id uuid PRIMARY KEY,
    dataset_id uuid NOT NULL,
    version integer NOT NULL CHECK(version > 0),
    period_from date,
    period_until date,
    superseded_by uuid,
    corrected boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(business_id,dataset_id,version),
    FOREIGN KEY(business_id,analysis_id) REFERENCES analyses(business_id,id),
    FOREIGN KEY(business_id,dataset_id) REFERENCES analyses(business_id,id),
    FOREIGN KEY(business_id,superseded_by) REFERENCES analyses(business_id,id),
    CHECK(period_from IS NULL OR period_until IS NULL OR period_from <= period_until)
);
CREATE TABLE IF NOT EXISTS dataset_uploads (
    business_id uuid NOT NULL REFERENCES businesses(id),
    request_key uuid NOT NULL,
    signature text NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(business_id,request_key)
);
INSERT INTO schema_versions(version) VALUES (13) ON CONFLICT DO NOTHING;

-- Only businesses explicitly created through the guided first-report flow are
-- enrolled. Existing local workspaces retain their established navigation.
CREATE TABLE IF NOT EXISTS web_onboarding (
    business_id uuid PRIMARY KEY REFERENCES web_businesses(business_id),
    job_id uuid,
    completed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    FOREIGN KEY (business_id, job_id) REFERENCES web_jobs(business_id, id),
    CHECK (NOT completed OR job_id IS NOT NULL)
);
INSERT INTO schema_versions(version) VALUES (14) ON CONFLICT DO NOTHING;
