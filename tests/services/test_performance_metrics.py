from __future__ import annotations

import json

from pydantic import ValidationError
import pytest

from deeptutor.services.performance_metrics import (
    BUDGETS_MS,
    PerformanceMetricInput,
    PerformanceMetricStore,
    check_budgets,
)


def test_metric_schema_rejects_private_or_arbitrary_payloads() -> None:
    with pytest.raises(ValidationError):
        PerformanceMetricInput.model_validate(
            {
                "name": "route_visible",
                "route": "/home",
                "duration_ms": 420,
                "conversation": "不应记录的正文",
            }
        )


def test_store_writes_only_whitelisted_fields_and_summarizes(tmp_path) -> None:
    store = PerformanceMetricStore(tmp_path)
    for duration in (100, 200, 300, 400, 500):
        store.append(
            PerformanceMetricInput(
                name="route_visible",
                route="/progress",
                duration_ms=duration,
            )
        )

    raw = [json.loads(line) for line in store.path.read_text(encoding="utf-8").splitlines()]
    assert len(raw) == 5
    assert set(raw[0]) == {
        "schema_version",
        "timestamp",
        "name",
        "route",
        "duration_ms",
        "outcome",
        "stage",
        "tool_calls",
        "error_type",
        "build_version",
    }
    assert not any("profile" in key or "user" in key for key in raw[0])

    summary = store.summary()
    route = summary["metrics"]["route_visible"]
    assert route["count"] == 5
    assert route["p50_ms"] == 300
    assert route["p95_ms"] == 500


def test_store_keeps_profile_roots_isolated(tmp_path) -> None:
    first = PerformanceMetricStore(tmp_path / "first")
    second = PerformanceMetricStore(tmp_path / "second")
    first.append(
        PerformanceMetricInput(name="chat_first_token", route="/home", duration_ms=900)
    )

    assert first.summary()["total"] == 1
    assert second.summary()["total"] == 0


# ── Budget validation (competition readiness §5) ──────────────────────────


def test_budgets_pass_when_under_limits(tmp_path) -> None:
    store = PerformanceMetricStore(tmp_path)
    store.append(
        PerformanceMetricInput(name="cold_start_interactive", route="/home", duration_ms=2000)
    )
    store.append(PerformanceMetricInput(name="route_visible", route="/home", duration_ms=500))
    store.append(
        PerformanceMetricInput(name="progress_core_visible", route="/progress", duration_ms=1500)
    )
    store.append(PerformanceMetricInput(name="chat_status_visible", route="/home", duration_ms=150))
    store.append(PerformanceMetricInput(name="chat_first_token", route="/home", duration_ms=3000))

    result = check_budgets(tmp_path)
    assert result["all_measured"] is True
    assert result["budgets_met"] is True
    assert all(
        result["metrics"][name]["status"] == "pass" for name in BUDGETS_MS
    )


def test_budget_over_limit_is_fail_not_pass(tmp_path) -> None:
    store = PerformanceMetricStore(tmp_path)
    store.append(
        PerformanceMetricInput(name="chat_status_visible", route="/home", duration_ms=600)
    )
    result = check_budgets(tmp_path)
    assert result["metrics"]["chat_status_visible"]["status"] == "over_budget"


def test_unmeasured_budget_is_not_measured_not_pass(tmp_path) -> None:
    result = check_budgets(tmp_path)
    assert result["all_measured"] is False
    assert result["budgets_met"] is False
    assert result["metrics"]["cold_start_interactive"]["status"] == "not_measured"


def test_budgets_cover_all_five_gates() -> None:
    assert set(BUDGETS_MS) == {
        "cold_start_interactive",
        "route_visible",
        "progress_core_visible",
        "chat_status_visible",
        "chat_first_token",
    }
    assert BUDGETS_MS["cold_start_interactive"] <= 3000
    assert BUDGETS_MS["route_visible"] <= 1000
    assert BUDGETS_MS["progress_core_visible"] <= 2000
    assert BUDGETS_MS["chat_status_visible"] <= 300
    assert BUDGETS_MS["chat_first_token"] <= 5000
