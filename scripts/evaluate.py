"""Run every error scenario through the real LLM and compare it with the ground truth.

Usage: .venv/bin/python scripts/evaluate.py
Needs Ollama running (OLLAMA_HOST / OLLAMA_MODEL, defaults in app/llm.py). Does not use the
database: results are written to evaluation/results.json and evaluation/REPORT.md.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.evaluation import evaluate, summarize, to_json, to_markdown  # noqa: E402
from app.llm import LLMAnalyzer  # noqa: E402


def main() -> int:
    analyzer = LLMAnalyzer.from_env()
    results = evaluate(analyzer, ROOT / "sample-logs")
    summary = summarize(results, analyzer.model)

    out_dir = ROOT / "evaluation"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "results.json").write_text(to_json(results, summary))
    (out_dir / "REPORT.md").write_text(to_markdown(results, summary))

    for r in results:
        status = "OK  " if r.error_type_ok and r.severity_ok else "MISS"
        print(f"{status} {r.scenario_id}: {r.error_type}/{r.severity} ({r.seconds}s){' ' + r.failure if r.failure else ''}")
    print(
        f"error_type {summary.error_type_correct}/{summary.total}, "
        f"severity {summary.severity_correct}/{summary.total}, "
        f"both {summary.both_correct}/{summary.total}, failures {summary.failures}"
    )
    return 1 if summary.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
