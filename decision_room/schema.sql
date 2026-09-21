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
