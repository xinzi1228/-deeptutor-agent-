"""TeachingFlowTool tests — query/advance/reset over the flow engine."""

from __future__ import annotations

import pytest


class _FakeEngine:
    """Minimal sync stand-in for TeachingFlowEngine."""

    def __init__(self) -> None:
        self.state = {"task_id": "task1", "current_step": "evaluate", "steps": {}, "blocked": None}

    def get_state(self, *a, **kw) -> dict:
        return self.state

    def advance(self, step, *a, **kw) -> dict:
        self.state["current_step"] = step
        return self.state

    def reset(self, *a, **kw) -> dict:
        self.state = {"task_id": None, "current_step": "select_task", "steps": {}, "blocked": None}
        return self.state

    def start_task(self, task_id, *a, **kw) -> dict:
        self.state = {"task_id": task_id, "current_step": "show_task", "steps": {}, "blocked": None}
        return self.state


@pytest.fixture
def fake_engine(monkeypatch):
    engine = _FakeEngine()
    monkeypatch.setattr("deeptutor.tools.teaching_flow_tool._build_engine", lambda: engine)
    return engine


@pytest.mark.asyncio
async def test_query_returns_current_step(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="query")
    assert result.success
    assert "evaluate" in result.content
    assert "task1" in result.content


@pytest.mark.asyncio
async def test_query_no_state(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    fake_engine.state = {"task_id": None, "current_step": "select_task", "steps": {}, "blocked": None}
    result = await TeachingFlowTool().execute(action="query")
    assert result.success
    assert "select_task" in result.content


@pytest.mark.asyncio
async def test_advance_marks_step(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="advance", step="feedback")
    assert result.success
    assert "feedback" in result.content


@pytest.mark.asyncio
async def test_advance_without_step_fails(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="advance")
    assert not result.success


@pytest.mark.asyncio
async def test_reset_clears(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="reset")
    assert result.success
    assert "select_task" in result.content


@pytest.mark.asyncio
async def test_advance_unknown_step_returns_failure(fake_engine):
    """Engine ValueError on unknown step degrades to a failed ToolResult."""
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    def _raise(step, *a, **kw) -> dict:
        raise ValueError(f"未知步骤: {step}")

    fake_engine.advance = _raise
    result = await TeachingFlowTool().execute(action="advance", step="nope")
    assert not result.success
    assert "未知步骤" in result.content
