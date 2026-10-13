"""Tests for the deterministic Hop log parser."""

import json
from pathlib import Path

import pytest

from app.parser import parse_log
from app.parser.log_parser import MAX_ERROR_LINES, MAX_LINE_LENGTH

SAMPLE_LOGS = Path(__file__).resolve().parent.parent / "sample-logs"
SCENARIOS = {s["id"]: s for s in json.loads((SAMPLE_LOGS / "scenarios.json").read_text())}

# scenario id -> (failed transform, substring of the root error)
EXPECTED = {
    "01_duplicate_student_pk": ("Insert students", 'unique constraint "students_pkey"'),
    "02_duplicate_email": ("Insert students", 'unique constraint "students_email_key"'),
    "03_invalid_status": ("Insert students", 'check constraint "students_status_check"'),
    "04_missing_email": ("Insert students", 'null value in column "email"'),
    "05_invalid_date_format": ("Read new students", "couldn't convert string [01/02/2026]"),
    "06_document_too_long": ("Insert students", "value too long for type character varying(20)"),
    "07_nonexistent_column": ("Insert students", 'column "phone_number" of relation "students" does not exist'),
    "08_sync_invalid_status": ("Sync students", 'check constraint "students_status_check"'),
    "09_unknown_student_reference": ("Insert access logs", 'foreign key constraint "access_logs_student_id_fkey"'),
    "10_invalid_ip_address": ("Insert access logs", 'invalid input syntax for type inet: "10.20.5.300"'),
    "11_invalid_access_result": ("Insert access logs", 'check constraint "access_logs_result_check"'),
    "12_missing_input_file": ("Read new students", "students_2026_10.csv (No such file or directory)"),
    "13_connection_refused": ("Sync students", "Connection to localhost:5499 refused"),
    "14_authentication_failed": ("Sync students", 'password authentication failed for user "etl_analyzer"'),
    "15_database_missing": ("Insert access logs", 'database "etl_analyzer_archive" does not exist'),
}


def test_every_scenario_has_expectations():
    assert set(EXPECTED) == set(SCENARIOS)


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED))
def test_parses_sample_log(scenario_id):
    parsed = parse_log((SAMPLE_LOGS / f"{scenario_id}.log").read_text())
    transform, root_fragment = EXPECTED[scenario_id]

    assert parsed.has_error
    assert parsed.pipeline == SCENARIOS[scenario_id]["pipeline"]
    assert parsed.failed_transform == transform
    assert root_fragment in parsed.root_error
    assert 0 < len(parsed.error_lines) <= MAX_ERROR_LINES
    assert all(len(line) <= MAX_LINE_LENGTH for line in parsed.error_lines)
    assert not any(line.startswith("at ") for line in parsed.error_lines)
    assert len(parsed.error_lines) == len(set(parsed.error_lines))


@pytest.mark.parametrize(
    ("scenario_id", "detail"),
    [
        ("01_duplicate_student_pk", "Key (student_id)=(21) already exists."),
        ("09_unknown_student_reference", 'Key (student_id)=(999) is not present in table "students".'),
    ],
)
def test_extracts_detail_without_jdbc_hint(scenario_id, detail):
    parsed = parse_log((SAMPLE_LOGS / f"{scenario_id}.log").read_text())
    assert parsed.detail == detail


def test_parses_short_excerpt_from_plan():
    text = 'Pipeline: student_sync\nERROR: duplicate key value violates\nunique constraint "students_pkey"'
    parsed = parse_log(text)

    assert parsed.pipeline == "student_sync"
    assert parsed.failed_transform is None
    assert parsed.root_error.startswith("ERROR: duplicate key value violates")
    assert parsed.has_error


def test_successful_log_has_no_error():
    text = (
        "2026/10/13 09:46:14 - student_insert - Execution started for pipeline [student_insert]\n"
        "2026/10/13 09:46:15 - Insert students.0 - Finished processing (I=0, O=5, R=5, W=5, U=0, E=0)\n"
    )
    parsed = parse_log(text)

    assert parsed.pipeline == "student_insert"
    assert parsed.failed_transform is None
    assert parsed.root_error is None
    assert parsed.error_lines == []
    assert not parsed.has_error


def test_empty_input():
    parsed = parse_log("")
    assert parsed.pipeline is None
    assert not parsed.has_error


def test_long_lines_are_truncated():
    text = "ERROR: " + "x" * 1000
    parsed = parse_log(text)
    assert len(parsed.root_error) == MAX_LINE_LENGTH
    assert parsed.root_error.endswith("...")


def test_error_lines_are_capped():
    text = "\n".join(f"ERROR: failure number {i}" for i in range(100))
    assert len(parse_log(text).error_lines) == MAX_ERROR_LINES
