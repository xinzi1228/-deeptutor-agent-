# 多专家角色体系实施计划（Expert Roles — 借鉴 agency-agents）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把标注星图教学升级为多专家角色体系——6 专家角色集（对应竞赛 6 模块，agency-agents 封装结构）+ 轻量编排（TeachingFlowEngine 阶段→专家路由 + 评测后自动 readiness 验收）+ 专家索引与一致性校验。

**Architecture:** 6 个专家角色 markdown（`annotation-coach-flows/references/experts/`）→ `experts_manifest.json`（divisions.json 风格索引）+ pytest 校验 → `TeachingFlowEngine.expert_route()`（阶段→专家）+ teaching_flow query 附带 expert → `annotation_check` 评测后自动 readiness 判定并写入 flow_state/records。annotation-coach 总协调按阶段路由。

**Tech Stack:** Python 3.13, pytest + pytest-asyncio, markdown (角色卡), Next.js (无前端改动——teaching_flow 工具内容附带 expert)。

**Spec:** `docs/specs/expert-roles-design.md`（已提交 `3592b2e3`）

---

### Task 1: 6 专家角色文件 + annotation-coach 协作节

**Files:**
- Create: `deeptutor/skills/builtin/annotation-coach-flows/references/experts/{learning_planner,session_steward,task_guide,struggle_detective,report_analyst,grading_expert}.md`
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` (+ sync workspace copy)
- Test: `tests/test_experts.py` (frontmatter + id/name/file consistency)

- [ ] **Step 1: Write the failing test**

Create `tests/test_experts.py`:

```python
"""Expert role files — frontmatter completeness + id/name/file consistency."""

from __future__ import annotations

import re
from pathlib import Path

EXPERT_DIR = Path(__file__).resolve().parents[1] / "deeptutor" / "skills" / "builtin" / "annotation-coach-flows" / "references" / "experts"

EXPECTED_EXPERTS = [
    "learning_planner", "session_steward", "task_guide",
    "struggle_detective", "report_analyst", "grading_expert",
]

REQUIRED_FRONTMATTER = ["name", "description", "color", "emoji", "vibe"]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def test_expert_files_exist():
    for eid in EXPECTED_EXPERTS:
        assert (EXPERT_DIR / f"{eid}.md").exists(), f"missing expert file {eid}.md"


def test_no_extra_expert_files():
    files = {p.stem for p in EXPERT_DIR.glob("*.md")}
    assert files == set(EXPECTED_EXPERTS)


def test_frontmatter_complete():
    for eid in EXPECTED_EXPERTS:
        fm = _frontmatter(EXPERT_DIR / f"{eid}.md")
        for field in REQUIRED_FRONTMATTER:
            assert fm.get(field), f"{eid}.md missing frontmatter field: {field}"


def test_frontmatter_name_matches_filename():
    for eid in EXPECTED_EXPERTS:
        fm = _frontmatter(EXPERT_DIR / f"{eid}.md")
        assert fm.get("name") == eid, f"{eid}.md frontmatter name mismatch"


def test_expert_sections_present():
    for eid in EXPECTED_EXPERTS:
        text = (EXPERT_DIR / f"{eid}.md").read_text(encoding="utf-8")
        for section in ["身份", "使命", "规则", "能力", "流程"]:
            assert section in text, f"{eid}.md missing section: {section}"
```

NOTE: adjust the section keywords to match what you actually put in the expert files (e.g. 身份/使命/规则/能力/流程/交付物). Keep the test aligned with the template structure you use.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_experts.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL (no expert files)

- [ ] **Step 3: Create the 6 expert files**

Read the existing flow files (`flow-theory.md`, `flow-practice.md`, `decision-matrix.md`) to match the writing style. Then create 6 expert files under `deeptutor/skills/builtin/annotation-coach-flows/references/experts/`, each following this template (fill in per-expert specifics):

```markdown
---
name: <expert_id>
description: <一句话职责>
color: "#<hex>"
emoji: <emoji>
vibe: <角色气质一句话>
---

# <专家名> Agent

你是<专家名>，专注<职责域>。

## 🧠 你的身份与记忆

- **角色**: <角色定位>
- **人格**: <人格特征>
- **记忆**: <你记住的领域模式>
- **经验**: <背景>

## 🎯 你的核心使命

### <任务域 1>

- 职责...

### <任务域 2>

- 职责...

## ⚠️ 你必须遵守的规则

### <规则域>

- 规则...（引用对应 flow 协议 / 工具 / readiness_gate）

## 🛠 你的核心能力

### 工具与数据

- **工具**: <工具名列表>
- **数据源**: <数据源>

## 📋 你的流程与交付物

### 流程

- 步骤...

### 交付物

- 产出...
```

Per-expert content guidance (from the design doc §3.1):

1. **learning_planner** (🗺️ #10B981, ①学习计划): 诊断→建课程计划、模块化路线、目标对齐。Rules: 用 finalize_diagnosis 建课（不手写路线）；诊断记录必落盘；参考 flow-onboarding Step4/5。Tools: finalize_diagnosis, write_learning_record, course_plan. Deliverables: 4 模块课程计划、诊断 brief。
2. **session_steward** (💬 #6366F1, ②会话管理): 会话恢复、断点续学、记忆管理。Rules: 有历史先 read_memory 恢复上下文；断点从上次 readiness 续；三层记忆读/写。Tools: read_memory, write_memory, teaching_flow (query). Deliverables: 恢复摘要、续学建议。
3. **task_guide** (🧭 #F59E0B, ③任务引导): 选任务、展示、等待、推进、6 步协议。Rules: 用 teaching_flow 跟踪步骤（start_task/advance/block）；选任务按 readiness_gate 6 判定；评测后自动推进 evaluate。Tools: teaching_flow, get_annotation_task, log_decision. Deliverables: 任务展示、步骤状态。
4. **struggle_detective** (🕵️ #EF4444, ④困难介入): 卡住检测、介入建议、阻塞报告。Rules: 评测后必查 struggle_detect；有信号按建议介入并用 log_decision(kind=struggle_intervention)；阻塞记 block。Tools: struggle_detect, teaching_flow (block), log_decision. Deliverables: 介入建议、阻塞报告。
5. **report_analyst** (📊 #8B5CF6, ⑤学习报告): 进度/雷达/图谱/成就报告、可视化。Rules: 报告用确定性数据（graph_query/chart_cards/achievements）；不虚构数据。Tools: graph_query, ability_radar, achievements (via API), chart_cards. Deliverables: 进度报告、雷达/图谱/成就展示。
6. **grading_expert** (✅ #06B6D4, ⑥练习批改): 评测、反馈、错误分析、readiness 判定。Rules: 用 annotation_check 评测（bbox 带 task_id 自动推进）；feedback 分回合（Verdict→缺口→修复）；按 readiness_gate 判定推进。Tools: annotation_check, grading, teaching_flow. Deliverables: 评测结果、分回合反馈、readiness。

- [ ] **Step 4: Add the 专家协作 section to PERSONA.md**

Edit `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` — add a section (e.g. after rule 13, before 角色定位):

```markdown
## 专家协作（多专家角色体系）

你是总协调者。按教学阶段路由到对应专家视角，调用专家角色卡的规则：

| 阶段 | 路由专家 |
|------|---------|
| 诊断/建课 | learning_planner |
| 会话恢复/记忆 | session_steward |
| 选任务/推进 | task_guide |
| 卡住/介入 | struggle_detective |
| 进度/报告 | report_analyst |
| 评测/反馈 | grading_expert |

切换专家视角时，遵守对应专家角色卡的 Core Mission + Critical Rules。
专家角色卡在 annotation-coach-flows skill 的 references/experts/ 下。
```

Sync to the workspace copy `data/user/workspace/personas/annotation-coach/PERSONA.md` (gitignored, apply the same edit).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_experts.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 6: Ruff + Commit**

Ruff: `python -m ruff check tests/test_experts.py`

```bash
git add deeptutor/skills/builtin/annotation-coach-flows/references/experts/ deeptutor/services/persona/presets/annotation-coach/PERSONA.md tests/test_experts.py
git commit -m "feat: 6 专家角色卡 (agency-agents 结构) + annotation-coach 专家协作节"
```
(The workspace PERSONA copy is gitignored — update it but it won't be committed.)

---

### Task 2: `experts_manifest.json` + 一致性校验测试

**Files:**
- Create: `deeptutor/skills/builtin/annotation-coach-flows/experts_manifest.json`
- Test: `tests/test_experts_manifest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_experts_manifest.py`:

```python
"""experts_manifest.json consistency — index <-> directory + frontmatter."""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "deeptutor" / "skills" / "builtin" / "annotation-coach-flows"
MANIFEST_PATH = BASE / "experts_manifest.json"
EXPERT_DIR = BASE / "references" / "experts"
REQUIRED_FIELDS = ["id", "label", "icon", "color", "file"]


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def test_manifest_exists():
    assert MANIFEST_PATH.exists()


def test_manifest_has_coordinator_and_6_experts():
    manifest = _load_manifest()
    assert "coordinator" in manifest
    assert manifest["coordinator"]["id"] == "annotation_coach"
    experts = manifest["experts"]
    assert len(experts) == 6


def test_manifest_entries_have_required_fields():
    manifest = _load_manifest()
    for entry in [manifest["coordinator"]] + manifest["experts"]:
        for field in REQUIRED_FIELDS:
            assert entry.get(field), f"manifest entry missing {field}: {entry}"


def test_manifest_files_exist():
    manifest = _load_manifest()
    for entry in [manifest["coordinator"]] + manifest["experts"]:
        p = BASE / entry["file"]
        assert p.exists(), f"manifest file missing: {entry['file']}"


def test_every_expert_file_in_manifest():
    files = {p.stem for p in EXPERT_DIR.glob("*.md")}
    manifest_ids = {e["id"] for e in _load_manifest()["experts"]}
    assert files == manifest_ids


def test_frontmatter_name_matches_manifest_id():
    manifest = _load_manifest()
    for entry in manifest["experts"]:
        fm = _frontmatter(EXPERT_DIR / f"{entry['id']}.md")
        assert fm.get("name") == entry["id"], f"{entry['id']} frontmatter name mismatch"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_experts_manifest.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL (no manifest)

- [ ] **Step 3: Create `experts_manifest.json`**

Create `deeptutor/skills/builtin/annotation-coach-flows/experts_manifest.json`:

```json
{
  "_note": "教学专家角色索引（Source of truth）。coordinator + 6 experts。每个条目 file 指向角色文件。pytest 校验目录与索引双向一致 + frontmatter 完整。",
  "coordinator": {
    "id": "annotation_coach",
    "label": "标注教练",
    "icon": "🎯",
    "color": "#3B82F6",
    "file": "../../services/persona/presets/annotation-coach/PERSONA.md"
  },
  "experts": [
    {"id": "learning_planner", "label": "学习计划师", "icon": "🗺️", "color": "#10B981", "file": "references/experts/learning_planner.md"},
    {"id": "session_steward", "label": "会话管家", "icon": "💬", "color": "#6366F1", "file": "references/experts/session_steward.md"},
    {"id": "task_guide", "label": "任务引导师", "icon": "🧭", "color": "#F59E0B", "file": "references/experts/task_guide.md"},
    {"id": "struggle_detective", "label": "困难检测师", "icon": "🕵️", "color": "#EF4444", "file": "references/experts/struggle_detective.md"},
    {"id": "report_analyst", "label": "学习报告师", "icon": "📊", "color": "#8B5CF6", "file": "references/experts/report_analyst.md"},
    {"id": "grading_expert", "label": "练习批改师", "icon": "✅", "color": "#06B6D4", "file": "references/experts/grading_expert.md"}
  ]
}
```

IMPORTANT: adjust the coordinator `file` path so `BASE / file` resolves correctly in the test. `BASE` in the test is `.../annotation-coach-flows`. The PERSONA.md is at `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` — relative from `.../annotation-coach-flows` that is `../../services/persona/presets/annotation-coach/PERSONA.md`. Verify the relative path resolves (`python -c "from pathlib import Path; p=Path('deeptutor/skills/builtin/annotation-coach-flows')/'../../services/persona/presets/annotation-coach/PERSONA.md'; print(p.resolve(), p.resolve().exists())"`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_experts_manifest.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Ruff + Commit**

Ruff: `python -m ruff check tests/test_experts_manifest.py`

```bash
git add deeptutor/skills/builtin/annotation-coach-flows/experts_manifest.json tests/test_experts_manifest.py
git commit -m "feat: experts_manifest.json 索引 (divisions.json 风格) + 一致性校验测试"
```

---

### Task 3: `TeachingFlowEngine.expert_route` + teaching_flow query 附带 expert

**Files:**
- Modify: `deeptutor/services/teaching_flow.py`
- Modify: `deeptutor/tools/teaching_flow_tool.py`
- Test: `tests/services/test_teaching_flow.py` (append) + `tests/tools/test_teaching_flow_tool.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/services/test_teaching_flow.py`:

```python
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
```

NOTE: The engine should include `expert` in the returned state (from `get_state`/`start_task`/`advance`/`on_evaluated`). Adjust `_fresh_state` to compute `expert` from `current_step` via `expert_route`. Verify the expected expert values against your mapping.

Append to `tests/tools/test_teaching_flow_tool.py`:

```python
@pytest.mark.asyncio
async def test_query_includes_expert(fake_engine):
    from deeptutor.tools.teaching_flow_tool import TeachingFlowTool

    fake_engine.state = {"task_id": "task1", "current_step": "evaluate", "steps": {}, "blocked": None, "expert": "grading_expert"}
    result = await TeachingFlowTool().execute(action="query")
    assert result.success
    assert "grading_expert" in result.content
```

(Extend the `_FakeEngine` state to include `expert` if needed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_teaching_flow.py::test_expert_route_mapping -v 2>&1 | Select-Object -First 8`
Expected: FAIL (EXPERT_ROUTE not defined)

- [ ] **Step 3: Implement**

In `deeptutor/services/teaching_flow.py`:
1. Add the `EXPERT_ROUTE` mapping (module-level constant):

```python
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
```

2. Add the method + include expert in state:

```python
    def expert_route(self, stage: str) -> str:
        """Map a teaching stage to its expert role id (default: task_guide)."""
        return EXPERT_ROUTE.get(stage, "task_guide")

    def _fresh_state(self) -> dict:
        state = {
            "task_id": None,
            "current_step": "select_task",
            "steps": {s: {"status": STATUS_PENDING, "ts": None} for s in FLOW_STEPS},
            "blocked": None,
            "updated_at": None,
        }
        state["expert"] = self.expert_route("select_task")
        return state
```

3. In `_write` (or wherever current_step is set), keep `expert` synced to `current_step`. The simplest: after building the state dict in each action method, set `state["expert"] = self.expert_route(state.get("current_step") or "select_task")` right before `_write`. Add a small helper `_with_expert(state)` that returns the state with `expert` set, and call it in start_task/advance/on_evaluated/block/reset before writing.

In `deeptutor/tools/teaching_flow_tool.py` `_format_state`, add the expert line:

```python
def _format_state(state: dict, hint: str | None = None) -> str:
    task = state.get("task_id") or "（未开始）"
    step = state.get("current_step") or "（完成）"
    expert = state.get("expert") or "—"
    blocked = state.get("blocked")
    lines = ["## 教学流程状态", f"当前任务: {task}", f"当前步骤: {step}", f"路由专家: {expert}"]
    if blocked:
        lines.append(f"阻塞: {blocked.get('reason', '')}")
        lines.append(f"建议: {blocked.get('next_action', '')}")
    elif hint:
        lines.append(f"下一步: {hint}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_teaching_flow.py tests/tools/test_teaching_flow_tool.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (existing + new tests)

- [ ] **Step 5: Ruff + Commit**

Ruff: `python -m ruff check deeptutor/services/teaching_flow.py deeptutor/tools/teaching_flow_tool.py tests/services/test_teaching_flow.py tests/tools/test_teaching_flow_tool.py`

```bash
git add deeptutor/services/teaching_flow.py deeptutor/tools/teaching_flow_tool.py tests/services/test_teaching_flow.py tests/tools/test_teaching_flow_tool.py
git commit -m "feat: TeachingFlowEngine 阶段→专家路由 (expert_route) + query 附带专家"
```

---

### Task 4: `annotation_check` 自动 readiness 验收

**Files:**
- Modify: `deeptutor/tools/annotation_check.py`
- Test: `tests/tools/test_annotation_check_quality.py` (append) or new `tests/tools/test_readiness_auto.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tools/test_annotation_check_quality.py` (or a new file):

```python
def test_auto_readiness_thresholds():
    from deeptutor.tools.annotation_check import auto_readiness

    assert auto_readiness(0.9) == "advance"
    assert auto_readiness(0.85) == "advance"
    assert auto_readiness(0.8) == "advance_with_caution"
    assert auto_readiness(0.7) == "advance_with_caution"
    assert auto_readiness(0.68) == "more_practice"
    assert auto_readiness(0.65) == "more_practice"
    assert auto_readiness(0.5) == "review_first"


def test_auto_readiness_floor():
    from deeptutor.tools.annotation_check import auto_readiness

    assert auto_readiness(0.0) == "review_first"
    assert auto_readiness(None) == "review_first"  # missing f1 -> conservative
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check_quality.py::test_auto_readiness_thresholds -v 2>&1 | Select-Object -First 8`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement**

In `deeptutor/tools/annotation_check.py`, add the readiness helper (module-level):

```python
# -------------------------------------------------------- auto readiness gate

READINESS_ADVANCE = "advance"
READINESS_ADVANCE_WITH_CAUTION = "advance_with_caution"
READINESS_MORE_PRACTICE = "more_practice"
READINESS_REVIEW_FIRST = "review_first"


def auto_readiness(f1: float | None) -> str:
    """Map an F1 score to a readiness_gate decision (deterministic, conservative on missing)."""
    try:
        f = float(f1)
    except (TypeError, ValueError):
        return READINESS_REVIEW_FIRST
    if f >= 0.85:
        return READINESS_ADVANCE
    if f >= 0.7:
        return READINESS_ADVANCE_WITH_CAUTION
    if f >= 0.65:
        return READINESS_MORE_PRACTICE
    return READINESS_REVIEW_FIRST
```

Then wire it into the bbox branch of `execute()`: after computing `f1` and the auto-advance (`on_evaluated`), also:
1. Compute `readiness = auto_readiness(f1)`.
2. Store it in `metadata` (e.g. `metadata["readiness"] = readiness`).
3. If `task_id` was provided, record it in the flow state (extend the `on_evaluated` call to pass `readiness` — but that changes TeachingFlowEngine's signature; instead keep it simple: add the readiness to the flow state via a small extension, OR just include it in the tool's returned metadata + append to the content text so the Coach sees it). PREFER the minimal path: put `readiness` in the returned `metadata` and mention it in the report content ("自动判定 readiness: advance"). Also log it via the learning record if the tool already writes one (it appends a `write_learning_record` reminder — the actual record write is done by the Coach). So: include readiness in metadata + content, and let the Coach include it when it calls write_learning_record.

If you want the flow_state to carry readiness, extend `TeachingFlowEngine.on_evaluated` to accept an optional `readiness` kwarg and store it in `steps["evaluate"]["readiness"]`. That's clean and keeps the engine deterministic. Do BOTH if straightforward:
- `on_evaluated(task_id, f1, readiness=None)` → `steps["evaluate"]["readiness"] = readiness` when provided
- `annotation_check` bbox branch computes readiness and passes it through

Update the existing `on_evaluated` tests accordingly (they call `on_evaluated("task1", f1=0.5)` — adding an optional kwarg is backward compatible).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_annotation_check_quality.py tests/services/test_teaching_flow.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Ruff + Commit**

Ruff: `python -m ruff check deeptutor/tools/annotation_check.py deeptutor/services/teaching_flow.py tests/tools/test_annotation_check_quality.py tests/services/test_teaching_flow.py`

```bash
git add deeptutor/tools/annotation_check.py deeptutor/services/teaching_flow.py tests/tools/test_annotation_check_quality.py tests/services/test_teaching_flow.py
git commit -m "feat: annotation_check 自动 readiness 验收 (F1阈值→readiness_gate判定)"
```

---

### Task 5: 全量回归 + 冒烟

**Files:** none (verification)

- [ ] **Step 1: Run feature tests**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/test_experts.py tests/test_experts_manifest.py tests/services/test_teaching_flow.py tests/tools/test_teaching_flow_tool.py tests/tools/test_annotation_check_quality.py -q 2>&1 | Select-Object -Last 5`
Expected: PASS

- [ ] **Step 2: Backend full regression**

Run: `python -m pytest tests/ -q 2>&1 | Select-Object -Last 6`
Expected: no NEW failures vs the known pre-existing baseline (~33: Windows path/sep, GBK locale, missing optional deps, sandbox env).

- [ ] **Step 3: End-to-end smoke (expert route + readiness + manifest)**

Run:
```powershell
cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -c @"
import json
from pathlib import Path
from deeptutor.services.teaching_flow import TeachingFlowEngine, EXPERT_ROUTE
from deeptutor.tools.annotation_check import auto_readiness
import deeptutor.skills.builtin.annotation_coach_flows  # noqa (module may not exist; see below)

# 1) expert route
e = TeachingFlowEngine(path=None, in_memory=True)
e.start_task('task1')
print('state expert:', e.get_state().get('expert'))
print('route evaluate ->', EXPERT_ROUTE['evaluate'])

# 2) readiness thresholds
print('readiness 0.9 ->', auto_readiness(0.9))
print('readiness 0.8 ->', auto_readiness(0.8))
print('readiness 0.68 ->', auto_readiness(0.68))
print('readiness 0.5 ->', auto_readiness(0.5))

# 3) manifest consistency
base = Path('deeptutor/skills/builtin/annotation-coach-flows')
m = json.loads((base/'experts_manifest.json').read_text(encoding='utf-8'))
files = {p.stem for p in (base/'references/experts').glob('*.md')}
ids = {x['id'] for x in m['experts']}
print('manifest experts:', len(m['experts']), '| files match:', files == ids)

assert e.get_state().get('expert') == 'task_guide'
assert auto_readiness(0.9) == 'advance'
assert files == ids
print('SMOKE OK')
"@
```
Expected: state expert = task_guide, route evaluate → grading_expert, readiness thresholds correct, manifest files match, SMOKE OK.

NOTE: the `import deeptutor.skills.builtin.annotation_coach_flows` line is just a probe — if that module doesn't exist, remove it. The smoke relies on reading the manifest + expert files from disk (path-relative to the repo root).

- [ ] **Step 4: Commit any fixes**

If smoke/full-run found issues, fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §3.1/3.2 专家角色文件 → Task 1
- §3.3 PERSONA 协作节 → Task 1
- §5.1/5.2 索引 + 校验 → Task 2
- §4.1 expert_route → Task 3
- §4.2 自动 readiness → Task 4
- §6 测试验证 → Task 5
✅ 全覆盖

**2. Placeholder scan:** 所有代码块完整。Task 1 的专家文件是内容写作（给出模板 + 每专家职责/规则/工具/交付物要点）；Task 3 的 expert 字段同步到 state 需 implementer 按 `_with_expert` 小助手处理；Task 4 的 `on_evaluated` 加可选 readiness kwarg 需 backward-compatible。

**3. Type consistency:**
- 专家 id: `learning_planner/session_steward/task_guide/struggle_detective/report_analyst/grading_expert` — Task 1/2/3 一致
- `EXPERT_ROUTE` 键: 任务级 6 步 + 会话级阶段 — Task 3 一致
- readiness: `advance/advance_with_caution/more_practice/review_first` — Task 4 与 decision-matrix 一致
- manifest 字段: `id/label/icon/color/file` — Task 2 一致

**已知风险：**
1. Task 1 专家文件是长 markdown——implementer 按模板写，测试只校验 frontmatter + section 关键词，不校验内容深度
2. Task 3 `expert` 字段需在所有 state 返回路径同步——用 `_with_expert` 小助手统一
3. Task 4 `on_evaluated` 加可选 kwarg——backward-compatible，现有测试不受影响
4. Task 2 协调者 file 相对路径需解析正确——已给验证命令
