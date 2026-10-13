"""Tests for POST /api/v1/logs/analyze with a fake analyzer (no real LLM calls)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.llm import InvalidDiagnosisError, LLMUnavailableError
from app.main import app, get_analyzer
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
def client():
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_analyzes_sample_log(client, use_analyzer):
    fake = use_analyzer(DIAGNOSIS)
    log_text = (SAMPLE_LOGS / "01_duplicate_student_pk.log").read_text()

    response = client.post(URL, json={"log_text": log_text})

    assert response.status_code == 200
    assert response.json() == {
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


def test_request_pipeline_overrides_log(client, use_analyzer):
    fake = use_analyzer(DIAGNOSIS)

    response = client.post(URL, json={"log_text": "ERROR: duplicate key value", "pipeline": "student_sync"})

    assert response.status_code == 200
    assert response.json()["pipeline"] == "student_sync"
    assert fake.calls[0][1] == "student_sync"


def test_log_without_error_returns_422(client, use_analyzer):
    fake = use_analyzer(DIAGNOSIS)

    response = client.post(URL, json={"log_text": "Execution started for pipeline [student_insert]"})

    assert response.status_code == 422
    assert response.json()["detail"] == "No error found in the log."
    assert fake.calls == []


@pytest.mark.parametrize("body", [{}, {"log_text": ""}, {"log_text": "ERROR", "pipeline": "x" * 101}])
def test_invalid_request_returns_422(client, use_analyzer, body):
    use_analyzer(DIAGNOSIS)
    assert client.post(URL, json=body).status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(LLMUnavailableError("down"), 503), (InvalidDiagnosisError("bad json"), 502)],
)
def test_llm_failures_map_to_http_errors(client, use_analyzer, error, status_code):
    use_analyzer(error)

    response = client.post(URL, json={"log_text": "ERROR: something failed"})

    assert response.status_code == status_code
    assert "bad json" not in response.text
