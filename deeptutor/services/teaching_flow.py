"""TeachingFlowEngine — deterministic task-level step state machine.

Tracks the flow-practice 6-step pipeline (select_task -> show_task -> waiting
-> evaluate -> feedback -> record) with step gates (prerequisites must be done)
and blocked reports (reason + next_action). Pure functions over a JSON state
file — no LLM, so state transitions are testable, reproducible, and auditable.

Borrowed shape from chinese-thesis-workbench's Phase+Status model: each step
has a status (pending/in_progress/blocked/needs_review/done) and blocking is
explicit with a next action for the coach.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

FLOW_STEPS = ["select_task", "show_task", "waiting", "evaluate", "feedback", "record"]

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_BLOCKED = "blocked"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_DONE = "done"

# step -> prerequisites (steps that must be done before this can start)
PREREQUISITES: dict[str, list[str]] = {
    "select_task": [],
    "show_task": ["select_task"],
    "waiting": ["show_task"],
    "evaluate": ["waiting"],
    "feedback": ["evaluate"],
    "record": ["feedback"],
}

# stage -> expert role id (multi-expert routing, see references/experts/)
EXPERT_ROUTE: dict[str, str] = {
    "onboarding": "learning_planner",
    "theory": "learning_planner",
    "select_task": "task_guide",
    "show_task": "task_guide",
    "waiting": "task_guide",
    "evaluate": "grading_expert",
    "feedback": "grading_expert",
    "record": "report_analyst",
    "struggle": "struggle_detective",
    "report": "report_analyst",
    "session": "session_steward",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_path(base_dir: Path | None) -> Path:
    root = base_dir or Path(__file__).resolve().parents[2] / "data" / "user" / "workspace"
    return root / "learning" / "flow_state.json"


def flow_state_path(base_dir: Path | None = None) -> Path:
    return _default_path(base_dir)


class TeachingFlowEngine:
    """Deterministic task-level flow state machine over flow_state.json."""

    def __init__(self, path: Path | None = None, *, base_dir: Path | None = None, in_memory: bool = False) -> None:
        self._path = path or _default_path(base_dir)
        self._in_memory: dict | None = self._fresh_state() if in_memory else None

    # ------------------------------------------------------------------ state

    def _resolve(self, state_path: Path | None) -> Path:
        return state_path or self._path

    def get_state(self, state_path: Path | None = None) -> dict:
        if self._in_memory is not None:
            return self._in_memory
        p = self._resolve(state_path)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return self._fresh_state()
        return self._fresh_state()

    def _fresh_state(self) -> dict:
        return {
            "task_id": None,
            "current_step": "select_task",
            "steps": {s: {"status": STATUS_PENDING, "ts": None} for s in FLOW_STEPS},
            "blocked": None,
            "expert": self.expert_route("select_task"),
            "updated_at": None,
        }

    def _with_expert(self, state: dict) -> dict:
        step = state.get("current_step") or "select_task"
        state["expert"] = self.expert_route(step)
        return state

    def _write(self, state: dict, state_path: Path | None = None) -> dict:
        state["updated_at"] = _now()
        if self._in_memory is not None:
            self._in_memory = state
            return state
        p = self._resolve(state_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def expert_route(self, stage: str) -> str:
        """Map a teaching stage to its expert role id (default: task_guide)."""
        return EXPERT_ROUTE.get(stage, "task_guide")

    # -------------------------------------------------------------- actions

    def start_task(self, task_id: str, *, state_path: Path | None = None) -> dict:
        state = self._fresh_state()
        state["task_id"] = task_id
        state["current_step"] = "show_task"
        state["steps"]["select_task"] = {"status": STATUS_DONE, "ts": _now()}
        state["steps"]["show_task"] = {"status": STATUS_IN_PROGRESS, "ts": _now()}
        return self._write(self._with_expert(state), state_path)

    def advance(self, step: str, *, state_path: Path | None = None) -> dict:
        if step not in FLOW_STEPS:
            raise ValueError(f"未知步骤: {step} (可选: {', '.join(FLOW_STEPS)})")
        state = self.get_state(state_path)
        for pre in PREREQUISITES[step]:
            if state["steps"].get(pre, {}).get("status") != STATUS_DONE:
                state["blocked"] = {
                    "step": step,
                    "reason": f"前置步骤 '{pre}' 未完成，不能推进到 '{step}'",
                    "next_action": f"先完成 {pre}（调对应工具或等待学生操作）",
                }
                return self._write(self._with_expert(state), state_path)
        state["steps"][step]["status"] = STATUS_DONE
        state["steps"][step]["ts"] = state["steps"][step].get("ts") or _now()
        idx = FLOW_STEPS.index(step)
        if idx + 1 < len(FLOW_STEPS):
            state["current_step"] = FLOW_STEPS[idx + 1]
            state["steps"][FLOW_STEPS[idx + 1]]["status"] = STATUS_IN_PROGRESS
        else:
            state["current_step"] = None
        state["blocked"] = None
        return self._write(self._with_expert(state), state_path)

    def on_evaluated(self, task_id: str, f1: float, *, readiness: str | None = None, state_path: Path | None = None) -> dict:
        state = self.get_state(state_path)
        if state.get("task_id") != task_id:
            state = self.start_task(task_id, state_path=state_path)
        state["steps"]["evaluate"]["status"] = STATUS_DONE
        state["steps"]["evaluate"]["ts"] = _now()
        state["steps"]["evaluate"]["f1"] = f1
        if readiness is not None:
            state["steps"]["evaluate"]["readiness"] = readiness
        state["steps"]["feedback"]["status"] = STATUS_IN_PROGRESS
        state["current_step"] = "feedback"
        state["blocked"] = None
        return self._write(self._with_expert(state), state_path)

    def block(self, step: str, reason: str, next_action: str, *, state_path: Path | None = None) -> dict:
        if step not in FLOW_STEPS:
            raise ValueError(f"未知步骤: {step} (可选: {', '.join(FLOW_STEPS)})")
        state = self.get_state(state_path)
        state["steps"][step]["status"] = STATUS_BLOCKED
        state["blocked"] = {"step": step, "reason": reason, "next_action": next_action}
        return self._write(self._with_expert(state), state_path)

    def reset(self, *, state_path: Path | None = None) -> dict:
        state = self._fresh_state()
        return self._write(self._with_expert(state), state_path)

    # ------------------------------------------------------------- guidance

    def next_step_hint(self, state_path: Path | None = None) -> str:
        state = self.get_state(state_path)
        step = state.get("current_step")
        if state.get("blocked"):
            b = state["blocked"]
            return f"当前阻塞在 {b['step']}: {b['reason']} → 建议: {b['next_action']}"
        hints = {
            "select_task": "选择下一个任务 (start_task / get_annotation_task)",
            "show_task": "展示任务给学生 (show_task)",
            "waiting": "等待学生提交标注结果",
            "evaluate": "调用 annotation_check 评测 (on_evaluated 自动推进)",
            "feedback": "给出反馈并等学生回应",
            "record": "写学习记录 (write_learning_record)",
        }
        return hints.get(step, "继续当前步骤")


__all__ = [
    "FLOW_STEPS",
    "EXPERT_ROUTE",
    "STATUS_PENDING",
    "STATUS_IN_PROGRESS",
    "STATUS_BLOCKED",
    "STATUS_NEEDS_REVIEW",
    "STATUS_DONE",
    "TeachingFlowEngine",
    "flow_state_path",
]
