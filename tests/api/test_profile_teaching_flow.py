"""teaching-flow endpoint — current 6-step protocol state (read-only)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_teaching_flow_no_file_returns_empty():
    from deeptutor.api.routers.profile import teaching_flow_state

    result = await teaching_flow_state()
    assert "has_flow" in result
    assert result["has_flow"] is False
    assert "steps" in result
    assert "current_step" in result


@pytest.mark.asyncio
async def test_teaching_flow_with_state(tmp_path, monkeypatch):
    from deeptutor.api.routers.profile import teaching_flow_state
    from deeptutor.services.teaching_flow import TeachingFlowEngine

    state_path = tmp_path / "flow_state.json"
    engine = TeachingFlowEngine(path=state_path)
    engine.start_task("task1")

    # The endpoint does `from deeptutor.services.teaching_flow import TeachingFlowEngine`
    # inside the function — monkeypatch the module attribute so it returns our temp engine.
    monkeypatch.setattr(
        "deeptutor.services.teaching_flow.TeachingFlowEngine",
        lambda: TeachingFlowEngine(path=state_path),
    )

    result = await teaching_flow_state()
    assert result["has_flow"] is True
    assert result["task_id"] == "task1"
    assert result["current_step"] == "show_task"
    assert "expert" in result
