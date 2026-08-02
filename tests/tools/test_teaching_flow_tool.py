"""TeachingFlowTool tests — query/advance/reset/start_task/block over the flow engine."""

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

    def block(self, step, reason, next_action, *a, **kw) -> dict:
        self.state["blocked"] = {"step": step, "reason": reason, "next_action": next_action}
        return self.state

    def next_step_hint(self, *a, **kw) -> str:
        hints = {
            "select_task": "选择下一个任务",
            "show_task": "展示任务给学生",
            "waiting": "等待学生提交标注结果",
            "evaluate": "调用 annotation_check 评测",
            "feedback": "给出反馈并等学生回应",
            "record": "写学习记录",
        }
        return hints.get(self.state.get("current_step"), "继续当前步骤")


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


@pytest.mark.asyncio
async def test_unknown_action_fails(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="advan")
    assert not result.success
    assert "query" in result.content
    assert "start_task" in result.content


@pytest.mark.asyncio
async def test_start_task_sets_task(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="start_task", task_id="task2")
    assert result.success
    assert "task2" in result.content


@pytest.mark.asyncio
async def test_start_task_without_task_id_fails(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="start_task")
    assert not result.success


@pytest.mark.asyncio
async def test_block_reports_reason(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(
        action="block",
        step="evaluate",
        reason="评测接口超时",
        next_action="重试评测",
    )
    assert result.success
    assert "阻塞" in result.content
    assert "评测接口超时" in result.content


@pytest.mark.asyncio
async def test_query_includes_next_step_hint(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(action="query")
    assert result.success
    assert "下一步" in result.content
    assert "annotation_check" in result.content


@pytest.mark.asyncio
async def test_block_skips_next_step_hint(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    result = await TeachingFlowTool().execute(
        action="block",
        step="evaluate",
        reason="评测接口超时",
        next_action="重试评测",
    )
    assert result.success
    assert "阻塞" in result.content
    assert "建议" in result.content
    assert "下一步" not in result.content


@pytest.mark.asyncio
async def test_query_includes_expert(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    fake_engine.state = {"task_id": "task1", "current_step": "evaluate", "steps": {}, "blocked": None, "expert": "grading_expert"}
    result = await TeachingFlowTool().execute(action="query")
    assert result.success
    assert "grading_expert" in result.content
