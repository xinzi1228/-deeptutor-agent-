"""trace-log endpoint — teaching-turn aggregation (records + decisions)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_trace_log_returns_records_sorted_desc():
    from deeptutor.api.routers.profile import trace_log

    result = await trace_log(limit=30)
    assert "traces" in result
    traces = result["traces"]
    ts = [t["timestamp"] for t in traces]
    assert ts == sorted(ts, reverse=True)


@pytest.mark.asyncio
async def test_trace_log_annotation_exercise_has_f1_and_readiness():
    from deeptutor.api.routers.profile import trace_log

    result = await trace_log(limit=30)
    exercises = [t for t in result["traces"] if t["type"] == "annotation_exercise"]
    assert exercises, "expected at least one annotation_exercise in demo data"
    for ex in exercises[:3]:
        assert "f1" in ex
        assert "readiness" in ex
        assert "intervention" in ex
        assert "decision" in ex


@pytest.mark.asyncio
async def test_trace_log_limit():
    from deeptutor.api.routers.profile import trace_log

    result = await trace_log(limit=1)
    assert len(result["traces"]) <= 1
