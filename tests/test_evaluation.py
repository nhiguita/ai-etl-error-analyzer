"""Tests for the evaluation helpers with a fake analyzer (no real LLM calls)."""

import json
from pathlib import Path

from app.evaluation import evaluate, evaluate_scenario, summarize, to_json, to_markdown
from app.llm import LLMUnavailableError
from app.schemas import LLMDiagnosis

SAMPLE_LOGS = Path(__file__).resolve().parent.parent / "sample-logs"
SCENARIOS = json.loads((SAMPLE_LOGS / "scenarios.json").read_text())


class TruthAnalyzer:
    """Returns the ground truth, except for the ids in `wrong` (fixed answer) or `broken` (error)."""

    model = "fake-model"

    def __init__(self, wrong=(), broken=()):
        self.wrong = set(wrong)
        self.broken = set(broken)
        self.current = None

    def diagnose(self, parsed, pipeline):
        scenario = self.current
        if scenario["id"] in self.broken:
            raise LLMUnavailableError("Ollama is down")
        if scenario["id"] in self.wrong:
            return LLMDiagnosis(
                error_type="INVALID_VALUE", severity="LOW", probable_cause="wrong", recommendation="wrong"
            )
        expected = scenario["expected"]
        return LLMDiagnosis(
            error_type=expected["error_type"],
            severity=expected["severity"],
            probable_cause=expected["root_cause"],
            recommendation="Fix it.",
        )


def run(analyzer):
    # Feed scenarios one by one so the fake knows which answer to give.
    results = []
    for scenario in SCENARIOS:
        analyzer.current = scenario
        log_text = (SAMPLE_LOGS / f"{scenario['id']}.log").read_text()
        results.append(evaluate_scenario(analyzer, scenario, log_text))
    return results


def test_perfect_analyzer_scores_everything():
    results = run(TruthAnalyzer())
    summary = summarize(results, "fake-model")

    assert summary.total == len(SCENARIOS)
    assert summary.error_type_correct == summary.severity_correct == summary.both_correct == summary.total
    assert summary.failures == 0
    assert summary.error_type_confusion == {}
    assert summary.severity_confusion == {}


def test_counts_mistakes_and_failures():
    results = run(TruthAnalyzer(wrong={"01_duplicate_student_pk"}, broken={"13_connection_refused"}))
    summary = summarize(results, "fake-model")

    assert summary.error_type_correct == summary.total - 2
    assert summary.both_correct == summary.total - 2
    assert summary.failures == 1
    assert summary.error_type_confusion == {
        "DATABASE_CONSTRAINT -> INVALID_VALUE": 1,
        "DATABASE_CONNECTION -> None": 1,
    }
    assert summary.severity_confusion == {"CRITICAL -> None": 1, "HIGH -> LOW": 1}
    broken = next(r for r in results if r.scenario_id == "13_connection_refused")
    assert broken.failure == "LLMUnavailableError: Ollama is down"


def test_results_include_parser_output():
    results = run(TruthAnalyzer())
    first = results[0]
    assert first.pipeline == "student_insert"
    assert 'students_pkey' in first.root_error


def test_evaluate_reads_every_sample_log():
    class ConstantAnalyzer:
        model = "fake-model"

        def diagnose(self, parsed, pipeline):
            return LLMDiagnosis(
                error_type="DATABASE_CONSTRAINT", severity="MEDIUM", probable_cause="x", recommendation="y"
            )

    results = evaluate(ConstantAnalyzer(), SAMPLE_LOGS)
    assert [r.scenario_id for r in results] == [s["id"] for s in SCENARIOS]
    assert all(r.failure is None for r in results)


def test_reports():
    results = run(TruthAnalyzer(wrong={"01_duplicate_student_pk"}))
    summary = summarize(results, "fake-model")

    data = json.loads(to_json(results, summary))
    assert data["summary"]["both_correct"] == summary.total - 1
    assert len(data["results"]) == summary.total

    markdown = to_markdown(results, summary)
    assert f"| both correct | {summary.total - 1}/{summary.total} " in markdown
    assert "`DATABASE_CONSTRAINT -> INVALID_VALUE`: 1" in markdown
    assert "### 15_database_missing" in markdown


def test_empty_summary():
    summary = summarize([], "fake-model")
    assert summary.total == 0
    assert summary.mean_seconds == 0.0
    assert "0/0" in to_markdown([], summary)
