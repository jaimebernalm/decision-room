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
ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
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

-- Conversational prose is independently checked, with durable provider outcomes.
CREATE TABLE IF NOT EXISTS chat_answer_reviews (
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
INSERT INTO schema_versions(version) VALUES (14) ON CONFLICT DO NOTHING;

-- Reversible chat deletion; shared memory and reviewed reports remain independent.
INSERT INTO schema_versions(version) VALUES (15) ON CONFLICT DO NOTHING;

-- Stable owner selections and pending AI editorial proposals, isolated by business.
CREATE TABLE IF NOT EXISTS web_home_layouts (
    business_id uuid PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
    revision integer NOT NULL DEFAULT 0,
    layout jsonb NOT NULL DEFAULT '{}',
    proposal jsonb
);
INSERT INTO schema_versions(version) VALUES (16) ON CONFLICT DO NOTHING;

-- A folder upload retains the files selected by the owner. Excel worksheets are
-- prepared as traceable CSV tables; the submitted workbook remains downloadable.
CREATE TABLE IF NOT EXISTS dataset_bundle_files (
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    relative_path text NOT NULL,
    sha256 text NOT NULL,
    byte_count bigint NOT NULL CHECK (byte_count > 0),
    original_key text NOT NULL,
    PRIMARY KEY (business_id, analysis_id, relative_path),
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id)
);
INSERT INTO schema_versions(version) VALUES (17) ON CONFLICT DO NOTHING;

-- Recoverable removal from the report library, preserving evidence and chat links.
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
INSERT INTO schema_versions(version) VALUES (18) ON CONFLICT DO NOTHING;

-- Immutable data model revisions: the ER view and agents read the same document.
CREATE TABLE IF NOT EXISTS data_model_revisions (
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    fingerprint text NOT NULL,
    body jsonb NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id,analysis_id,revision),
    FOREIGN KEY (business_id,analysis_id) REFERENCES analyses(business_id,id)
);
INSERT INTO schema_versions(version) VALUES (19) ON CONFLICT DO NOTHING;

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
INSERT INTO schema_versions(version) VALUES (20) ON CONFLICT DO NOTHING;

-- Guided setup shares the durable chat; legacy onboarding jobs remain untouched.
CREATE TABLE IF NOT EXISTS onboarding_sessions (
    business_id uuid PRIMARY KEY REFERENCES web_businesses(business_id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    stage text NOT NULL DEFAULT 'goal' CHECK(stage IN ('goal','data','scope','report','complete')),
    analysis_id uuid,
    goal jsonb NOT NULL DEFAULT '{}',
    brief jsonb,
    proposal_turn_id uuid REFERENCES chat_turns(id),
    confirmed jsonb,
    job_id uuid,
    FOREIGN KEY(business_id,conversation_id) REFERENCES chat_conversations(business_id,id),
    FOREIGN KEY(business_id,analysis_id) REFERENCES analyses(business_id,id),
    FOREIGN KEY(business_id,job_id) REFERENCES web_jobs(business_id,id)
);
CREATE TABLE IF NOT EXISTS onboarding_events (
    business_id uuid NOT NULL REFERENCES onboarding_sessions(business_id) ON DELETE CASCADE,
    request_key uuid NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(business_id,request_key)
);
INSERT INTO schema_versions(version) VALUES (21) ON CONFLICT DO NOTHING;

-- Durable bounded discovery before chat/planning snapshots.
CREATE TABLE IF NOT EXISTS data_model_discoveries (
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    call_key text NOT NULL,
    attempt integer NOT NULL,
    status text NOT NULL CHECK(status IN ('running','completed','failed','interrupted')),
    context_payload jsonb NOT NULL,
    model_settings jsonb NOT NULL,
    output jsonb,
    usage jsonb,
    issue text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(business_id,analysis_id,call_key,attempt),
    FOREIGN KEY(business_id,analysis_id) REFERENCES analyses(business_id,id)
);
INSERT INTO schema_versions(version) VALUES (22) ON CONFLICT DO NOTHING;

-- Durable parent/worker links. Child runs reuse isolated research checkpoints.
CREATE TABLE IF NOT EXISTS agent_research_branches (
    business_id uuid NOT NULL,
    parent_id uuid NOT NULL,
    dispatch_step integer NOT NULL,
    ordinal integer NOT NULL,
    child_id uuid NOT NULL UNIQUE,
    assignment jsonb NOT NULL,
    PRIMARY KEY(parent_id,dispatch_step,ordinal),
    FOREIGN KEY(business_id,parent_id) REFERENCES agent_research(business_id,id),
    FOREIGN KEY(business_id,child_id) REFERENCES agent_research(business_id,id),
    CHECK(parent_id <> child_id)
);
ALTER TABLE agent_research_branches ADD COLUMN IF NOT EXISTS started_at timestamptz;
ALTER TABLE agent_research_branches ADD COLUMN IF NOT EXISTS finished_at timestamptz;
INSERT INTO schema_versions(version) VALUES (23) ON CONFLICT DO NOTHING;

-- 3.7: durable business direction and owner clarification during research.
ALTER TABLE agent_research DROP CONSTRAINT IF EXISTS agent_research_status_check;
ALTER TABLE agent_research ADD CONSTRAINT agent_research_status_check
    CHECK (status IN ('new','running','completed','partial','waiting','replan_required','failed','stale'));
ALTER TABLE agent_research ADD COLUMN IF NOT EXISTS paused_seconds double precision NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS business_planner_events (
    id uuid PRIMARY KEY,
    research_id uuid NOT NULL,
    business_id uuid NOT NULL,
    ordinal integer NOT NULL,
    checkpoint_key text NOT NULL,
    stage text NOT NULL CHECK (stage IN ('initial','checkpoint','delivery')),
    direction jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,research_id) REFERENCES agent_research(business_id,id),
    UNIQUE (research_id,checkpoint_key), UNIQUE (research_id,ordinal),
    UNIQUE (business_id,research_id,id)
);
CREATE TABLE IF NOT EXISTS business_planner_answers (
    id uuid PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE,
    research_id uuid NOT NULL,
    business_id uuid NOT NULL,
    disposition text NOT NULL CHECK (disposition IN ('answered','unknown','declined')),
    text text NOT NULL,
    request_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,research_id,event_id) REFERENCES business_planner_events(business_id,research_id,id),
    UNIQUE (research_id,request_key)
);
INSERT INTO schema_versions(version) VALUES (24) ON CONFLICT DO NOTHING;

-- 3.8: durable process activity, independent of analytical checkpoints.
CREATE TABLE IF NOT EXISTS activity_traces (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL REFERENCES businesses(id),
    origin_kind text NOT NULL,
    origin_id uuid NOT NULL,
    last_sequence bigint NOT NULL DEFAULT 0,
    history_complete boolean NOT NULL DEFAULT true,
    heartbeat_at timestamptz,
    worker_active boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(business_id,id), UNIQUE(business_id,origin_kind,origin_id)
);
CREATE TABLE IF NOT EXISTS activity_links (
    business_id uuid NOT NULL,
    trace_id uuid NOT NULL,
    kind text NOT NULL,
    source_id uuid NOT NULL,
    PRIMARY KEY(business_id,kind,source_id),
    FOREIGN KEY(business_id,trace_id) REFERENCES activity_traces(business_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS activity_links_trace ON activity_links(business_id,trace_id,kind);
CREATE TABLE IF NOT EXISTS activity_tasks (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    trace_id uuid NOT NULL,
    parent_task_id uuid,
    actor_id text NOT NULL,
    role text NOT NULL,
    kind text NOT NULL,
    source_id text NOT NULL,
    status text NOT NULL,
    public_text text NOT NULL,
    purpose text NOT NULL DEFAULT '',
    refs jsonb NOT NULL DEFAULT '[]',
    source jsonb NOT NULL DEFAULT '{}',
    started_at timestamptz,
    finished_at timestamptz,
    last_sequence bigint NOT NULL,
    UNIQUE(business_id,trace_id,id), UNIQUE(trace_id,kind,source_id),
    FOREIGN KEY(business_id,trace_id) REFERENCES activity_traces(business_id,id) ON DELETE CASCADE,
    FOREIGN KEY(business_id,trace_id,parent_task_id) REFERENCES activity_tasks(business_id,trace_id,id),
    CHECK(parent_task_id IS NULL OR parent_task_id<>id),
    CHECK(status IN ('queued','running','waiting_owner','waiting_dependency','retry_wait','completed','failed','interrupted','superseded'))
);
CREATE TABLE IF NOT EXISTS activity_events (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    trace_id uuid NOT NULL,
    sequence bigint NOT NULL,
    task_id uuid NOT NULL,
    dedupe_key text NOT NULL,
    type text NOT NULL,
    status text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    occurred_at timestamptz,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    reconstructed boolean NOT NULL DEFAULT false,
    UNIQUE(trace_id,sequence), UNIQUE(trace_id,dedupe_key),
    FOREIGN KEY(business_id,trace_id,task_id) REFERENCES activity_tasks(business_id,trace_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS activity_events_page ON activity_events(business_id,trace_id,sequence);
CREATE INDEX IF NOT EXISTS activity_traces_recent ON activity_traces(business_id,created_at DESC,id);
INSERT INTO schema_versions(version) VALUES (25) ON CONFLICT DO NOTHING;

-- 3.8 follow-up: unknown legacy finishes stay NULL, never invented as starts.
ALTER TABLE chat_calls ADD COLUMN IF NOT EXISTS finished_at timestamptz;
ALTER TABLE chat_answer_reviews ADD COLUMN IF NOT EXISTS finished_at timestamptz;
INSERT INTO schema_versions(version) VALUES (26) ON CONFLICT DO NOTHING;

-- 2.5.18: immutable presentation revisions, separate from analytical approval.
CREATE TABLE IF NOT EXISTS report_presentation_revisions (
    business_id uuid NOT NULL REFERENCES businesses(id),
    report_id uuid NOT NULL REFERENCES agent_reviews(id),
    base_version text NOT NULL,
    revision integer NOT NULL CHECK(revision>=0),
    config jsonb NOT NULL,
    snapshot jsonb NOT NULL,
    request_key text,
    request_sha256 text,
    origin text NOT NULL CHECK(origin IN ('catalog','editor','chat')),
    description text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(business_id,report_id,base_version,revision),
    UNIQUE(business_id,request_key)
);
INSERT INTO schema_versions(version) VALUES (27) ON CONFLICT DO NOTHING;

-- Owner presentation groups do not alter memory contents or analytical revisions.
CREATE TABLE IF NOT EXISTS web_dossier_layouts (
    business_id uuid PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
    revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    layout jsonb NOT NULL DEFAULT '{}'
);
INSERT INTO schema_versions(version) VALUES (28) ON CONFLICT DO NOTHING;

-- 2.5.21: owner-pinned chats stay ahead of recent conversations.
ALTER TABLE chat_conversations ADD COLUMN IF NOT EXISTS pinned_at timestamptz;
INSERT INTO schema_versions(version) VALUES (29) ON CONFLICT DO NOTHING;

-- Historical inputs remain available to reports while leaving the everyday library.
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS library_hidden boolean NOT NULL DEFAULT false;
INSERT INTO schema_versions(version) VALUES (30) ON CONFLICT DO NOTHING;

-- F0: HTML engine control and receipts; preserve master version 30.
-- Engine P2 admission foundation; legacy sessions and report FKs are unchanged.
CREATE TABLE IF NOT EXISTS engine_runs (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    owner_context text NOT NULL,
    profile jsonb NOT NULL,
    prompt text NOT NULL CHECK(octet_length(prompt)<=262144),
    prompt_sha256 text NOT NULL,
    input_context jsonb NOT NULL,
    input_sha256 text NOT NULL,
    model text NOT NULL,
    snapshot jsonb NOT NULL,
    snapshot_sha256 text NOT NULL,
    limits jsonb NOT NULL,
    status text NOT NULL DEFAULT 'running'
        CHECK(status IN ('running','pausing','waiting','delivered','failed','aborted')),
    abort_reason text,
    credential_sha256 text NOT NULL,
    credential_revoked boolean NOT NULL DEFAULT false,
    credential_expires_at timestamptz NOT NULL DEFAULT clock_timestamp()+interval '7 days',
    active_started_at timestamptz DEFAULT clock_timestamp(),
    active_seconds double precision NOT NULL DEFAULT 0 CHECK(active_seconds>=0),
    calls integer NOT NULL DEFAULT 0 CHECK(calls>=0),
    charged_input bigint NOT NULL DEFAULT 0 CHECK(charged_input>=0),
    charged_output bigint NOT NULL DEFAULT 0 CHECK(charged_output>=0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(business_id,analysis_id) REFERENCES analyses(business_id,id),
    UNIQUE(business_id,request_key),
    UNIQUE(business_id,id)
);
CREATE TABLE IF NOT EXISTS engine_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES engine_runs(id),
    kind text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS engine_events_run ON engine_events(run_id,id);
CREATE TABLE IF NOT EXISTS engine_model_calls (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES engine_runs(id),
    request_sha256 text NOT NULL,
    state text NOT NULL CHECK(state IN ('counting','admitted','settled','uncertain')),
    reserved_input bigint NOT NULL DEFAULT 0 CHECK(reserved_input>=0),
    reserved_output bigint NOT NULL DEFAULT 0 CHECK(reserved_output>=0),
    usage jsonb,
    issue text,
    settlement_sha256 text,
    count_seconds double precision,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    admitted_at timestamptz,
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS engine_model_calls_run ON engine_model_calls(run_id,started_at,id);

-- Engine drafts are independent of legacy approvals and retain exact raw bytes.
CREATE TABLE IF NOT EXISTS engine_documents (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    run_id uuid NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(business_id,run_id) REFERENCES engine_runs(business_id,id),
    UNIQUE(business_id,id)
);
CREATE TABLE IF NOT EXISTS engine_document_revisions (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    document_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK(ordinal>0),
    request_key text NOT NULL,
    raw bytea NOT NULL CHECK(octet_length(raw)<=262144),
    raw_sha256 text NOT NULL,
    delivery_via text NOT NULL CHECK(delivery_via IN ('mcp','file')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(business_id,document_id) REFERENCES engine_documents(business_id,id),
    UNIQUE(document_id,request_key),
    UNIQUE(document_id,ordinal),
    UNIQUE(business_id,id)
);

-- Engine control-plane state. Outbox admission precedes every prompt submission.
CREATE TABLE IF NOT EXISTS engine_sessions (
    run_id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    session_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(business_id,run_id) REFERENCES engine_runs(business_id,id),
    UNIQUE(run_id,session_id)
);
CREATE TABLE IF NOT EXISTS engine_prompt_outbox (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    run_id uuid NOT NULL,
    session_id text NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    message_id text NOT NULL,
    prompt text NOT NULL CHECK(octet_length(prompt)<=262144),
    state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','dispatching','confirmed')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    dispatched_at timestamptz,
    confirmed_at timestamptz,
    FOREIGN KEY(business_id,run_id) REFERENCES engine_runs(business_id,id),
    FOREIGN KEY(run_id,session_id) REFERENCES engine_sessions(run_id,session_id),
    UNIQUE(run_id,request_key),
    UNIQUE(run_id,message_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS engine_prompt_outbox_pending
    ON engine_prompt_outbox(run_id) WHERE state<>'confirmed';
CREATE TABLE IF NOT EXISTS engine_message_versions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    business_id uuid NOT NULL,
    run_id uuid NOT NULL,
    session_id text NOT NULL,
    message_id text NOT NULL,
    content jsonb NOT NULL,
    content_sha256 text NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(business_id,run_id) REFERENCES engine_runs(business_id,id),
    FOREIGN KEY(run_id,session_id) REFERENCES engine_sessions(run_id,session_id),
    UNIQUE(run_id,message_id,content_sha256)
);

-- Durable owner questions; pausing and receipt of an answer do not run a model.
CREATE TABLE IF NOT EXISTS engine_owner_questions (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    run_id uuid NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    body jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pausing' CHECK(state IN ('pausing','waiting','resumed')),
    checkpoint_key text,
    checkpoint_sha256 text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    waiting_at timestamptz,
    expires_at timestamptz,
    resumed_at timestamptz,
    FOREIGN KEY(business_id,run_id) REFERENCES engine_runs(business_id,id),
    UNIQUE(run_id,request_key),
    UNIQUE(run_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS engine_owner_question_pending
    ON engine_owner_questions(run_id) WHERE state<>'resumed';
CREATE TABLE IF NOT EXISTS engine_owner_answers (
    question_id uuid PRIMARY KEY,
    run_id uuid NOT NULL,
    request_key text NOT NULL,
    request_sha256 text NOT NULL,
    body jsonb NOT NULL,
    message_id text,
    resumed_credential_sha256 text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(run_id,question_id) REFERENCES engine_owner_questions(run_id,id),
    FOREIGN KEY(run_id,message_id) REFERENCES engine_prompt_outbox(run_id,message_id),
    UNIQUE(run_id,request_key)
);


INSERT INTO schema_versions(version) VALUES (31) ON CONFLICT DO NOTHING;

-- F0 immutable engine selection: existing jobs stay legacy and are never replayed.
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS engine_kind text NOT NULL DEFAULT 'legacy'
    CHECK(engine_kind IN ('legacy','opencode'));
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS engine_config jsonb NOT NULL DEFAULT '{}';
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS engine_run_id uuid;
ALTER TABLE web_jobs ADD COLUMN IF NOT EXISTS report_document_id uuid;
ALTER TABLE web_jobs DROP CONSTRAINT IF EXISTS web_jobs_phase_check;
ALTER TABLE web_jobs ADD CONSTRAINT web_jobs_phase_check
    CHECK(phase IN ('upload','planning','research','review','done','engine'));
ALTER TABLE web_jobs DROP CONSTRAINT IF EXISTS web_jobs_engine_run_fk;
ALTER TABLE web_jobs ADD CONSTRAINT web_jobs_engine_run_fk
    FOREIGN KEY(business_id,engine_run_id) REFERENCES engine_runs(business_id,id);
ALTER TABLE web_jobs DROP CONSTRAINT IF EXISTS web_jobs_engine_legacy_ids_check;
ALTER TABLE web_jobs ADD CONSTRAINT web_jobs_engine_legacy_ids_check
    CHECK(engine_kind='legacy' OR (session_id IS NULL AND research_id IS NULL AND review_id IS NULL));
CREATE UNIQUE INDEX IF NOT EXISTS web_jobs_engine_run_unique ON web_jobs(engine_run_id);
CREATE OR REPLACE FUNCTION keep_web_job_engine() RETURNS trigger AS $$
BEGIN
    IF NEW.engine_kind IS DISTINCT FROM OLD.engine_kind OR NEW.engine_config IS DISTINCT FROM OLD.engine_config THEN
        RAISE EXCEPTION 'Job engine configuration is immutable';
    END IF;
    IF OLD.engine_run_id IS NOT NULL AND NEW.engine_run_id IS DISTINCT FROM OLD.engine_run_id THEN
        RAISE EXCEPTION 'Job engine run identity is immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS web_job_engine_immutable ON web_jobs;
CREATE TRIGGER web_job_engine_immutable BEFORE UPDATE ON web_jobs
    FOR EACH ROW EXECUTE FUNCTION keep_web_job_engine();
INSERT INTO schema_versions(version) VALUES (32) ON CONFLICT DO NOTHING;

-- F1 gradual registry: HTML only. Legacy IDs, tables and presentation FKs stay intact.
CREATE TABLE IF NOT EXISTS engine_report_contexts (
    run_id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    selection jsonb NOT NULL,
    memories jsonb NOT NULL,
    data_models jsonb NOT NULL,
    table_versions jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(business_id,run_id) REFERENCES engine_runs(business_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS engine_documents_source ON engine_documents(business_id,id,run_id);
CREATE UNIQUE INDEX IF NOT EXISTS engine_revisions_source ON engine_document_revisions(business_id,document_id,id);
CREATE TABLE IF NOT EXISTS report_documents (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    origin text NOT NULL CHECK(origin='engine_html'),
    source_run_id uuid NOT NULL UNIQUE,
    current_revision_id uuid,
    stale_reason text,
    deleted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(business_id,analysis_id) REFERENCES analyses(business_id,id),
    FOREIGN KEY(business_id,id,source_run_id) REFERENCES engine_documents(business_id,id,run_id),
    UNIQUE(business_id,id),
    UNIQUE(business_id,source_run_id,id)
);
CREATE TABLE IF NOT EXISTS report_document_revisions (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    document_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK(ordinal>0),
    raw_sha256 text NOT NULL CHECK(raw_sha256 ~ '^[0-9a-f]{64}$'),
    raw_bytes integer NOT NULL CHECK(raw_bytes BETWEEN 0 AND 262144),
    profile_version text NOT NULL,
    presentation_state text NOT NULL CHECK(presentation_state='not_evaluated'),
    verification_state text NOT NULL CHECK(verification_state='not_requested'),
    derived_version integer NOT NULL CHECK(derived_version=0),
    canonical_text text CHECK(canonical_text IS NULL),
    canonical_sha256 text CHECK(canonical_sha256 IS NULL),
    created_at timestamptz NOT NULL,
    FOREIGN KEY(business_id,document_id) REFERENCES report_documents(business_id,id),
    FOREIGN KEY(business_id,document_id,id) REFERENCES engine_document_revisions(business_id,document_id,id),
    UNIQUE(document_id,ordinal),
    UNIQUE(business_id,document_id,id)
);
ALTER TABLE report_documents DROP CONSTRAINT IF EXISTS report_document_head;
ALTER TABLE report_documents ADD CONSTRAINT report_document_head
    FOREIGN KEY(business_id,id,current_revision_id) REFERENCES report_document_revisions(business_id,document_id,id);
ALTER TABLE web_jobs DROP CONSTRAINT IF EXISTS web_jobs_report_document_fk;
ALTER TABLE web_jobs ADD CONSTRAINT web_jobs_report_document_fk
    FOREIGN KEY(business_id,engine_run_id,report_document_id) REFERENCES report_documents(business_id,source_run_id,id);
ALTER TABLE web_jobs DROP CONSTRAINT IF EXISTS web_jobs_report_document_kind;
ALTER TABLE web_jobs ADD CONSTRAINT web_jobs_report_document_kind
    CHECK(report_document_id IS NULL OR (engine_kind='opencode' AND engine_run_id IS NOT NULL));
CREATE UNIQUE INDEX IF NOT EXISTS web_jobs_report_document_unique ON web_jobs(report_document_id);
CREATE OR REPLACE FUNCTION keep_report_revision() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Report source and revision are immutable';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS engine_report_context_immutable ON engine_report_contexts;
CREATE TRIGGER engine_report_context_immutable BEFORE UPDATE OR DELETE ON engine_report_contexts
    FOR EACH ROW EXECUTE FUNCTION keep_report_revision();
DROP TRIGGER IF EXISTS engine_report_raw_immutable ON engine_document_revisions;
CREATE TRIGGER engine_report_raw_immutable BEFORE UPDATE OR DELETE ON engine_document_revisions
    FOR EACH ROW EXECUTE FUNCTION keep_report_revision();
DROP TRIGGER IF EXISTS report_revision_immutable ON report_document_revisions;
CREATE TRIGGER report_revision_immutable BEFORE UPDATE OR DELETE ON report_document_revisions
    FOR EACH ROW EXECUTE FUNCTION keep_report_revision();
CREATE OR REPLACE FUNCTION keep_report_document_source() RETURNS trigger AS $$
BEGIN
    IF (NEW.id,NEW.business_id,NEW.analysis_id,NEW.origin,NEW.source_run_id,NEW.created_at)
        IS DISTINCT FROM (OLD.id,OLD.business_id,OLD.analysis_id,OLD.origin,OLD.source_run_id,OLD.created_at) THEN
        RAISE EXCEPTION 'Report source is immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS report_document_source_immutable ON report_documents;
CREATE TRIGGER report_document_source_immutable BEFORE UPDATE ON report_documents
    FOR EACH ROW EXECUTE FUNCTION keep_report_document_source();
CREATE OR REPLACE FUNCTION keep_web_job_engine() RETURNS trigger AS $$
BEGIN
    IF NEW.engine_kind IS DISTINCT FROM OLD.engine_kind OR NEW.engine_config IS DISTINCT FROM OLD.engine_config THEN
        RAISE EXCEPTION 'Job engine configuration is immutable';
    END IF;
    IF OLD.engine_run_id IS NOT NULL AND NEW.engine_run_id IS DISTINCT FROM OLD.engine_run_id THEN
        RAISE EXCEPTION 'Job engine run identity is immutable';
    END IF;
    IF OLD.report_document_id IS NOT NULL AND NEW.report_document_id IS DISTINCT FROM OLD.report_document_id THEN
        RAISE EXCEPTION 'Job report identity is immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
INSERT INTO schema_versions(version) VALUES (33) ON CONFLICT DO NOTHING;

-- Migration 34: bind registry and job analysis to the exact source run.
CREATE UNIQUE INDEX IF NOT EXISTS engine_runs_analysis_source ON engine_runs(business_id,id,analysis_id);
CREATE UNIQUE INDEX IF NOT EXISTS report_documents_analysis_source ON report_documents(business_id,source_run_id,id,analysis_id);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='report_documents_run_analysis') THEN
        ALTER TABLE report_documents ADD CONSTRAINT report_documents_run_analysis
            FOREIGN KEY(business_id,source_run_id,analysis_id) REFERENCES engine_runs(business_id,id,analysis_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='web_jobs_report_analysis') THEN
        ALTER TABLE web_jobs ADD CONSTRAINT web_jobs_report_analysis
            FOREIGN KEY(business_id,engine_run_id,report_document_id,analysis_id)
            REFERENCES report_documents(business_id,source_run_id,id,analysis_id);
        ALTER TABLE web_jobs ADD CONSTRAINT web_jobs_report_analysis_required
            CHECK(report_document_id IS NULL OR analysis_id IS NOT NULL);
    END IF;
END $$;
INSERT INTO schema_versions(version) VALUES (34) ON CONFLICT DO NOTHING;

-- Migration 35: provenance of the generated v1 brief and panorama (F2). Existing runs keep '{}'.
ALTER TABLE engine_runs ADD COLUMN IF NOT EXISTS brief jsonb NOT NULL DEFAULT '{}';
-- Static request identity: a replayed key is checked against it without rebuilding dynamic inputs.
ALTER TABLE engine_runs ADD COLUMN IF NOT EXISTS request_static_sha256 text;
INSERT INTO schema_versions(version) VALUES (35) ON CONFLICT DO NOTHING;

-- Migration 36: versioned, immutable derivatives; original receipts remain immutable.
ALTER TABLE report_document_revisions DROP CONSTRAINT IF EXISTS report_document_revisions_presentation_state_check;
ALTER TABLE report_document_revisions DROP CONSTRAINT IF EXISTS report_document_revisions_derived_version_check;
ALTER TABLE report_document_revisions DROP CONSTRAINT IF EXISTS report_document_revisions_canonical_text_check;
ALTER TABLE report_document_revisions DROP CONSTRAINT IF EXISTS report_document_revisions_canonical_sha256_check;
ALTER TABLE report_document_revisions ADD COLUMN IF NOT EXISTS presentation_reason text;
ALTER TABLE report_document_revisions ADD COLUMN IF NOT EXISTS derive_status text NOT NULL DEFAULT 'pending';
ALTER TABLE report_document_revisions ADD COLUMN IF NOT EXISTS derive_issue text;
ALTER TABLE report_document_revisions ADD COLUMN IF NOT EXISTS policy_version text;
ALTER TABLE report_document_revisions ADD COLUMN IF NOT EXISTS renderer_version text;
ALTER TABLE report_document_revisions ADD COLUMN IF NOT EXISTS inventory_sha256 text;
ALTER TABLE report_document_revisions ADD COLUMN IF NOT EXISTS snapshot_html text;
CREATE UNIQUE INDEX IF NOT EXISTS report_revision_raw_identity ON report_document_revisions(business_id,document_id,id,raw_sha256);
CREATE TABLE IF NOT EXISTS report_presentation_checks (
    business_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    raw_sha256 text NOT NULL,
    policy_version text NOT NULL,
    state text NOT NULL CHECK(state IN ('allowed','blocked')),
    reason text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(business_id,document_id,revision_id,raw_sha256,policy_version),
    FOREIGN KEY(business_id,document_id,revision_id,raw_sha256)
        REFERENCES report_document_revisions(business_id,document_id,id,raw_sha256)
);
CREATE TABLE IF NOT EXISTS report_derivatives (
    business_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    raw_sha256 text NOT NULL,
    policy_version text NOT NULL,
    renderer_version text NOT NULL,
    derived_version integer NOT NULL CHECK(derived_version>0),
    status text NOT NULL CHECK(status IN ('ready','failed')),
    canonical_text text,
    canonical_sha256 text CHECK(canonical_sha256 ~ '^[0-9a-f]{64}$'),
    inventory jsonb,
    inventory_sha256 text CHECK(inventory_sha256 ~ '^[0-9a-f]{64}$'),
    snapshot_html text CHECK(octet_length(snapshot_html)<=20971520),
    issue text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(business_id,document_id,revision_id,raw_sha256,policy_version,renderer_version),
    FOREIGN KEY(business_id,document_id,revision_id,raw_sha256)
        REFERENCES report_document_revisions(business_id,document_id,id,raw_sha256),
    CHECK ((status='ready' AND canonical_text IS NOT NULL AND canonical_sha256 IS NOT NULL
        AND inventory IS NOT NULL AND inventory_sha256 IS NOT NULL AND issue IS NULL)
        OR (status='failed' AND canonical_text IS NULL AND canonical_sha256 IS NULL
        AND inventory IS NULL AND inventory_sha256 IS NULL AND snapshot_html IS NULL AND issue IS NOT NULL)),
    CHECK(octet_length(canonical_text)<=4000000 AND octet_length(inventory::text)<=16777216)
);
CREATE TABLE IF NOT EXISTS report_derivation_jobs (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    raw_sha256 text NOT NULL,
    policy_version text NOT NULL,
    renderer_version text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','ready','failed')),
    claim_id uuid,
    attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(business_id,document_id,revision_id,raw_sha256,policy_version,renderer_version),
    FOREIGN KEY(business_id,document_id,revision_id,raw_sha256)
        REFERENCES report_document_revisions(business_id,document_id,id,raw_sha256)
);
DROP TRIGGER IF EXISTS report_presentation_immutable ON report_presentation_checks;
CREATE TRIGGER report_presentation_immutable BEFORE UPDATE OR DELETE ON report_presentation_checks
    FOR EACH ROW EXECUTE FUNCTION keep_report_revision();
DROP TRIGGER IF EXISTS report_derivative_immutable ON report_derivatives;
CREATE TRIGGER report_derivative_immutable BEFORE UPDATE OR DELETE ON report_derivatives
    FOR EACH ROW EXECUTE FUNCTION keep_report_revision();
CREATE OR REPLACE FUNCTION keep_report_projection() RETURNS trigger AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Report revision cannot be deleted'; END IF;
    IF (NEW.id,NEW.business_id,NEW.document_id,NEW.ordinal,NEW.raw_sha256,NEW.raw_bytes,
        NEW.profile_version,NEW.verification_state,NEW.created_at)
       IS DISTINCT FROM (OLD.id,OLD.business_id,OLD.document_id,OLD.ordinal,OLD.raw_sha256,OLD.raw_bytes,
        OLD.profile_version,OLD.verification_state,OLD.created_at) THEN
        RAISE EXCEPTION 'Report source and revision are immutable';
    END IF;
    IF NEW.presentation_state NOT IN ('not_evaluated','allowed','blocked') OR
       NEW.derive_status NOT IN ('pending','ready','failed') THEN
        RAISE EXCEPTION 'Unknown report projection state';
    END IF;
    IF NEW.presentation_state<>'not_evaluated' AND NOT EXISTS (
        SELECT 1 FROM report_presentation_checks p WHERE
        (p.business_id,p.document_id,p.revision_id,p.raw_sha256,p.policy_version,p.state,p.reason)
        IS NOT DISTINCT FROM (NEW.business_id,NEW.document_id,NEW.id,NEW.raw_sha256,
            NEW.policy_version,NEW.presentation_state,NEW.presentation_reason)) THEN
        RAISE EXCEPTION 'Presentation projection needs its immutable assessment';
    END IF;
    IF NEW.derived_version=0 THEN
        IF NEW.derive_status<>'pending' OR NEW.canonical_text IS NOT NULL OR NEW.canonical_sha256 IS NOT NULL
            OR NEW.inventory_sha256 IS NOT NULL OR NEW.snapshot_html IS NOT NULL OR NEW.derive_issue IS NOT NULL THEN
            RAISE EXCEPTION 'Pending projection cannot contain derivatives';
        END IF;
    ELSIF NOT EXISTS (SELECT 1 FROM report_derivatives d WHERE
        (d.business_id,d.document_id,d.revision_id,d.raw_sha256,d.policy_version,d.renderer_version,
         d.derived_version,d.status,d.canonical_text,d.canonical_sha256,d.inventory_sha256,d.snapshot_html,d.issue)
        IS NOT DISTINCT FROM (NEW.business_id,NEW.document_id,NEW.id,NEW.raw_sha256,NEW.policy_version,NEW.renderer_version,
         NEW.derived_version,NEW.derive_status,NEW.canonical_text,NEW.canonical_sha256,NEW.inventory_sha256,NEW.snapshot_html,NEW.derive_issue)) THEN
        RAISE EXCEPTION 'Derivative projection needs its immutable result';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS report_revision_immutable ON report_document_revisions;
CREATE TRIGGER report_revision_immutable BEFORE UPDATE OR DELETE ON report_document_revisions
    FOR EACH ROW EXECUTE FUNCTION keep_report_projection();
INSERT INTO schema_versions(version) VALUES (36) ON CONFLICT DO NOTHING;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='report_projection_states') THEN
        ALTER TABLE report_document_revisions ADD CONSTRAINT report_projection_states CHECK(
            presentation_state IN ('not_evaluated','allowed','blocked') AND derived_version>=0
            AND derive_status IN ('pending','ready','failed')
            AND (derived_version>0 OR (derive_status='pending' AND canonical_text IS NULL
                AND canonical_sha256 IS NULL AND inventory_sha256 IS NULL AND snapshot_html IS NULL AND derive_issue IS NULL)));
    END IF;
END $$;
CREATE OR REPLACE FUNCTION keep_derivation_job_identity() RETURNS trigger AS $$
BEGIN
    IF (NEW.id,NEW.business_id,NEW.document_id,NEW.revision_id,NEW.raw_sha256,NEW.policy_version,NEW.renderer_version,NEW.created_at)
       IS DISTINCT FROM (OLD.id,OLD.business_id,OLD.document_id,OLD.revision_id,OLD.raw_sha256,OLD.policy_version,OLD.renderer_version,OLD.created_at) THEN
        RAISE EXCEPTION 'Render job source identity is immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS report_derivation_job_source ON report_derivation_jobs;
CREATE TRIGGER report_derivation_job_source BEFORE UPDATE ON report_derivation_jobs
    FOR EACH ROW EXECUTE FUNCTION keep_derivation_job_identity();

-- Migration 37: native reports are additional sources; historical HTML identities remain unchanged.
ALTER TABLE report_documents DROP CONSTRAINT IF EXISTS report_documents_origin_check;
ALTER TABLE report_documents ADD CONSTRAINT report_documents_origin_check
    CHECK(origin IN ('engine_html','engine_blocks'));
INSERT INTO schema_versions(version) VALUES (37) ON CONFLICT DO NOTHING;

-- Native preterminal checks share the parent run's proxy, quotas and USD ledger.
CREATE TABLE IF NOT EXISTS engine_native_cycles (
    run_id UUID PRIMARY KEY REFERENCES engine_runs(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    stage TEXT NOT NULL CHECK(stage IN ('checking','correcting','final_checking','complete','incomplete')),
    draft_revision_id UUID NOT NULL REFERENCES engine_document_revisions(id),
    selected_revision_id UUID REFERENCES engine_document_revisions(id),
    correction_used BOOLEAN NOT NULL DEFAULT false,
    issue TEXT,
    CHECK(stage IN ('complete','incomplete') OR selected_revision_id IS NULL),
    CHECK(stage<>'complete' OR selected_revision_id IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS engine_native_checks (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES engine_runs(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    revision_id UUID NOT NULL REFERENCES engine_document_revisions(id),
    raw_sha256 TEXT NOT NULL CHECK(raw_sha256 ~ '^[0-9a-f]{64}$'),
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','complete','incomplete')),
    credential_sha256 TEXT NOT NULL,
    instance_id UUID NOT NULL,
    session_id TEXT,
    message_id TEXT NOT NULL,
    dispatched BOOLEAN NOT NULL DEFAULT false,
    input_sha256 TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0 CHECK(calls BETWEEN 0 AND 20),
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    finished_at TIMESTAMPTZ,
    observations JSONB,
    raw_result BYTEA CHECK(octet_length(raw_result)<=262144),
    result JSONB,
    result_sha256 TEXT,
    issue TEXT,
    UNIQUE(run_id,revision_id,version),
    CHECK((status='complete')=(result IS NOT NULL)),
    CHECK((result IS NULL)=(result_sha256 IS NULL))
);
CREATE OR REPLACE FUNCTION guard_native_check() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Native check history is immutable'; END IF;
    IF TG_OP='UPDATE' AND (OLD.status<>'running' OR
        (OLD.id,OLD.run_id,OLD.business_id,OLD.revision_id,OLD.raw_sha256,OLD.version,
         OLD.credential_sha256,OLD.instance_id,OLD.message_id,OLD.input_sha256,OLD.started_at)
         IS DISTINCT FROM
        (NEW.id,NEW.run_id,NEW.business_id,NEW.revision_id,NEW.raw_sha256,NEW.version,
         NEW.credential_sha256,NEW.instance_id,NEW.message_id,NEW.input_sha256,NEW.started_at))
        THEN RAISE EXCEPTION 'Native check identity/result is immutable'; END IF;
    IF NOT EXISTS(SELECT 1 FROM engine_document_revisions r JOIN engine_documents d ON d.id=r.document_id
        WHERE r.id=NEW.revision_id AND r.business_id=NEW.business_id AND d.run_id=NEW.run_id
        AND d.business_id=NEW.business_id AND r.raw_sha256=NEW.raw_sha256)
        THEN RAISE EXCEPTION 'Native check source mismatch'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS native_check_guard ON engine_native_checks;
CREATE TRIGGER native_check_guard BEFORE INSERT OR UPDATE OR DELETE ON engine_native_checks FOR EACH ROW EXECUTE FUNCTION guard_native_check();
INSERT INTO schema_versions(version) VALUES (38) ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION guard_native_cycle() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Native cycle history is retained'; END IF;
    IF TG_OP='UPDATE' AND (OLD.stage IN ('complete','incomplete') OR OLD.run_id<>NEW.run_id OR OLD.business_id<>NEW.business_id
        OR OLD.correction_used AND NOT NEW.correction_used) THEN RAISE EXCEPTION 'Native cycle cannot be reopened'; END IF;
    IF NOT EXISTS(SELECT 1 FROM engine_document_revisions r JOIN engine_documents d ON d.id=r.document_id
        WHERE r.id=NEW.draft_revision_id AND d.run_id=NEW.run_id AND d.business_id=NEW.business_id AND r.business_id=NEW.business_id)
        THEN RAISE EXCEPTION 'Native cycle source mismatch'; END IF;
    IF NEW.selected_revision_id IS NOT NULL AND (NEW.selected_revision_id<>NEW.draft_revision_id OR NOT EXISTS(
        SELECT 1 FROM engine_document_revisions r JOIN engine_documents d ON d.id=r.document_id
        WHERE r.id=NEW.selected_revision_id AND r.business_id=NEW.business_id
        AND d.run_id=NEW.run_id AND d.business_id=NEW.business_id))
        THEN RAISE EXCEPTION 'Native selection source mismatch'; END IF;
    IF NEW.selected_revision_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM engine_native_checks c
        WHERE c.run_id=NEW.run_id AND c.business_id=NEW.business_id AND c.revision_id=NEW.selected_revision_id
        AND c.version='priority-check-1-' || CASE WHEN NEW.correction_used THEN 'final' ELSE 'initial' END
        AND c.status=CASE WHEN NEW.stage='complete' THEN 'complete' ELSE 'incomplete' END)
        THEN RAISE EXCEPTION 'Native selection requires final check'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS native_cycle_guard ON engine_native_cycles;
CREATE TRIGGER native_cycle_guard BEFORE INSERT OR UPDATE OR DELETE ON engine_native_cycles FOR EACH ROW EXECUTE FUNCTION guard_native_cycle();
-- Quick chat calculations: durable intent and ownership, written before any Docker call.
-- executions keeps the result; chat_retrievals keeps the model-facing observation.
CREATE TABLE IF NOT EXISTS chat_calculations (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    turn_id uuid NOT NULL REFERENCES chat_turns(id),
    attempt integer NOT NULL,
    ordinal integer NOT NULL,
    analysis_id uuid NOT NULL,
    request jsonb NOT NULL,
    identity_sha256 text NOT NULL,
    definitions jsonb NOT NULL,
    dependencies jsonb NOT NULL,
    admission text NOT NULL CHECK (admission IN ('reserved','admitted','refused')),
    refusal text,
    execution_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (turn_id, attempt, ordinal),
    UNIQUE (execution_id),
    CHECK ((admission = 'admitted') = (execution_id IS NOT NULL)),
    CHECK ((admission = 'refused') = (refusal IS NOT NULL)),
    FOREIGN KEY (business_id, conversation_id) REFERENCES chat_conversations(business_id, id),
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id),
    FOREIGN KEY (business_id, execution_id) REFERENCES executions(business_id, id)
);
CREATE INDEX IF NOT EXISTS chat_calculations_turn ON chat_calculations(turn_id, attempt);
-- Reports offered by the chat. Only an explicit owner acceptance (a separate endpoint,
-- never model output) turns an offer into a job, atomically with its receipt.
CREATE TABLE IF NOT EXISTS chat_report_offers (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    turn_id uuid NOT NULL REFERENCES chat_turns(id),
    attempt integer NOT NULL,
    analysis_id uuid NOT NULL,
    objective text NOT NULL,
    brief jsonb,
    continuation jsonb NOT NULL,
    offer_sha256 text NOT NULL,
    status text NOT NULL CHECK (status IN ('open','accepted')),
    accepted_turn_id uuid UNIQUE REFERENCES chat_turns(id),
    accepted_objective text,
    request_key uuid,
    job_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    accepted_at timestamptz,
    UNIQUE (turn_id, attempt),
    CHECK ((status = 'accepted') = (accepted_turn_id IS NOT NULL AND accepted_objective IS NOT NULL AND request_key IS NOT NULL)),
    FOREIGN KEY (business_id, conversation_id) REFERENCES chat_conversations(business_id, id),
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id),
    FOREIGN KEY (business_id, job_id) REFERENCES web_jobs(business_id, id)
);
-- Version 39: quick chat calculations and report offers.
INSERT INTO schema_versions(version) VALUES (39) ON CONFLICT DO NOTHING;
-- Saved indicators: a fixed, owner-confirmed formula from a published quick calculation,
-- recomputed without a model on new dataset versions through an attempt journal.
CREATE TABLE IF NOT EXISTS saved_indicators (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    dataset_id uuid NOT NULL,
    name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    status text NOT NULL CHECK (status IN ('active','retired')),
    revision integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    retired_at timestamptz,
    UNIQUE (business_id, id),
    FOREIGN KEY (business_id, dataset_id) REFERENCES analyses(business_id, id)
);
CREATE TABLE IF NOT EXISTS indicator_versions (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    indicator_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    state text NOT NULL CHECK (state IN ('proposed','active','superseded','discarded')),
    code text NOT NULL,
    code_sha256 text NOT NULL,
    tables jsonb NOT NULL,
    metric_keys jsonb NOT NULL,
    definitions jsonb NOT NULL,
    signature jsonb NOT NULL,
    signature_sha256 text NOT NULL,
    provenance jsonb NOT NULL,
    applies_from integer,
    comparison jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    confirmed_at timestamptz,
    UNIQUE (indicator_id, version),
    UNIQUE (business_id, id),
    FOREIGN KEY (business_id, indicator_id) REFERENCES saved_indicators(business_id, id)
);
CREATE UNIQUE INDEX IF NOT EXISTS indicator_versions_active ON indicator_versions(indicator_id) WHERE state='active';
CREATE TABLE IF NOT EXISTS indicator_values (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    indicator_id uuid NOT NULL,
    version_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    dataset_version integer NOT NULL,
    status text NOT NULL CHECK (status IN ('pending','completed','unavailable','revoked')),
    reason text,
    detail text,
    metrics jsonb,
    meanings_basis jsonb,
    execution_id uuid,
    latest_attempt_id uuid,
    next_attempt_at timestamptz,
    computed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (indicator_id, version_id, analysis_id),
    UNIQUE (business_id, id),
    CHECK ((status = 'completed') = (metrics IS NOT NULL)),
    FOREIGN KEY (business_id, indicator_id) REFERENCES saved_indicators(business_id, id),
    FOREIGN KEY (business_id, version_id) REFERENCES indicator_versions(business_id, id),
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id),
    FOREIGN KEY (business_id, execution_id) REFERENCES executions(business_id, id)
);
CREATE INDEX IF NOT EXISTS indicator_values_due ON indicator_values(status, next_attempt_at) WHERE status='pending';
CREATE TABLE IF NOT EXISTS indicator_attempts (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    purpose text NOT NULL CHECK (purpose IN ('value','comparison')),
    value_id uuid,
    version_id uuid NOT NULL,
    analysis_id uuid NOT NULL,
    attempt_no integer NOT NULL CHECK (attempt_no > 0),
    identity jsonb NOT NULL,
    admission text NOT NULL CHECK (admission IN ('reserved','admitted','refused')),
    outcome text CHECK (outcome IN ('completed','transient','structural')),
    reason text,
    detail text,
    runtime jsonb,
    execution_id uuid UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK ((admission = 'admitted') = (execution_id IS NOT NULL)),
    CHECK ((purpose = 'value') = (value_id IS NOT NULL)),
    FOREIGN KEY (business_id, value_id) REFERENCES indicator_values(business_id, id),
    FOREIGN KEY (business_id, version_id) REFERENCES indicator_versions(business_id, id),
    FOREIGN KEY (business_id, analysis_id) REFERENCES analyses(business_id, id),
    FOREIGN KEY (business_id, execution_id) REFERENCES executions(business_id, id)
);
CREATE INDEX IF NOT EXISTS indicator_attempts_value ON indicator_attempts(value_id, attempt_no);
CREATE TABLE IF NOT EXISTS indicator_requests (
    business_id uuid NOT NULL,
    request_key uuid NOT NULL,
    kind text NOT NULL,
    request_sha256 text NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (business_id, request_key)
);
-- Owner-visible knowledge of indicators and follow-ups; bumped only when its projection changes.
CREATE TABLE IF NOT EXISTS knowledge_heads (
    business_id uuid PRIMARY KEY,
    indicators_revision integer NOT NULL DEFAULT 0,
    indicators_sha256 text NOT NULL DEFAULT '',
    follow_ups_revision integer NOT NULL DEFAULT 0,
    follow_ups_sha256 text NOT NULL DEFAULT ''
);
INSERT INTO schema_versions(version) VALUES (40) ON CONFLICT DO NOTHING;
-- Follow-up register: immutable action snapshots per native report revision and position,
-- and owner topics (one per action occurrence) whose state only the owner sets.
CREATE TABLE IF NOT EXISTS follow_ups (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    document_id uuid NOT NULL,
    content_sha256 text NOT NULL,
    current_action_id uuid,
    state text NOT NULL CHECK (state IN ('proposed','checked','closed')),
    availability text NOT NULL CHECK (availability IN ('available','withdrawn')),
    withdrawn_reason text,
    note text CHECK (note IS NULL OR char_length(note) <= 300),
    link jsonb,
    revision integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id, id)
);
CREATE INDEX IF NOT EXISTS follow_ups_document ON follow_ups(business_id, document_id);
CREATE TABLE IF NOT EXISTS follow_up_actions (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    document_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    block_id text NOT NULL,
    position integer NOT NULL,
    priority_title text NOT NULL,
    content jsonb NOT NULL,
    content_sha256 text NOT NULL,
    headline text NOT NULL,
    report_date timestamptz NOT NULL,
    dataset_id uuid,
    analysis_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}',
    topic_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (revision_id, block_id),
    UNIQUE (business_id, id),
    FOREIGN KEY (business_id, topic_id) REFERENCES follow_ups(business_id, id)
);
CREATE TABLE IF NOT EXISTS follow_up_events (
    id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    follow_up_id uuid NOT NULL,
    request_key uuid NOT NULL,
    request_sha256 text NOT NULL,
    from_state text,
    to_state text NOT NULL,
    note text,
    link jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id, request_key),
    FOREIGN KEY (business_id, follow_up_id) REFERENCES follow_ups(business_id, id)
);
CREATE TABLE IF NOT EXISTS follow_up_sync (
    document_id uuid PRIMARY KEY,
    business_id uuid NOT NULL,
    revision_id uuid,
    available boolean NOT NULL,
    synced_at timestamptz NOT NULL DEFAULT now()
);
