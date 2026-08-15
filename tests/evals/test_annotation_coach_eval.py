from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.run_annotation_coach_eval import load_suite, validate_case

ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "tests" / "evals" / "annotation_coach_cases.json"


def _cases() -> list[dict]:
    return load_suite(CASES_PATH)["cases"]


def test_eval_suite_has_approved_size_and_scene_distribution() -> None:
    cases = _cases()
    assert len(cases) == 40
    assert Counter(case["scene"] for case in cases) == {
        "交通道路": 14,
        "工厂质检": 9,
        "校园监控": 8,
        "商超货架": 9,
    }
    assert len({case["id"] for case in cases}) == 40


def test_eval_suite_covers_all_intents_and_failure_boundaries() -> None:
    cases = _cases()
    assert {case["expected_intent"] for case in cases} == {
        "theory",
        "clarification",
        "annotation_help",
        "submission_explanation",
        "correction",
        "report",
        "normative",
        "diagnosis",
    }
    flags = {flag for case in cases for flag in case["flags"]}
    assert {
        "trusted_chart",
        "no_reliable_source",
        "cross_profile",
        "teacher_readonly",
        "simulate_timeout",
        "simulate_cancel",
        "professional_mode",
    } <= flags


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_eval_case_matches_deterministic_policy(case: dict) -> None:
    assert validate_case(case) == []


def test_offline_runner_never_calls_a_model() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_annotation_coach_eval.py"), "--offline-contracts"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["valid"] is True
    assert summary["case_count"] == 40
    assert summary["model_calls"] == 0
