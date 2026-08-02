"""TeachingFlowEngine — deterministic task-level step state machine tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from deeptutor.services.teaching_flow import (
    FLOW_STEPS,
    TeachingFlowEngine,
    flow_state_path,
)

STEPS = list(FLOW_STEPS)


def _engine(tmp_path, name="flow_state.json", *, in_memory=False) -> TeachingFlowEngine:
    if in_memory:
        return TeachingFlowEngine(in_memory=True)
    return TeachingFlowEngine(path=tmp_path / name)


def _without_ts(steps: dict) -> dict:
    """Strip volatile wall-clock timestamps to compare deterministic structure."""
    return {name: {k: v for k, v in step.items() if k != "ts"} for name, step in steps.items()}


def test_flow_steps_order():
    assert STEPS == ["select_task", "show_task", "waiting", "evaluate", "feedback", "record"]


def test_default_construction_persists_to_workspace_path(tmp_path):
    e = TeachingFlowEngine(base_dir=tmp_path)
    state = e.start_task("task1")
    p = tmp_path / "learning" / "flow_state.json"
    assert p.exists()
    assert json.loads(p.read_text(encoding="utf-8"))["task_id"] == "task1"
    assert state["current_step"] == "show_task"
    assert flow_state_path(base_dir=tmp_path) == p


def test_in_memory_opt_in_does_not_write(tmp_path):
    e = _engine(tmp_path, in_memory=True)
    e.start_task("task1")
    assert not (tmp_path / "flow_state.json").exists()
    assert e.get_state()["task_id"] == "task1"


def test_start_task_sets_select_and_show(tmp_path):
    e = _engine(tmp_path, in_memory=True)
    state = e.start_task("task1")
    assert state["task_id"] == "task1"
    assert state["current_step"] == "show_task"
    assert state["steps"]["select_task"]["status"] == "done"
    assert state["steps"]["show_task"]["status"] == "in_progress"


def test_advance_requires_prerequisite(tmp_path):
    e = _engine(tmp_path, in_memory=True)
    e.start_task("task1")
    result = e.advance("evaluate")
    assert result["blocked"] is not None
    assert "waiting" in result["blocked"]["reason"]


def test_advance_unknown_step_raises(tmp_path):
    e = _engine(tmp_path, in_memory=True)
    e.start_task("task1")
    with pytest.raises(ValueError):
        e.advance("nope")


def test_advance_flow_in_order(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json")
    for step in ["show_task", "waiting", "evaluate"]:
        r = e.advance(step)
        assert r["blocked"] is None, step
    state = e.get_state(tmp_path / "flow_state.json")
    assert state["steps"]["evaluate"]["status"] == "done"
    assert state["current_step"] == "feedback"


def test_on_evaluated_auto_advances(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json")
    for step in ["show_task", "waiting"]:
        e.advance(step, state_path=tmp_path / "flow_state.json")
    r = e.on_evaluated("task1", f1=0.5, state_path=tmp_path / "flow_state.json")
    assert r["steps"]["evaluate"]["status"] == "done"
    assert r["steps"]["evaluate"]["f1"] == 0.5
    assert r["current_step"] == "feedback"


def test_on_evaluated_auto_starts_when_task_id_differs(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json")
    r = e.on_evaluated("task2", f1=0.8, state_path=tmp_path / "flow_state.json")
    assert r["task_id"] == "task2"
    assert r["steps"]["evaluate"]["status"] == "done"
    assert r["steps"]["evaluate"]["f1"] == 0.8
    assert r["current_step"] == "feedback"


def test_block_records_reason_and_next_action(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json")
    r = e.block("waiting", reason="学生长时间未提交", next_action="主动询问是否需要帮助",
                state_path=tmp_path / "flow_state.json")
    assert r["steps"]["waiting"]["status"] == "blocked"
    assert r["blocked"] == {"step": "waiting", "reason": "学生长时间未提交", "next_action": "主动询问是否需要帮助"}


def test_block_unknown_step_raises(tmp_path):
    e = _engine(tmp_path, in_memory=True)
    e.start_task("task1")
    with pytest.raises(ValueError):
        e.block("nope", reason="x", next_action="y")


def test_reset_clears_state(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json")
    e.advance("show_task", state_path=tmp_path / "flow_state.json")
    r = e.reset(state_path=tmp_path / "flow_state.json")
    assert r["task_id"] is None
    assert r["current_step"] == "select_task"


def test_next_step_hint(tmp_path):
    e = _engine(tmp_path, in_memory=True)
    e.start_task("task1")
    hint = e.next_step_hint()
    assert "show" in hint or "展示" in hint or "next" in hint.lower()


def test_corrupt_state_file_falls_back_to_fresh(tmp_path):
    p = tmp_path / "flow_state.json"
    p.write_text("{not valid json", encoding="utf-8")
    e = _engine(tmp_path)
    state = e.get_state()
    assert state["task_id"] is None
    assert state["current_step"] == "select_task"


def test_deterministic(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json")
    for step in ["show_task", "waiting", "evaluate"]:
        e.advance(step, state_path=tmp_path / "flow_state.json")
    s1 = e.get_state(tmp_path / "flow_state.json")
    e.reset(state_path=tmp_path / "flow_state.json")
    e.start_task("task1", state_path=tmp_path / "flow_state.json")
    for step in ["show_task", "waiting", "evaluate"]:
        e.advance(step, state_path=tmp_path / "flow_state.json")
    s2 = e.get_state(tmp_path / "flow_state.json")
    assert s1["current_step"] == s2["current_step"]
    assert _without_ts(s1["steps"]) == _without_ts(s2["steps"])


def test_expert_route_mapping():
    from deeptutor.services.teaching_flow import EXPERT_ROUTE, TeachingFlowEngine

    assert EXPERT_ROUTE["select_task"] == "task_guide"
    assert EXPERT_ROUTE["evaluate"] == "grading_expert"
    assert EXPERT_ROUTE["onboarding"] == "learning_planner"

    e = TeachingFlowEngine(path=None, in_memory=True)
    assert e.expert_route("feedback") == "grading_expert"
    assert e.expert_route("unknown_stage") == "task_guide"  # default fallback


def test_get_state_includes_expert():
    from deeptutor.services.teaching_flow import TeachingFlowEngine

    e = TeachingFlowEngine(path=None, in_memory=True)
    e.start_task("task1")
    state = e.get_state()
    assert "expert" in state
    assert state["expert"] == "task_guide"  # current_step is show_task after start_task
