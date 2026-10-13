"""Integrity checks for the error scenarios and their captured Hop logs."""

import json
import re
from pathlib import Path

import pytest

from app.schemas import ErrorType, Severity

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LOGS = ROOT / "sample-logs"
PIPELINES = ROOT / "hop-pipelines" / "pipelines"
DATA = ROOT / "hop-pipelines" / "data"

ERROR_TYPES = {e.value for e in ErrorType}
SEVERITIES = {s.value for s in Severity}

SCENARIOS = json.loads((SAMPLE_LOGS / "scenarios.json").read_text())


def by_id(scenario):
    return scenario["id"]


def test_scenario_ids_are_unique_and_ordered():
    ids = [s["id"] for s in SCENARIOS]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=by_id)
def test_expected_labels_are_valid(scenario):
    expected = scenario["expected"]
    assert expected["error_type"] in ERROR_TYPES
    assert expected["severity"] in SEVERITIES
    assert expected["root_cause"].strip()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=by_id)
def test_referenced_pipelines_exist(scenario):
    for pipeline in [scenario["pipeline"], *(step[0] for step in scenario["setup"])]:
        assert (PIPELINES / f"{pipeline}.hpl").is_file()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=by_id)
def test_input_files_exist_unless_missing_file_is_the_error(scenario):
    for arg in scenario["args"]:
        key, _, value = arg.partition("=")
        if key == "INPUT_FILE":
            exists = (DATA / value).is_file()
            assert exists != (scenario["expected"]["error_type"] == "FILE_NOT_FOUND")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=by_id)
def test_captured_log_contains_the_error(scenario):
    log = (SAMPLE_LOGS / f"{scenario['id']}.log").read_text()
    assert scenario["log_marker"] in log


@pytest.mark.parametrize("scenario", SCENARIOS, ids=by_id)
def test_captured_log_has_no_local_paths(scenario):
    log = (SAMPLE_LOGS / f"{scenario['id']}.log").read_text()
    assert not re.search(r"/home/(?!etl\b)\w+", log)


def test_every_error_type_has_a_scenario():
    assert {s["expected"]["error_type"] for s in SCENARIOS} == ERROR_TYPES
