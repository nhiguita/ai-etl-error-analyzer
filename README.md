# AI ETL Error Analyzer

An API that reads Apache Hop pipeline logs, classifies the error, explains the probable cause and
recommends a fix, using a local LLM (Qwen3 4B on Ollama) with validated structured output.

```
POST /api/v1/logs/analyze
{"log_text": "<content of sample-logs/09_unknown_student_reference.log>"}
```

Real response from `qwen3:4b`:

```json
{
  "analysis_id": 1,
  "created_at": "2026-10-13T09:59:45.374632+02:00",
  "pipeline": "access_log_load",
  "failed_transform": "Insert access logs",
  "root_error": "ERROR: insert or update on table \"access_logs\" violates foreign key constraint \"access_logs_student_id_fkey\"",
  "error_type": "DATABASE_CONSTRAINT",
  "severity": "HIGH",
  "probable_cause": "The student_id value 999 does not exist in the students table, causing a foreign key constraint violation.",
  "recommendation": "Ensure that the student_id value 999 exists in the students table before inserting into access_logs. Check the students table for the existence of student_id 999 or update the source data to include valid student IDs.",
  "model": "qwen3:4b"
}
```

The type is correct; the expected severity for this case is `MEDIUM` (see [Results](#results)).

## Results

Evaluated on 15 real Hop failures reproduced on purpose (duplicates, invalid values, missing
columns, failed connections, missing files), each with a known root cause:

| Metric | qwen3:4b |
| --- | --- |
| `error_type` accuracy | 15/15 |
| `severity` accuracy | 14/15 |
| Root cause correct (manual review) | 13/15 (+1 partial) |
| Invalid / failed LLM responses | 0 |
| Mean latency per log | ~3.9 s (6 GB VRAM GPU) |

Details: [evaluation/REPORT.md](evaluation/REPORT.md) (generated) and
[evaluation/REVIEW.md](evaluation/REVIEW.md) (manual review and observations).

## How it works

```
Hop log ──► parser (deterministic) ──► prompt ──► Qwen3 4B (Ollama, JSON schema) ──► Pydantic ──► PostgreSQL
            pipeline, failed transform,                                              validation    analyzer.log_analyses
            root error, detail, key lines
```

1. **Parser** (`app/parser/log_parser.py`): reduces a Hop log with Java stack traces to the
   pipeline name, the failing transform, the root error (PostgreSQL/JDBC message, file or
   conversion error), the `Detail:` line and up to 20 relevant lines. No LLM involved.
2. **LLM** (`app/llm.py`, `app/prompts.py`): the parsed context and the error taxonomy are sent to
   Qwen3 through the Ollama Python client with `format=<JSON schema>`, temperature 0 and thinking
   disabled. Invalid output is retried once.
3. **Validation** (`app/schemas.py`): `error_type` and `severity` are enums of the
   [error taxonomy](docs/ERROR_TAXONOMY.md); text fields have length limits.
4. **Storage** (`app/models.py`, `sql/03_analyses.sql`): every analysis is saved with SQLAlchemy.

HTTP errors: `422` invalid request or no error found in the log, `502` the LLM returned an
invalid diagnosis twice, `503` Ollama or the database is unavailable.

## Stack

Python 3.14 · FastAPI · Pydantic · Ollama (Qwen3 4B) · PostgreSQL 18 · SQLAlchemy 2 · Apache Hop
2.19 · Pytest. No LangChain: the LLM call, structured output and validation are explicit.

## Repository layout

| Path | Content |
| --- | --- |
| `app/` | FastAPI app, log parser, LLM client, schemas, ORM model, evaluation logic |
| `hop-pipelines/` | Apache Hop project: `student_insert`, `student_sync`, `access_log_load`, `student_insert_with_phone`, fictitious CSV inputs |
| `sql/` | School schema with intentional constraints, fictitious seed data, analyses table |
| `sample-logs/` | 15 captured Hop error logs and `scenarios.json` (setup and ground truth) |
| `docs/ERROR_TAXONOMY.md` | Error types and severity rules |
| `evaluation/` | Evaluation results and review |
| `scripts/` | Environment setup, DB init, pipeline runner, log capture, evaluation, API launcher |
| `tests/` | Pytest suite (the LLM and the database are mocked) |

All data is fictitious.

## Setup (Ubuntu on WSL2)

Requirements: PostgreSQL, Java 21, Ollama with `qwen3:4b`, Python 3.14.

```bash
bash scripts/setup_wsl.sh                  # sudo: Java 21, unzip, DB role and database
# Apache Hop client 2.19 unzipped in tools/hop (not versioned)
ollama pull qwen3:4b

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env                       # set ETL_DB_PASSWORD
scripts/init_db.sh                         # school schema + seed data + analyzer schema
```

## Usage

```bash
# API (http://localhost:8000/docs)
scripts/run_api.sh

curl -X POST localhost:8000/api/v1/logs/analyze \
  -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"log_text": open(sys.argv[1]).read()}))' \
        sample-logs/09_unknown_student_reference.log)"

# Hop pipelines
scripts/run_pipeline.sh student_insert
scripts/run_pipeline.sh student_insert INPUT_FILE=students_invalid_status.csv

# Reproduce the 15 error scenarios and recapture their logs
.venv/bin/python scripts/capture_error_logs.py

# Evaluate the LLM against the ground truth (writes evaluation/)
.venv/bin/python scripts/evaluate.py

# Tests (no LLM or database needed)
.venv/bin/pytest -q
```

## Limitations

- Severity rules that depend on scope (one bad record vs. a broken setup) are the weakest point:
  scenario 09 was rated HIGH instead of MEDIUM.
- When PostgreSQL reports a CHECK violation without a column name, the model can pick the wrong
  value from the failing row (scenario 11). Adding the table's constraint definitions to the
  context is a possible improvement.
- The evaluation set is small (15 scenarios); the prompt was not tuned on it.

## License

[MIT](LICENSE) © 2026 Natalia Higuita Alzate
