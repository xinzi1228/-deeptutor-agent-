"""TeachingFlowEngine — deterministic task-level step state machine tests."""

from __future__ import annotations

import json
from pathlib import Path

from deeptutor.services.teaching_flow import (
    FLOW_STEPS,
    TeachingFlowEngine,
    flow_state_path,
)

STEPS = list(FLOW_STEPS)


def _engine(tmp_path, name="flow_state.json", persist=True) -> TeachingFlowEngine:
    path = tmp_path / name if persist else None
    return TeachingFlowEngine(path=path)


def _state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _without_ts(steps: dict) -> dict:
    """Strip volatile wall-clock timestamps to compare deterministic structure."""
    return {name: {k: v for k, v in step.items() if k != "ts"} for name, step in steps.items()}


def test_flow_steps_order():
    assert STEPS == ["select_task", "show_task", "waiting", "evaluate", "feedback", "record"]


def test_start_task_sets_select_and_show(tmp_path):
    e = _engine(tmp_path, persist=False)
    state = e.start_task("task1", state_path=None, base_dir=None)
    assert state["task_id"] == "task1"
    assert state["current_step"] == "show_task"
    assert state["steps"]["select_task"]["status"] == "done"
    assert state["steps"]["show_task"]["status"] == "in_progress"


def test_advance_requires_prerequisite(tmp_path):
    e = _engine(tmp_path, persist=False)
    e.start_task("task1", state_path=None, base_dir=None)
    result = e.advance("evaluate")
    assert result["blocked"] is not None
    assert "waiting" in result["blocked"]["reason"]


def test_advance_flow_in_order(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json", base_dir=None)
    for step in ["show_task", "waiting", "evaluate"]:
        r = e.advance(step)
        assert r["blocked"] is None, step
    state = e.get_state(tmp_path / "flow_state.json")
    assert state["steps"]["evaluate"]["status"] == "done"
    assert state["current_step"] == "feedback"


def test_on_evaluated_auto_advances(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json", base_dir=None)
    for step in ["show_task", "waiting"]:
        e.advance(step, state_path=tmp_path / "flow_state.json")
    r = e.on_evaluated("task1", f1=0.5, state_path=tmp_path / "flow_state.json")
    assert r["steps"]["evaluate"]["status"] == "done"
    assert r["steps"]["evaluate"]["f1"] == 0.5
    assert r["current_step"] == "feedback"


def test_block_records_reason_and_next_action(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json", base_dir=None)
    r = e.block("waiting", reason="学生长时间未提交", next_action="主动询问是否需要帮助",
                state_path=tmp_path / "flow_state.json")
    assert r["steps"]["waiting"]["status"] == "blocked"
    assert r["blocked"] == {"step": "waiting", "reason": "学生长时间未提交", "next_action": "主动询问是否需要帮助"}


def test_reset_clears_state(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json", base_dir=None)
    e.advance("show_task", state_path=tmp_path / "flow_state.json")
    r = e.reset(state_path=tmp_path / "flow_state.json")
    assert r["task_id"] is None
    assert r["current_step"] == "select_task"


def test_next_step_hint(tmp_path):
    e = _engine(tmp_path, persist=False)
    e.start_task("task1", state_path=None, base_dir=None)
    hint = e.next_step_hint()
    assert "show" in hint or "展示" in hint or "next" in hint.lower()


def test_deterministic(tmp_path):
    e = _engine(tmp_path)
    e.start_task("task1", state_path=tmp_path / "flow_state.json", base_dir=None)
    for step in ["show_task", "waiting", "evaluate"]:
        e.advance(step, state_path=tmp_path / "flow_state.json")
    s1 = e.get_state(tmp_path / "flow_state.json")
    e.reset(state_path=tmp_path / "flow_state.json")
    e.start_task("task1", state_path=tmp_path / "flow_state.json", base_dir=None)
    for step in ["show_task", "waiting", "evaluate"]:
        e.advance(step, state_path=tmp_path / "flow_state.json")
    s2 = e.get_state(tmp_path / "flow_state.json")
    assert s1["current_step"] == s2["current_step"]
    assert _without_ts(s1["steps"]) == _without_ts(s2["steps"])
