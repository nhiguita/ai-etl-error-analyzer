# Error taxonomy

Labels used for the ground truth in `sample-logs/scenarios.json` and, later, for the
analyzer output. One error type and one severity per failed pipeline run.

## Error types

| Type | Meaning | Typical log text |
| --- | --- | --- |
| `DATABASE_CONSTRAINT` | The database rejected a row because of a declared rule: primary key, unique, foreign key, check or not-null. | `violates unique constraint`, `violates check constraint`, `violates foreign key constraint`, `violates not-null constraint` |
| `INVALID_VALUE` | A value cannot be converted to the target type or does not fit it (format, syntax, length), whether Hop or PostgreSQL detects it. | `couldn't convert string`, `invalid input syntax for type`, `value too long for type` |
| `SCHEMA_MISMATCH` | The pipeline references a column or table that does not exist in the target database. | `column "..." of relation "..." does not exist` |
| `DATABASE_CONNECTION` | The pipeline cannot open a connection: host/port unreachable or database missing. | `Connection to host:port refused`, `database "..." does not exist` |
| `AUTHENTICATION` | The database refused the credentials. | `password authentication failed` |
| `FILE_NOT_FOUND` | An input file expected by the pipeline is missing. | `FileNotFoundException`, `No such file or directory` |

Precedence: a value rejected by a `CHECK` constraint (e.g. an unknown `status`) is
`DATABASE_CONSTRAINT`, because the database names the violated rule; `INVALID_VALUE` is for
type, format and length errors.

## Severity

Severity reflects the scope of the impact and what it takes to recover.

| Severity | Rule |
| --- | --- |
| `CRITICAL` | No pipeline can reach the database (connection refused, credentials rejected, database missing). Every load that uses the connection fails until it is fixed. |
| `HIGH` | The pipeline itself or its setup is wrong: schema mismatch, missing input file, or a non-idempotent load re-run (duplicate primary key on a full batch). Correcting individual records does not help. |
| `MEDIUM` | Specific source records are invalid (duplicate email, unknown reference, value outside the allowed set, bad format). Fixing or removing those records lets the load succeed. |
| `LOW` | The pipeline finished but logged warnings. Reserved; no current scenario. |

In every scenario the transform fails, the batch is rolled back and the pipeline exits with
code 1, so no partial data is written.
