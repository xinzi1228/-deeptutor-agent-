# 任务引导引擎实施计划（Teaching Flow Engine）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把任务引导从"协议"升级为"引擎"——任务级 6 步状态机（TeachingFlowEngine）+ annotation_check 像素级校验（贴边/重叠/紧致度）+ 题型扩展（判断/规范/错误案例）。

**Architecture:** `TeachingFlowEngine` 纯函数服务（读/写 `flow_state.json`，gate 前置条件 + blocked 报告，借鉴 chinese-thesis-workbench Phase+Status）→ `teaching_flow` 工具（Coach 查询/推进/重置，always-on 第 15 个）→ `annotation_check` 增强（启发式像素校验 + 自动推进 + 新 task_type 评测）→ `grading.py` 题型扩展 + `task_bank` 新任务。

**Tech Stack:** Python 3.13, pytest + pytest-asyncio。确定性引擎（无 LLM in core，纯函数 + JSON 持久化）。

**Spec:** `docs/specs/teaching-flow-engine-design.md`（已提交 `c1350bf1`）

---

### Task 1: `TeachingFlowEngine` 服务——任务级 6 步状态机

**Files:**
- Create: `deeptutor/services/teaching_flow.py`
- Test: `tests/services/test_teaching_flow.py`

- [ ] **Step 1: Write the failing test**

Create `tests/services/test_teaching_flow.py`:

```python
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


def _engine(tmp_path, name="flow_state.json") -> TeachingFlowEngine:
    return TeachingFlowEngine(path=tmp_path / name)


def _state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_flow_steps_order():
    assert STEPS == ["select_task", "show_task", "waiting", "evaluate", "feedback", "record"]


def test_start_task_sets_select_and_show():
    e = _engine(Path("_tmp"))
    state = e.start_task("task1", state_path=None, base_dir=None)
    assert state["task_id"] == "task1"
    assert state["current_step"] == "show_task"
    assert state["steps"]["select_task"]["status"] == "done"
    assert state["steps"]["show_task"]["status"] == "in_progress"


def test_advance_requires_prerequisite():
    # evaluate before waiting done -> gate blocks
    e = _engine(Path("_tmp"))
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


def test_next_step_hint():
    e = _engine(Path("_tmp"))
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
    assert s1["steps"] == s2["steps"]
```

NOTE: The test uses a `path` parameter pattern. Design the `TeachingFlowEngine` API so the state file path is injectable (a `state_path` kwarg on methods, or an engine constructed with a base dir + default filename). The tests above assume methods accept `state_path` (and `base_dir` for default resolution). Implement to match — the exact signature is yours to finalize, but the TESTS define the observable behavior. If a signature feels awkward, adjust BOTH the test and impl consistently (the assertions above are the contract).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_teaching_flow.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/services/teaching_flow.py`:

```python
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

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

DEFAULT_STATE_PATH = None  # resolved lazily from workspace when not provided


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_path(base_dir: Path | None) -> Path:
    root = base_dir or Path(__file__).resolve().parents[2] / "data" / "user" / "workspace"
    return root / "learning" / "flow_state.json"


def flow_state_path(base_dir: Path | None = None) -> Path:
    return _default_path(base_dir)


class TeachingFlowEngine:
    """Deterministic task-level flow state machine over flow_state.json."""

    def __init__(self, path: Path | None = None, base_dir: Path | None = None) -> None:
        self._path = path or _default_path(base_dir)

    # ------------------------------------------------------------------ state

    def _resolve(self, state_path: Path | None) -> Path:
        return state_path or self._path

    def get_state(self, state_path: Path | None = None) -> dict:
        p = self._resolve(state_path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return self._fresh_state()

    def _fresh_state(self) -> dict:
        return {
            "task_id": None,
            "current_step": "select_task",
            "steps": {s: {"status": STATUS_PENDING, "ts": None} for s in FLOW_STEPS},
            "blocked": None,
            "updated_at": None,
        }

    def _write(self, state: dict, state_path: Path | None = None) -> dict:
        state["updated_at"] = _now()
        p = self._resolve(state_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    # -------------------------------------------------------------- actions

    def start_task(self, task_id: str, *, state_path: Path | None = None, base_dir: Path | None = None) -> dict:
        state = self._fresh_state()
        state["task_id"] = task_id
        state["current_step"] = "show_task"
        state["steps"]["select_task"] = {"status": STATUS_DONE, "ts": _now()}
        state["steps"]["show_task"] = {"status": STATUS_IN_PROGRESS, "ts": _now()}
        return self._write(state, state_path)

    def advance(self, step: str, *, state_path: Path | None = None, base_dir: Path | None = None) -> dict:
        state = self.get_state(state_path)
        if step not in FLOW_STEPS:
            return self._write(state, state_path)
        # gate: prerequisites must be done
        for pre in PREREQUISITES[step]:
            if state["steps"].get(pre, {}).get("status") != STATUS_DONE:
                state["blocked"] = {
                    "step": step,
                    "reason": f"前置步骤 '{pre}' 未完成，不能推进到 '{step}'",
                    "next_action": f"先完成 {pre}（调对应工具或等待学生操作）",
                }
                return self._write(state, state_path)
        state["steps"][step]["status"] = STATUS_DONE
        state["steps"][step]["ts"] = state["steps"][step].get("ts") or _now()
        idx = FLOW_STEPS.index(step)
        if idx + 1 < len(FLOW_STEPS):
            state["current_step"] = FLOW_STEPS[idx + 1]
            state["steps"][FLOW_STEPS[idx + 1]]["status"] = STATUS_IN_PROGRESS
        else:
            state["current_step"] = None
        state["blocked"] = None
        return self._write(state, state_path)

    def on_evaluated(self, task_id: str, f1: float, *, state_path: Path | None = None, base_dir: Path | None = None) -> dict:
        state = self.get_state(state_path)
        if state.get("task_id") != task_id:
            state = self.start_task(task_id, state_path=state_path)
        state["steps"]["evaluate"]["status"] = STATUS_DONE
        state["steps"]["evaluate"]["ts"] = _now()
        state["steps"]["evaluate"]["f1"] = f1
        state["steps"]["feedback"]["status"] = STATUS_IN_PROGRESS
        state["current_step"] = "feedback"
        state["blocked"] = None
        return self._write(state, state_path)

    def block(self, step: str, reason: str, next_action: str, *, state_path: Path | None = None, base_dir: Path | None = None) -> dict:
        state = self.get_state(state_path)
        if step in state["steps"]:
            state["steps"][step]["status"] = STATUS_BLOCKED
        state["blocked"] = {"step": step, "reason": reason, "next_action": next_action}
        return self._write(state, state_path)

    def reset(self, *, state_path: Path | None = None, base_dir: Path | None = None) -> dict:
        state = self._fresh_state()
        return self._write(state, state_path)

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
    "STATUS_PENDING",
    "STATUS_IN_PROGRESS",
    "STATUS_BLOCKED",
    "STATUS_NEEDS_REVIEW",
    "STATUS_DONE",
    "TeachingFlowEngine",
    "flow_state_path",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_teaching_flow.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (all tests). NOTE: the test file has some awkward `state_path=None` calls in the "no persistence" cases (`_engine(Path("_tmp"))` + `start_task("task1", state_path=None)`). The `_resolve` falls back to `self._path` which is `Path("_tmp")/flow_state.json` — this WRITES a file relative to CWD during tests. Fix the test to use tmp_path consistently (or set `path=None` + use in-memory). Adjust the test to avoid polluting the repo CWD (e.g. always use tmp_path, or make the engine accept `path=None` meaning "don't persist"). Choose the cleanest approach that keeps the assertions intact — do NOT weaken the gate/determinism assertions.

- [ ] **Step 5: Ruff**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; python -m ruff check deeptutor/services/teaching_flow.py tests/services/test_teaching_flow.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add deeptutor/services/teaching_flow.py tests/services/test_teaching_flow.py
git commit -m "feat: TeachingFlowEngine 任务级 6 步状态机 (gate+阻塞报告+flow_state.json)"
```

---

### Task 2: `teaching_flow` 工具 + always-on 注册

**Files:**
- Create: `deeptutor/tools/teaching_flow_tool.py`
- Test: `tests/tools/test_teaching_flow_tool.py` + `tests/tools/test_teaching_flow_registration.py`
- Modify: `deeptutor/tools/builtin/__init__.py` + `deeptutor/agents/_shared/tool_composition.py`

- [ ] **Step 1: Write the failing test**

Create `tests/tools/test_teaching_flow_tool.py`:

```python
"""TeachingFlowTool tests — query/advance/reset over the flow engine."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_teaching_flow_query_no_state(monkeypatch) -> None:
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    async def _fake_start(task_id, **kw):
        return {"task_id": task_id, "current_step": "show_task"}

    class _FakeEngine:
        def __init__(self, *a, **kw):
            pass

        def get_state(self, *a, **kw):
            return {"task_id": None, "current_step": "select_task", "steps": {}, "blocked": None}

        def start_task(self, *a, **kw):
            return _sync_or_raise(_fake_start(*a, **kw))

    monkeypatch.setattr("deeptutor.tools.teaching_flow_tool._build_engine", lambda *a, **kw: _FakeEngine())

    tool = TeachingFlowTool()
    result = await tool.execute(action="query")
    assert result.success
    assert "select_task" in result.content


def _sync_or_raise(coro):
    return coro
```

NOTE: The tool's `execute` needs `action` handling. The fake engine's `start_task` in the test is awkward — simplify: make `_FakeEngine` fully sync (get_state/start_task/advance/reset/block all plain methods returning dicts). Rewrite the test with a clean sync `_FakeEngine`. The REQUIRED test cases:
1. `action=query` with no state → returns current step (select_task), success
2. `action=advance` with a step → calls engine.advance, returns updated state in content
3. `action=reset` → calls engine.reset
4. `action=query` with existing state → returns task_id + current_step

Write a clean version of these 4 tests with a sync fake engine monkeypatched at `deeptutor.tools.teaching_flow_tool._build_engine`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_teaching_flow_tool.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/tools/teaching_flow_tool.py`:

```python
"""TeachingFlowTool — coach tool to query/advance/reset the teaching flow engine."""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints


class TeachingFlowTool(BaseTool):
    """Query / advance / reset the task-level teaching flow state machine."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="teaching_flow",
            description=(
                "Query or advance the current teaching-flow step for the active task "
                "(select_task -> show_task -> waiting -> evaluate -> feedback -> record). "
                "Call to know where you are in the pipeline, to advance a step after it "
                "completes, or to reset for a new task. Returns the current step + next "
                "action hint so you can stay on protocol."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="'query' (default) returns current step; 'advance' marks a step done; 'reset' clears state.",
                    required=False,
                    enum=["query", "advance", "reset"],
                    default="query",
                ),
                ToolParameter(
                    name="step",
                    type="string",
                    description="Step to advance when action=advance (select_task/show_task/waiting/evaluate/feedback/record).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.teaching_flow import TeachingFlowEngine

        action = kwargs.get("action", "query")
        step = kwargs.get("step")
        engine = _build_engine()

        if action == "advance":
            if not step:
                return ToolResult(content="action=advance 需要指定 step。", success=False)
            state = engine.advance(step)
            return ToolResult(content=_format_state(state), metadata={"state": state})
        if action == "reset":
            state = engine.reset()
            return ToolResult(content=_format_state(state), metadata={"state": state})

        state = engine.get_state()
        return ToolResult(content=_format_state(state), metadata={"state": state})

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


# ------------------------------------------------------------ dependencies

def _build_engine() -> Any:
    from deeptutor.services.teaching_flow import TeachingFlowEngine

    return TeachingFlowEngine()


def _format_state(state: dict) -> str:
    task = state.get("task_id") or "（未开始）"
    step = state.get("current_step") or "（完成）"
    blocked = state.get("blocked")
    lines = [f"## 教学流程状态\n", f"当前任务: {task}", f"当前步骤: {step}"]
    if blocked:
        lines.append(f"阻塞: {blocked.get('reason', '')}")
        lines.append(f"建议: {blocked.get('next_action', '')}")
    return "\n".join(lines)


__all__ = ["TeachingFlowTool"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_teaching_flow_tool.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Register the tool**

Create `tests/tools/test_teaching_flow_registration.py` (mirror `test_struggle_tool_registration.py`):

```python
"""teaching_flow registration tests."""

from __future__ import annotations


def test_teaching_flow_in_builtin() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES

    assert "teaching_flow" in BUILTIN_TOOL_NAMES


def test_teaching_flow_in_configurable() -> None:
    from deeptutor.tools.builtin import CONFIGURABLE_BUILTIN_TOOL_NAMES

    assert "teaching_flow" in CONFIGURABLE_BUILTIN_TOOL_NAMES


def test_teaching_flow_in_always_on() -> None:
    import inspect

    import deeptutor.agents._shared.tool_composition as tc

    src = inspect.getsource(tc)
    assert '"teaching_flow"' in src
```

Edit `deeptutor/tools/builtin/__init__.py`:
1. Add import: `from deeptutor.tools.teaching_flow_tool import TeachingFlowTool`
2. Add `TeachingFlowTool,` to `BUILTIN_TOOL_TYPES` (near `StruggleDetectTool,`)
3. Add `"TeachingFlowTool",` to `__all__`
4. Add `"teaching_flow",` to `CONFIGURABLE_BUILTIN_TOOL_NAMES`

Edit `deeptutor/agents/_shared/tool_composition.py`:
5. Add `"teaching_flow",` to the always_on tuple (near `struggle_detect`)

- [ ] **Step 6: Run tests to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_teaching_flow_tool.py tests/tools/test_teaching_flow_registration.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

Import smoke: `python -c "import deeptutor.tools.builtin as b; print('teaching_flow' in b.BUILTIN_TOOL_NAMES)"` → `True`

- [ ] **Step 7: Commit**

```bash
git add deeptutor/tools/teaching_flow_tool.py deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py tests/tools/test_teaching_flow_tool.py tests/tools/test_teaching_flow_registration.py
git commit -m "feat: teaching_flow 工具 (query/advance/reset) + 第15个 always-on 注册"
```

---

### Task 3: `annotation_check` 像素级校验增强（edge/overlap/tightness）

**Files:**
- Modify: `deeptutor/tools/annotation_check.py`
- Test: `tests/tools/test_annotation_check_quality.py`

- [ ] **Step 1: Write the failing test**

Create `tests/tools/test_annotation_check_quality.py`:

```python
"""Pixel-quality heuristic checks for annotation_check (edge/overlap/tightness)."""

from __future__ import annotations

from deeptutor.tools.annotation_check import (
    check_edge_proximity,
    check_overlap,
    check_tightness,
    quality_checks,
)


def test_edge_proximity_triggers():
    boxes = [{"x": 0, "y": 0, "w": 100, "h": 100, "label": "car"}]
    checks = check_edge_proximity(boxes, image_size=(1000, 1000), threshold=5)
    assert len(checks) == 1
    assert checks[0]["rule"] == "edge"


def test_edge_proximity_not_triggered():
    boxes = [{"x": 50, "y": 50, "w": 100, "h": 100, "label": "car"}]
    assert check_edge_proximity(boxes, image_size=(1000, 1000), threshold=5) == []


def test_overlap_triggers():
    boxes = [
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "car"},
        {"x": 20, "y": 20, "w": 100, "h": 100, "label": "car"},
    ]
    checks = check_overlap(boxes, iou_threshold=0.5)
    assert len(checks) == 1
    assert checks[0]["rule"] == "overlap"


def test_overlap_nested_not_flagged():
    boxes = [
        {"x": 10, "y": 10, "w": 200, "h": 200, "label": "car"},
        {"x": 50, "y": 50, "w": 60, "h": 60, "label": "car"},
    ]
    assert check_overlap(boxes, iou_threshold=0.5) == []


def test_tightness_triggers_on_wide_box():
    boxes = [{"x": 10, "y": 10, "w": 800, "h": 50, "label": "car"}]
    checks = check_tightness(boxes, ratio_threshold=5.0)
    assert len(checks) == 1
    assert checks[0]["rule"] == "tightness"


def test_tightness_not_triggered_normal():
    boxes = [{"x": 10, "y": 10, "w": 100, "h": 80, "label": "car"}]
    assert check_tightness(boxes, ratio_threshold=5.0) == []


def test_quality_checks_aggregates():
    boxes = [
        {"x": 0, "y": 0, "w": 800, "h": 40, "label": "car"},
    ]
    checks = quality_checks(boxes, image_size=(1000, 1000))
    rules = {c["rule"] for c in checks}
    assert "edge" in rules
    assert "tightness" in rules
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check_quality.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement the quality checks**

Add to `deeptutor/tools/annotation_check.py` (module-level functions, following the existing `_calculate_iou` style):

```python
# ------------------------------------------------------- quality heuristics

def check_edge_proximity(boxes: list[dict], image_size: tuple[int, int], threshold: int = 5) -> list[dict]:
    """Flag boxes touching the image edge (within threshold px) — may be drawn over the edge or miss edge objects."""
    img_w, img_h = image_size
    checks = []
    for i, box in enumerate(boxes):
        x, y = box["x"], box["y"]
        w, h = box["w"], box["h"]
        if x < threshold or y < threshold or (x + w) > (img_w - threshold) or (y + h) > (img_h - threshold):
            checks.append({
                "rule": "edge",
                "box_idx": i,
                "message": f"框 {i + 1} 贴到图像边缘 (距边界 < {threshold}px)，可能画过头或漏了边缘目标",
            })
    return checks


def check_overlap(boxes: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Flag heavily overlapping boxes (not nested) — likely duplicate annotations of the same object."""
    checks = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            iou = _calculate_iou(boxes[i], boxes[j])
            # skip near-identical nested boxes (one inside the other) — treat as acceptable
            a_area = boxes[i]["w"] * boxes[i]["h"]
            b_area = boxes[j]["w"] * boxes[j]["h"]
            smaller = min(a_area, b_area)
            larger = max(a_area, b_area)
            nested = smaller > 0 and (larger - smaller) / larger > 0.5 and iou >= 0.9
            if iou > iou_threshold and not nested:
                checks.append({
                    "rule": "overlap",
                    "box_idx": i,
                    "other_idx": j,
                    "message": f"框 {i + 1} 与框 {j + 1} 高度重叠 (IOU={iou:.2f})，可能重复标注同一目标",
                })
                break  # only flag once per box
    return checks


def check_tightness(boxes: list[dict], ratio_threshold: float = 5.0) -> list[dict]:
    """Flag boxes with extreme aspect ratio (too wide/thin) — likely too much padding or clipped object."""
    checks = []
    for i, box in enumerate(boxes):
        w, h = box["w"], box["h"]
        if w <= 0 or h <= 0:
            continue
        ratio = max(w, h) / min(w, h)
        if ratio > ratio_threshold:
            checks.append({
                "rule": "tightness",
                "box_idx": i,
                "message": f"框 {i + 1} 宽高比异常 ({ratio:.1f}:1)，可能留白过多或切到目标",
            })
    return checks


def quality_checks(boxes: list[dict], image_size: tuple[int, int]) -> list[dict]:
    """Aggregate all heuristic quality checks (no ground truth needed)."""
    checks = []
    checks.extend(check_edge_proximity(boxes, image_size))
    checks.extend(check_overlap(boxes))
    checks.extend(check_tightness(boxes))
    return checks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check_quality.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Wire quality checks into `_bbox_report` output**

Modify `_bbox_report` in `annotation_check.py` so it accepts an optional `image_size` and appends a "### 质量检查" section listing heuristic checks. Also update the tool `execute()` to accept an optional `image_size` parameter (default `(1000, 1000)`) and pass it through. Keep the change additive — existing bbox/classification behavior unchanged when image_size is absent (default `(1000,1000)` still produces checks; the section is appended after the metrics).

Concretely:
1. `_bbox_report(predictions, ground_truth, iou_threshold=0.5, image_size=(1000,1000))` → after building `lines`, append:
```python
    qchecks = quality_checks(predictions, image_size)
    if qchecks:
        lines.append("\n### 质量检查 (无需标准答案)")
        for qc in qchecks:
            lines.append(f"- {qc['message']}")
```
2. `execute()`: add `ToolParameter(name="image_size", type="string", description="Image dimensions as 'WxH' (e.g. '1000x1000'), used for edge checks. Optional.", required=False)`; parse it (`"WxH"` string → tuple) or default `(1000, 1000)`; pass to `_bbox_report`.

- [ ] **Step 6: Verify existing tests still pass**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check.py tests/tools/test_annotation_check_quality.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (existing annotation_check tests unaffected)

- [ ] **Step 7: Commit**

```bash
git add deeptutor/tools/annotation_check.py tests/tools/test_annotation_check_quality.py
git commit -m "feat: annotation_check 像素级质量校验 (贴边/重叠/紧致度, 无GT启发式)"
```

---

### Task 4: `annotation_check` 新 task_type 评测（judgment/standard/error_case）

**Files:**
- Modify: `deeptutor/tools/annotation_check.py`
- Test: `tests/tools/test_annotation_check_quality.py` (append)

- [ ] **Step 1: Write the failing test** (append to `test_annotation_check_quality.py`)

```python
def test_judgment_report():
    from deeptutor.tools.annotation_check import _judgment_report

    predictions = [{"id": 1, "label": "correct"}, {"id": 2, "label": "wrong"}]
    ground_truth = [{"id": 1, "answer": True}, {"id": 2, "answer": False}]
    content = _judgment_report(predictions, ground_truth)
    assert "Accuracy" in content or "准确率" in content
    assert "50%" in content or "0.5" in content


def test_standard_report_requires_valid_box():
    from deeptutor.tools.annotation_check import _standard_report

    # missing label field -> invalid
    predictions = [{"x": 0, "y": 0, "w": 100, "h": 100}]
    ground_truth = [{"required_fields": ["x", "y", "w", "h", "label"]}]
    content = _standard_report(predictions, ground_truth)
    assert "合规率" in content or "invalid" in content.lower() or "合规" in content


def test_error_case_report():
    from deeptutor.tools.annotation_check import _error_case_report

    # ground truth marks box 1 as erroneous (edge rule); student should flag it
    predictions = [{"id": 1, "flagged": True}, {"id": 2, "flagged": False}]
    ground_truth = [{"id": 1, "is_error": True}, {"id": 2, "is_error": False}]
    content = _error_case_report(predictions, ground_truth)
    assert "检出" in content or "accuracy" in content.lower() or "准确" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check_quality.py::test_judgment_report -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement the three reports**

Add to `deeptutor/tools/annotation_check.py`:

```python
def _judgment_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate judgment (true/false) answers per item."""
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    correct = 0
    total = len(ground_truth)
    lines = ["## 判断题结果\n"]
    for i, pred in enumerate(predictions):
        item_id = pred.get("id", i)
        gt = gt_by_id.get(item_id)
        if not gt:
            lines.append(f"- Item {item_id}: 额外作答（无标准答案）")
            continue
        is_correct = str(pred.get("label", "")).strip().lower() == str(gt.get("answer", "")).strip().lower()
        if is_correct:
            correct += 1
            lines.append(f"- Item {item_id}: ✅ 判断正确")
        else:
            lines.append(f"- Item {item_id}: ❌ 判断错误（正确答案: {gt.get('answer')}）")
    for item_id, gt in gt_by_id.items():
        if not any(p.get("id", i) == item_id for i, p in enumerate(predictions)):
            lines.append(f"- Item {item_id}: 未作答")
    accuracy = correct / total if total > 0 else 0
    lines.append(f"\n**准确率 (Accuracy)**: {accuracy:.0%} ({correct}/{total})")
    return "\n".join(lines)


def _standard_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate annotation-standard compliance (required fields / label / coord ranges)."""
    gt = ground_truth[0] if ground_truth else {}
    required = gt.get("required_fields", ["x", "y", "w", "h", "label"])
    labels = gt.get("labels", [])
    valid = 0
    total = len(predictions)
    lines = ["## 规范校验结果\n"]
    for i, pred in enumerate(predictions):
        missing = [f for f in required if f not in pred]
        bad_label = bool(labels) and pred.get("label") not in labels
        bad_coord = any(pred.get(f) is None for f in ["x", "y", "w", "h"] if f in required)
        if missing or bad_label or bad_coord:
            reasons = []
            if missing:
                reasons.append(f"缺字段 {missing}")
            if bad_label:
                reasons.append(f"标签 '{pred.get('label')}' 不在 {labels}")
            if bad_coord:
                reasons.append("坐标字段为空")
            lines.append(f"- 标注 {i + 1}: ❌ {', '.join(reasons)}")
        else:
            valid += 1
            lines.append(f"- 标注 {i + 1}: ✅ 符合规范")
    rate = valid / total if total > 0 else 0
    lines.append(f"\n**合规率**: {rate:.0%} ({valid}/{total})")
    return "\n".join(lines)


def _error_case_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate whether the student flagged the correct erroneous annotations."""
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    correct = 0
    total = len(ground_truth)
    lines = ["## 错误案例检出结果\n"]
    for i, pred in enumerate(predictions):
        item_id = pred.get("id", i)
        gt = gt_by_id.get(item_id)
        if not gt:
            continue
        flagged = bool(pred.get("flagged"))
        should_flag = bool(gt.get("is_error"))
        if flagged == should_flag:
            correct += 1
            lines.append(f"- 案例 {item_id}: ✅ 判断正确{'（标出错误）' if flagged else '（无误标）'}")
        else:
            lines.append(f"- 案例 {item_id}: ❌ 判断错误（{'应标出错误' if should_flag else '不应标出'}）")
    rate = correct / total if total > 0 else 0
    lines.append(f"\n**检出准确率**: {rate:.0%} ({correct}/{total})")
    return "\n".join(lines)
```

- [ ] **Step 4: Wire into `execute()`**

Modify `execute()` in `annotation_check.py` so `task_type` accepts `bbox | classification | judgment | standard | error_case`:
- `judgment` → `_judgment_report`
- `standard` → `_standard_report`
- `error_case` → `_error_case_report`
- Update the tool definition description + `task_type` parameter enum.

Also add dict-returning variants (`_judgment_dict` / `_standard_dict` / `_error_case_dict`) returning simple `{"accuracy"/"rate": round(x,4)}` for programmatic/metadata use. (Follow `_bbox_dict`/`_classify_dict` pattern.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check_quality.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add deeptutor/tools/annotation_check.py tests/tools/test_annotation_check_quality.py
git commit -m "feat: annotation_check 新题型评测 (judgment/standard/error_case)"
```

---

### Task 5: `grading.py` 题型扩展（tf/规范/错误案例）

**Files:**
- Modify: `deeptutor/learning/grading.py`
- Test: `tests/learning/test_grading.py` (or existing grading test)

- [ ] **Step 1: Write the failing test** (find the existing grading test file first: `glob tests -p "*grading*"`; append or create)

```python
"""grading extension tests — tf / standard / error_case question types."""

from __future__ import annotations

from deeptutor.learning.grading import grade_answer


def test_grade_tf_true():
    assert grade_answer("对", "对", question_type="tf")
    assert grade_answer("正确", "正确", question_type="tf")


def test_grade_tf_false():
    assert not grade_answer("对", "错", question_type="tf")


def test_grade_standard_valid_box():
    # standard question: expected is a JSON spec; answer is a valid box JSON
    expected = '{"required_fields":["x","y","w","h","label"]}'
    answer = '{"x":10,"y":10,"w":100,"h":100,"label":"car"}'
    assert grade_answer(answer, expected, question_type="standard")


def test_grade_standard_missing_field():
    expected = '{"required_fields":["x","y","w","h","label"]}'
    answer = '{"x":10,"y":10,"w":100,"h":100}'  # missing label
    assert not grade_answer(answer, expected, question_type="standard")


def test_grade_error_case():
    # error-case: answer must flag the same error the expected marks
    expected = '{"errors":[1,3]}'
    answer = "[1,3]"
    assert grade_answer(answer, expected, question_type="error_case")


def test_grade_error_case_partial():
    expected = '{"errors":[1,3]}'
    answer = "[1]"
    assert not grade_answer(answer, expected, question_type="error_case")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/learning/test_grading_extension.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL — `grade_answer` returns False for `tf` (unhandled type) or raises

- [ ] **Step 3: Implement** — extend `grade_answer` in `deeptutor/learning/grading.py`:

```python
    if question_type == "tf":
        user = user_answer.strip()
        expected = expected_answer.strip()
        return user.lower() in ("对", "正确", "true", "t", "yes", "是") and \
            expected.lower() in ("对", "正确", "true", "t", "yes", "是") or \
            user.lower() in ("错", "错误", "false", "f", "no", "否") and \
            expected.lower() in ("错", "错误", "false", "f", "no", "否")

    if question_type == "standard":
        import json
        try:
            spec = json.loads(expected_answer)
            answer = json.loads(user_answer)
        except json.JSONDecodeError:
            return False
        required = spec.get("required_fields", [])
        labels = spec.get("labels", [])
        if isinstance(answer, dict):
            if any(f not in answer for f in required):
                return False
            if labels and answer.get("label") not in labels:
                return False
            return True
        return False

    if question_type == "error_case":
        import json
        try:
            spec = json.loads(expected_answer)
            expected_errors = sorted(spec.get("errors", []))
            answer_errors = sorted(json.loads(user_answer)) if isinstance(user_answer, str) and user_answer.strip().startswith("[") else sorted(int(x) for x in user_answer.replace("[", "").replace("]", "").split(",") if x.strip())
        except (json.JSONDecodeError, ValueError):
            return False
        return answer_errors == expected_errors
```

NOTE: the `tf` boolean logic above is convoluted. Write it cleanly instead:
```python
    if question_type == "tf":
        truthy = {"对", "正确", "true", "t", "yes", "是", "1"}
        falsy = {"错", "错误", "false", "f", "no", "否", "0"}
        u = user_answer.strip().lower()
        e = expected_answer.strip().lower()
        if u in truthy:
            return e in truthy
        if u in falsy:
            return e in falsy
        return False
```
Use this clean version.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/learning/test_grading_extension.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

Also run existing grading tests: `python -m pytest tests/learning -k grading -q 2>&1 | Select-Object -Last 4` — no regression.

- [ ] **Step 5: Commit**

```bash
git add deeptutor/learning/grading.py tests/learning/test_grading_extension.py
git commit -m "feat: grading 题型扩展 (tf 判断/规范/错误案例)"
```

---

### Task 6: `task_bank` 新任务 + 接入 flow 协议 + PERSONA

**Files:**
- Modify: `data/user/workspace/task_bank.json` (add task10/11/12)
- Modify: `deeptutor/tools/task_bank_tool.py` (support new types in description/execution)
- Modify: `deeptutor/skills/builtin/annotation-coach-flows/references/flow-practice.md` + mirrored copy
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` + workspace copy

- [ ] **Step 1: Add new tasks to task_bank.json**

Append three tasks (keep existing 9). Structure follows existing entries:

```json
{
  "task10": {
    "title": "标注判断练习",
    "type": "judgment",
    "difficulty": "easy",
    "object_count": 3,
    "image_url": "/images/car2.jpeg",
    "labels": ["correct", "wrong"],
    "instruction": "判断下列标注是否正确。每项标注若符合规范（框紧贴目标、标签正确）则判定 correct，否则判定 wrong。",
    "ground_truth": [
      {"id": 1, "answer": "correct"},
      {"id": 2, "answer": "wrong"},
      {"id": 3, "answer": "correct"}
    ],
    "items": [
      {"id": 1, "text": "框 1 紧贴车身，标签 'car'"},
      {"id": 2, "text": "框 2 明显偏离目标，标签 'car'"},
      {"id": 3, "text": "框 3 覆盖整个车辆，标签 'car'"}
    ],
    "next_task": "task11",
    "knowledge_points": ["标注质量判断", "规范意识"]
  },
  "task11": {
    "title": "标注规范练习",
    "type": "standard",
    "difficulty": "medium",
    "object_count": 1,
    "image_url": "/images/car2.jpeg",
    "labels": ["car"],
    "instruction": "按规范输出一个标准标注框 JSON：必须包含 x/y/w/h/label 字段，label 必须为 'car'。",
    "ground_truth": [
      {"required_fields": ["x", "y", "w", "h", "label"], "labels": ["car"]}
    ],
    "next_task": "task12",
    "knowledge_points": ["标注格式规范", "最小外接矩形原则"]
  },
  "task12": {
    "title": "错误案例找错",
    "type": "error_case",
    "difficulty": "medium",
    "object_count": 3,
    "image_url": "/images/car2.jpeg",
    "labels": ["car"],
    "instruction": "下列标注中，找出标错的项（框不贴边/重叠/宽高比异常等）。输出标错项的 id 列表，如 [1,3]。",
    "ground_truth": [
      {"id": 1, "is_error": true},
      {"id": 2, "is_error": false},
      {"id": 3, "is_error": true}
    ],
    "items": [
      {"id": 1, "text": "框贴到图像左边缘"},
      {"id": 2, "text": "框紧贴目标，比例正常"},
      {"id": 3, "text": "框宽高比异常 (10:1)"}
    ],
    "next_task": null,
    "knowledge_points": ["错误模式识别", "像素质量检查"]
  }
}
```

Use a Python script to merge (preserve existing 9):
```powershell
cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -c @"
import json
from pathlib import Path
p = Path('data/user/workspace/task_bank.json')
d = json.loads(p.read_text(encoding='utf-8'))
new = { ... }  # the 3 new tasks as a dict literal
d.update(new)
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
print('tasks:', len(d))
"@
```

- [ ] **Step 2: Update `get_annotation_task` for new types**

Modify `deeptutor/tools/task_bank_tool.py`:
1. Update the tool description to mention judgment/standard/error_case types.
2. Extend the `execute()` so bbox/classification rendering stays, and add rendering for `judgment` (items + per-item判定), `standard` (格式规范), `error_case` (items + 输出标错 id)。 Ground truth is included for annotation_check like before.

- [ ] **Step 3: Verify task_bank loads + tool works**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -c "import json; d=json.load(open(r'data/user/workspace/task_bank.json',encoding='utf-8')); print('tasks:', len(d)); print('task10 type:', d['task10']['type'], '| task11:', d['task11']['type'], '| task12:', d['task12']['type'])"`
Expected: tasks: 12, types judgment/standard/error_case.

- [ ] **Step 4: Wire `teaching_flow` into flow-practice protocol**

Edit `deeptutor/skills/builtin/annotation-coach-flows/references/flow-practice.md` — Step1 (选任务), add:

```markdown
调 `teaching_flow` 查询当前步骤:
  → 若是新任务 → action=start_task 记录开始 (或由评测自动建立)
  → 推进各步骤: 展示完任务 action=advance(show_task), 收到提交 advance(waiting), 评测后自动推进 evaluate
  → 卡住/等待学生时可用 action=block 记录阻塞原因
```

Sync to `deeptutor/services/persona/presets/annotation-coach/references/flow-practice.md` (Copy-Item).

- [ ] **Step 5: Add PERSONA rule 13**

Edit `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` after rule 12:

```markdown
13. **用 `teaching_flow` 跟踪任务步骤**：每个任务按 6 步协议推进
    （选任务→展示→等待→评测→反馈→记录），用 `teaching_flow` 查询/推进，
    评测后自动进入反馈。学生等待超时用 block 记录阻塞并主动询问。
```

Sync to workspace copy `data/user/workspace/personas/annotation-coach/PERSONA.md` (same edit — that file is gitignored but must be updated for runtime effect).

- [ ] **Step 6: Commit**

```bash
git add deeptutor/tools/task_bank_tool.py deeptutor/skills/builtin/annotation-coach-flows/references/flow-practice.md deeptutor/services/persona/presets/annotation-coach/PERSONA.md deeptutor/services/persona/presets/annotation-coach/references/flow-practice.md
git add -f data/user/workspace/task_bank.json
git commit -m "feat: task_bank 新题型任务 + teaching_flow 接入流程协议 + PERSONA 规则13"
```
(The workspace PERSONA copy is gitignored — update it but it won't be in the commit; note this.)

---

### Task 7: 全量回归 + 冒烟

**Files:** none (verification)

- [ ] **Step 1: Run full struggle + flow + grading + tools tests**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_teaching_flow.py tests/tools/test_teaching_flow_tool.py tests/tools/test_teaching_flow_registration.py tests/tools/test_annotation_check_quality.py tests/learning/test_grading_extension.py -q 2>&1 | Select-Object -Last 6`
Expected: PASS

- [ ] **Step 2: Backend full regression**

Run: `python -m pytest tests/ -q 2>&1 | Select-Object -Last 6`
Expected: no NEW failures vs the known pre-existing baseline (Windows path/sep, optional deps, sandbox, etc.)

- [ ] **Step 3: End-to-end smoke (engine + tool + checks)**

Run:
```powershell
cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -c @"
import asyncio
from deeptutor.services.teaching_flow import TeachingFlowEngine
from deeptutor.tools.annotation_check import quality_checks

# 1) flow state machine
e = TeachingFlowEngine(path=None, base_dir='C:/Users/free/AppData/Local/Temp/opencode/flow-smoke')
state = e.start_task('task1')
state = e.advance('show_task')
state = e.advance('waiting')
state = e.on_evaluated('task1', f1=0.5)
print('flow step:', state['current_step'], '| evaluate f1:', state['steps']['evaluate']['f1'])

# 2) quality checks on an edge-touching wide box
boxes = [{'x':0,'y':0,'w':800,'h':40,'label':'car'}]
qc = quality_checks(boxes, image_size=(1000,1000))
print('quality rules:', sorted({c['rule'] for c in qc}))

# 3) gate blocks skipping
state = e.advance('record')  # feedback not done -> blocked
print('gate blocked:', state['blocked'] is not None)

assert state['current_step'] == 'feedback'
assert {'edge','tightness'} <= {c['rule'] for c in qc}
assert state['blocked'] is not None
print('SMOKE OK')
"@
```
Expected: flow step=feedback, quality rules=[edge, tightness], gate blocked=True, SMOKE OK.

- [ ] **Step 4: Commit any fixes**

If smoke found issues, fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §4 TeachingFlowEngine → Task 1
- §5 teaching_flow 工具 → Task 2
- §6.1 像素校验 → Task 3
- §6.2 新 task_type 评测 → Task 4
- §7 grading.py 题型 → Task 5
- §8 task_bank 新任务 + 协议 → Task 6
- §9 测试验证 → Task 7
✅ 全覆盖

**2. Placeholder scan:** 所有代码块完整。Task 1 测试的 `state_path=None` 用法有说明（implementer 需清理避免污染 CWD）；Task 3/4 引用现有 `annotation_check.py` 的 `_calculate_iou`/`_bbox_report` 结构（已有）。

**3. Type consistency:**
- `TeachingFlowEngine` 方法: `start_task/advance/on_evaluated/block/reset/get_state/next_step_hint` — Task 1/2 一致
- 状态文件字段: `task_id/current_step/steps/{status,ts}/blocked/updated_at` — Task 1/2 一致
- 步骤名: `select_task/show_task/waiting/evaluate/feedback/record` — Task 1/2/6 一致
- `quality_checks(boxes, image_size)` → `[{rule, box_idx, message}]` — Task 3 一致
- 新 task_type: `judgment/standard/error_case` — Task 4/5/6 一致
- `teaching_flow` 工具名 — Task 2/6 一致

**已知风险：**
1. Task 1 测试里 `state_path=None` 会写入 CWD——implementer 需改用 tmp_path 或 no-persist 模式（已标注）
2. Task 3 `_bbox_report` 加 `image_size` 参数是 additivce——需确保现有测试不受影响（默认值兜底）
3. Task 4 `_standard_report` 的 ground_truth 结构是自定义的（`required_fields`）——新 task_type 的 GT 结构由 task_bank 提供，两者需对齐
4. Task 6 的 workspace PERSONA 副本 gitignored——需同步更新但不提交（已标注）
5. task_bank.json 是运行时数据（gitignored）——提交需 `-f`（已标注）
