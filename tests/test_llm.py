"""Tests for LLMAnalyzer with a mocked Ollama client (no real LLM calls)."""

from unittest.mock import MagicMock

import ollama
import pytest

from app.llm import InvalidDiagnosisError, LLMAnalyzer, LLMUnavailableError
from app.parser import ParsedLog
from app.schemas import ErrorType, LLMDiagnosis, Severity

VALID_JSON = (
    '{"error_type": "DATABASE_CONSTRAINT", "severity": "HIGH", '
    '"probable_cause": "Duplicate primary key student_id 21.", '
    '"recommendation": "Use Insert/Update or skip existing IDs."}'
)
PARSED = ParsedLog(
    pipeline="student_insert",
    failed_transform="Insert students",
    root_error='ERROR: duplicate key value violates unique constraint "students_pkey"',
    detail="Key (student_id)=(21) already exists.",
    error_lines=["ERROR: Unexpected batch update error committing the database connection."],
)


def chat_response(content: str) -> ollama.ChatResponse:
    return ollama.ChatResponse(message=ollama.Message(role="assistant", content=content))


def make_analyzer(*side_effect) -> tuple[LLMAnalyzer, MagicMock]:
    client = MagicMock()
    client.chat.side_effect = list(side_effect)
    return LLMAnalyzer(client, "qwen3:4b"), client


def test_returns_validated_diagnosis():
    analyzer, client = make_analyzer(chat_response(VALID_JSON))

    diagnosis = analyzer.diagnose(PARSED, "student_insert")

    assert diagnosis.error_type is ErrorType.DATABASE_CONSTRAINT
    assert diagnosis.severity is Severity.HIGH
    client.chat.assert_called_once()


def test_sends_schema_and_parsed_context():
    analyzer, client = make_analyzer(chat_response(VALID_JSON))

    analyzer.diagnose(PARSED, "student_insert")

    kwargs = client.chat.call_args.kwargs
    assert kwargs["model"] == "qwen3:4b"
    assert kwargs["format"] == LLMDiagnosis.model_json_schema()
    assert kwargs["think"] is False
    assert kwargs["options"] == {"temperature": 0}
    system, user = kwargs["messages"]
    assert "DATABASE_CONSTRAINT" in system["content"]
    assert "Pipeline: student_insert" in user["content"]
    assert "Failed transform: Insert students" in user["content"]
    assert 'constraint "students_pkey"' in user["content"]
    assert "Key (student_id)=(21) already exists." in user["content"]


def test_retries_once_on_invalid_output():
    analyzer, client = make_analyzer(chat_response("not json"), chat_response(VALID_JSON))

    diagnosis = analyzer.diagnose(PARSED, "student_insert")

    assert diagnosis.severity is Severity.HIGH
    assert client.chat.call_count == 2


@pytest.mark.parametrize(
    "bad_output",
    [
        "not json",
        '{"error_type": "NETWORK", "severity": "HIGH", "probable_cause": "x", "recommendation": "y"}',
        '{"error_type": "DATABASE_CONSTRAINT", "severity": "HIGH", "probable_cause": "", "recommendation": "y"}',
        '{"error_type": "DATABASE_CONSTRAINT", "severity": "URGENT", "probable_cause": "x", "recommendation": "y"}',
    ],
)
def test_raises_after_repeated_invalid_output(bad_output):
    analyzer, client = make_analyzer(chat_response(bad_output), chat_response(bad_output))

    with pytest.raises(InvalidDiagnosisError):
        analyzer.diagnose(PARSED, "student_insert")
    assert client.chat.call_count == 2


@pytest.mark.parametrize(
    "error",
    [ollama.ResponseError("model 'qwen3:4b' not found", 404), ConnectionError("Failed to connect to Ollama")],
)
def test_wraps_ollama_errors(error):
    analyzer, _ = make_analyzer(error)

    with pytest.raises(LLMUnavailableError):
        analyzer.diagnose(PARSED, "student_insert")


def test_from_env_reads_model(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    assert LLMAnalyzer.from_env().model == "qwen3:8b"
