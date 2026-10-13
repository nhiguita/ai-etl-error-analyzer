-- Results of the log analyzer. Separate schema so that resetting the
-- school data (01_schema.sql) does not delete stored analyses.
-- Re-runnable: creates objects only if they do not exist.

SET client_min_messages = warning;
CREATE SCHEMA IF NOT EXISTS analyzer;

CREATE TABLE IF NOT EXISTS analyzer.log_analyses (
    analysis_id      BIGSERIAL    PRIMARY KEY,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    pipeline         VARCHAR(300),
    failed_transform VARCHAR(300),
    root_error       VARCHAR(300),
    error_type       VARCHAR(30)  NOT NULL CHECK (error_type IN (
        'DATABASE_CONSTRAINT', 'INVALID_VALUE', 'SCHEMA_MISMATCH',
        'DATABASE_CONNECTION', 'AUTHENTICATION', 'FILE_NOT_FOUND')),
    severity         VARCHAR(10)  NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    probable_cause   VARCHAR(300) NOT NULL,
    recommendation   VARCHAR(500) NOT NULL,
    model            VARCHAR(100) NOT NULL,
    log_text         TEXT         NOT NULL
);

CREATE INDEX IF NOT EXISTS log_analyses_pipeline_created_idx
    ON analyzer.log_analyses (pipeline, created_at DESC);
