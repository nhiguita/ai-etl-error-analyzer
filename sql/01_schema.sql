-- Fictitious school data used by the Apache Hop pipelines.
-- The constraints are intentional: the error scenarios rely on them
-- (duplicate keys, invalid values, missing references).
-- Re-runnable: drops and recreates the schema.

SET client_min_messages = warning;
DROP SCHEMA IF EXISTS school CASCADE;
CREATE SCHEMA school;

CREATE TABLE school.students (
    student_id      INTEGER      PRIMARY KEY,
    document_number VARCHAR(20)  NOT NULL UNIQUE,
    full_name       VARCHAR(120) NOT NULL,
    email           VARCHAR(120) NOT NULL UNIQUE,
    program         VARCHAR(80)  NOT NULL,
    enrollment_date DATE         NOT NULL,
    status          VARCHAR(12)  NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'graduated')),
    updated_at      TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE TABLE school.access_logs (
    log_id      BIGSERIAL   PRIMARY KEY,
    student_id  INTEGER     NOT NULL REFERENCES school.students (student_id),
    accessed_at TIMESTAMP   NOT NULL,
    resource    VARCHAR(80) NOT NULL,
    result      VARCHAR(10) NOT NULL CHECK (result IN ('success', 'denied')),
    ip_address  INET        NOT NULL
);

CREATE INDEX access_logs_student_idx ON school.access_logs (student_id, accessed_at);
