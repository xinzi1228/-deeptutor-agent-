from __future__ import annotations

import pytest

from deeptutor.api.routers import performance_metrics
from deeptutor.services.performance_metrics import PerformanceMetricStore


@pytest.mark.asyncio
async def test_router_accepts_metric_and_returns_aggregate(monkeypatch, tmp_path) -> None:
    store = PerformanceMetricStore(tmp_path)
    monkeypatch.setattr(performance_metrics, "_private_store", lambda write=False: store)

    accepted = await performance_metrics.create_event(
        performance_metrics.PerformanceMetricInput(
            name="progress_core_visible",
            route="/progress",
            duration_ms=1200,
        )
    )
    summary = await performance_metrics.get_summary()

    assert accepted == {"accepted": True}
    assert summary["total"] == 1
    assert summary["metrics"]["progress_core_visible"]["p50_ms"] == 1200


@pytest.mark.asyncio
async def test_batch_is_bounded() -> None:
    body = performance_metrics.PerformanceMetricBatch(
        events=[
            performance_metrics.PerformanceMetricInput(
                name="route_visible", route="/home", duration_ms=1
            )
            for _ in range(51)
        ]
    )
    with pytest.raises(Exception, match="50"):
        await performance_metrics.create_batch(body)
