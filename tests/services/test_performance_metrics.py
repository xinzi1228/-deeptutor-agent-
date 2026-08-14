from __future__ import annotations

import json

from pydantic import ValidationError
import pytest

from deeptutor.services.performance_metrics import (
    PerformanceMetricInput,
    PerformanceMetricStore,
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
