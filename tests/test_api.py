"""Tests for POST /api/v1/logs/analyze with a fake analyzer and session (no LLM, no database)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.llm import InvalidDiagnosisError, LLMUnavailableError
from app.db import get_session
from app.main import app, get_analyzer
from app.models import LogAnalysis
from app.schemas import LLMDiagnosis

SAMPLE_LOGS = Path(__file__).resolve().parent.parent / "sample-logs"
URL = "/api/v1/logs/analyze"


class FakeAnalyzer:
    model = "fake-model"

    def __init__(self, result):
        self.result = result
        self.calls = []

    def diagnose(self, parsed, pipeline):
        self.calls.append((parsed, pipeline))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


CREATED_AT = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


class FakeSession:
    def __init__(self, fail_on_commit=False):
        self.fail_on_commit = fail_on_commit
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add(self, record):
        self.added.append(record)

    def commit(self):
        if self.fail_on_commit:
            raise OperationalError("INSERT", {}, Exception("connection lost"))
        self.committed = True

    def refresh(self, record):
        record.analysis_id = 1
        record.created_at = CREATED_AT

    def rollback(self):
        self.rolled_back = True


DIAGNOSIS = LLMDiagnosis(
    error_type="DATABASE_CONSTRAINT",
    severity="HIGH",
    probable_cause="Duplicate primary key.",
    recommendation="Review insert logic and existing IDs.",
)


@pytest.fixture
def use_analyzer():
    def install(result):
        fake = FakeAnalyzer(result)
        app.dependency_overrides[get_analyzer] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.clear()


@pytest.fixture
def use_session():
    def install(**kwargs):
        fake = FakeSession(**kwargs)
        app.dependency_overrides[get_session] = lambda: fake
        return fake

    return install


@pytest.fixture
def session(use_session):
    return use_session()


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_analyzes_and_stores_sample_log(client, use_analyzer, session):
    fake = use_analyzer(DIAGNOSIS)
    log_text = (SAMPLE_LOGS / "01_duplicate_student_pk.log").read_text()

    response = client.post(URL, json={"log_text": log_text})

    assert response.status_code == 200
    assert response.json() == {
        "analysis_id": 1,
        "created_at": "2026-10-13T12:00:00Z",
        "pipeline": "student_insert",
        "failed_transform": "Insert students",
        "root_error": 'ERROR: duplicate key value violates unique constraint "students_pkey"',
        "error_type": "DATABASE_CONSTRAINT",
        "severity": "HIGH",
        "probable_cause": "Duplicate primary key.",
        "recommendation": "Review insert logic and existing IDs.",
        "model": "fake-model",
    }
    parsed, pipeline = fake.calls[0]
    assert parsed.detail == "Key (student_id)=(21) already exists."
    assert pipeline == "student_insert"

    [record] = session.added
    assert isinstance(record, LogAnalysis)
    assert session.committed
    assert record.pipeline == "student_insert"
    assert record.failed_transform == "Insert students"
    assert record.error_type == "DATABASE_CONSTRAINT"
    assert record.severity == "HIGH"
    assert record.model == "fake-model"
    assert record.log_text == log_text


def test_request_pipeline_overrides_log(client, use_analyzer, session):
    fake = use_analyzer(DIAGNOSIS)

    response = client.post(URL, json={"log_text": "ERROR: duplicate key value", "pipeline": "student_sync"})

    assert response.status_code == 200
    assert response.json()["pipeline"] == "student_sync"
    assert fake.calls[0][1] == "student_sync"
    assert session.added[0].pipeline == "student_sync"


def test_log_without_error_returns_422(client, use_analyzer, session):
    fake = use_analyzer(DIAGNOSIS)

    response = client.post(URL, json={"log_text": "Execution started for pipeline [student_insert]"})

    assert response.status_code == 422
    assert response.json()["detail"] == "No error found in the log."
    assert fake.calls == []
    assert session.added == []


@pytest.mark.parametrize("body", [{}, {"log_text": ""}, {"log_text": "ERROR", "pipeline": "x" * 101}])
def test_invalid_request_returns_422(client, use_analyzer, session, body):
    use_analyzer(DIAGNOSIS)
    assert client.post(URL, json=body).status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(LLMUnavailableError("down"), 503), (InvalidDiagnosisError("bad json"), 502)],
)
def test_llm_failures_map_to_http_errors(client, use_analyzer, session, error, status_code):
    use_analyzer(error)

    response = client.post(URL, json={"log_text": "ERROR: something failed"})

    assert response.status_code == status_code
    assert "bad json" not in response.text
    assert session.added == []


def test_storage_failure_returns_503(client, use_analyzer, use_session):
    use_analyzer(DIAGNOSIS)
    session = use_session(fail_on_commit=True)

    response = client.post(URL, json={"log_text": "ERROR: something failed"})

    assert response.status_code == 503
    assert response.json()["detail"] == "The analysis could not be stored."
    assert session.rolled_back
    assert "connection lost" not in response.text
