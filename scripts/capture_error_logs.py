"""Reproduce every error scenario in sample-logs/scenarios.json and save its Hop log.

For each scenario: reset the database, run the setup pipelines, run the failing pipeline,
check that it failed with the expected message and store the log as sample-logs/<id>.log.
Absolute paths of this machine are replaced so the logs can be published.

Usage: .venv/bin/python scripts/capture_error_logs.py [scenario_id ...]
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LOGS = ROOT / "sample-logs"
SCENARIOS_FILE = SAMPLE_LOGS / "scenarios.json"
PUBLIC_ROOT = "/opt/etl-error-analyzer"


def run(cmd: list[str], log_file: Path | None = None) -> int:
    env = os.environ.copy()
    if log_file is not None:
        env["RUN_LOG_FILE"] = str(log_file)
    return subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL).returncode


def sanitize(text: str) -> str:
    return text.replace(str(ROOT), PUBLIC_ROOT).replace(str(Path.home()), "/home/etl")


def capture(scenario: dict) -> str | None:
    """Return None on success, or a short reason why the scenario did not reproduce."""
    if run(["scripts/init_db.sh"]) != 0:
        return "init_db.sh failed"
    for step in scenario["setup"]:
        if run(["scripts/run_pipeline.sh", *step]) != 0:
            return f"setup pipeline {step[0]} failed"

    log_file = SAMPLE_LOGS / f"{scenario['id']}.log"
    status = run(["scripts/run_pipeline.sh", scenario["pipeline"], *scenario["args"]], log_file)
    log_file.write_text(sanitize(log_file.read_text()))

    if status == 0:
        return "pipeline succeeded but an error was expected"
    if scenario["log_marker"] not in log_file.read_text():
        return f"log does not contain marker: {scenario['log_marker']}"
    return None


def main() -> int:
    scenarios = json.loads(SCENARIOS_FILE.read_text())
    selected = set(sys.argv[1:])
    failures = 0
    for scenario in scenarios:
        if selected and scenario["id"] not in selected:
            continue
        problem = capture(scenario)
        print(f"{'OK  ' if problem is None else 'FAIL'} {scenario['id']}" + (f": {problem}" if problem else ""))
        failures += problem is not None

    # Leave the database in its seeded state for the next user of it.
    run(["scripts/init_db.sh"])
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
