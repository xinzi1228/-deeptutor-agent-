# 议题⑦ 多 Agent 总控 Phase 1（delegate_to_expert 委派工具）— 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `delegate_to_expert` 工具：总控 Agent 把子任务委派给某个分管专家（6 专家卡），用专家卡 prompt + 自包含 brief 起独立 LLM 回合，返回结构化结论。**上下文隔离核心**：分管专家不继承总控全历史，只看到 brief + task_data（dispatching-parallel-agents 原则）。

**Architecture:** 读专家卡（`deeptutor/skills/builtin/annotation-coach-flows/references/experts/<id>.md`）→ 构造 system=专家卡正文 + user=brief+task_data → LLM complete → 返回 `metadata.delegate={expert, result}`。**Phase 1 纯 LLM 委派**（受限工具由总控委派前调用并把结果放进 task_data，保持 brief 自包含）。分管 agent 的完整独立 AgentLoop 为后续 Phase。

**Tech Stack:** Python 3.11+ / pytest-asyncio / pathlib / BaseTool 协议

**依赖设计文档:** `docs/superpowers/specs/2026-08-05-master-orchestrator-design.md`

---

## File Structure

- Create: `deeptutor/tools/delegate_expert_tool.py` — `DelegateExpertTool` + `load_expert_card` 纯函数 + `EXPERT_IDS`
- Create: `tests/tools/test_delegate_expert_tool.py` — 测试（mock LLM + 专家卡读取）
- Modify: `deeptutor/tools/builtin/__init__.py` — 4 处注册
- Modify: `deeptutor/agents/_shared/tool_composition.py` — always_on 加 `"delegate_to_expert"`
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` + 副本 — 「总控委派」节

---

### Task 1: `delegate_expert_tool.py`（专家卡读取 + 委派工具）

**Files:**
- Create: `deeptutor/tools/delegate_expert_tool.py`
- Test: `tests/tools/test_delegate_expert_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_delegate_expert_tool.py
import pytest

from deeptutor.tools.delegate_expert_tool import (
    EXPERT_IDS,
    DelegateExpertTool,
    load_expert_card,
)


def test_expert_ids_six():
    assert set(EXPERT_IDS) == {
        "learning_planner", "task_guide", "grading_expert",
        "struggle_detective", "report_analyst", "session_steward",
    }


def test_load_expert_card_grading():
    card = load_expert_card("grading_expert")
    assert "批改专家" in card
    assert "annotation_check" in card


def test_load_expert_card_missing_returns_empty():
    assert load_expert_card("nonexistent") == ""


@pytest.mark.asyncio
async def test_execute_delegates_to_llm(monkeypatch):
    import deeptutor.services.llm as llm_mod

    captured = {}

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        captured["system"] = system_prompt
        captured["user"] = prompt
        return "F1=0.83，建议 advance_with_caution。"

    monkeypatch.setattr(llm_mod, "complete", fake_complete)
    tool = DelegateExpertTool()
    result = await tool.execute(
        expert_id="grading_expert",
        brief="评测学生提交的 bbox 标注",
        task_data='{"f1": 0.83}',
    )
    assert result.success is True
    assert result.metadata["delegate"]["expert"] == "grading_expert"
    assert "F1=0.83" in result.content
    assert "批改专家" in captured["system"]  # 专家卡注入 system
    assert "评测学生提交的 bbox 标注" in captured["user"]


@pytest.mark.asyncio
async def test_execute_invalid_expert_fails():
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="hacker", brief="x")
    assert result.success is False


@pytest.mark.asyncio
async def test_execute_empty_brief_fails():
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="   ")
    assert result.success is False


@pytest.mark.asyncio
async def test_execute_llm_error_fails(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def broken(prompt, system_prompt=None, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm_mod, "complete", broken)
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="x")
    assert result.success is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_delegate_expert_tool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.tools.delegate_expert_tool'`

- [ ] **Step 3: Write minimal implementation**

```python
# deeptutor/tools/delegate_expert_tool.py
"""DelegateExpertTool — delegate a sub-task to a specialist expert.

The master agent hands a self-contained brief + task data to one of the six
expert cards. The expert runs as an isolated LLM turn (system = expert card,
user = brief), NEVER inheriting the master's full conversation history
(context isolation — dispatching-parallel-agents principle).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

EXPERTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "skills" / "builtin" / "annotation-coach-flows" / "references" / "experts"
)

EXPERT_IDS: tuple[str, ...] = (
    "learning_planner",
    "task_guide",
    "grading_expert",
    "struggle_detective",
    "report_analyst",
    "session_steward",
)


def load_expert_card(expert_id: str) -> str:
    """Load an expert card markdown (frontmatter + body). Empty if missing."""
    md = EXPERTS_DIR / f"{expert_id}.md"
    if not md.exists():
        return ""
    return md.read_text(encoding="utf-8")


class DelegateExpertTool(BaseTool):
    """Delegate a sub-task to a specialist expert with isolated context."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="delegate_to_expert",
            description=(
                "Delegate a focused sub-task to a specialist expert (6 experts: "
                "learning_planner / task_guide / grading_expert / struggle_detective / "
                "report_analyst / session_steward). Provide a SELF-CONTAINED brief and "
                "task_data — the expert does NOT see the conversation history. The expert "
                "returns its conclusion for the master to synthesize."
            ),
            parameters=[
                ToolParameter(
                    name="expert_id",
                    type="string",
                    description="Expert to delegate to.",
                    required=True,
                    enum=list(EXPERT_IDS),
                ),
                ToolParameter(
                    name="brief",
                    type="string",
                    description="Self-contained task description (no conversation context needed).",
                    required=True,
                ),
                ToolParameter(
                    name="task_data",
                    type="string",
                    description="Optional JSON data the expert needs (e.g. grading results).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        expert_id = str(kwargs.get("expert_id") or "").strip()
        if expert_id not in EXPERT_IDS:
            return ToolResult(
                content=f"Error: expert_id 必须是 {', '.join(EXPERT_IDS)} 之一。",
                success=False,
            )
        brief = str(kwargs.get("brief") or "").strip()
        if not brief:
            return ToolResult(content="Error: brief 必填（自包含任务描述）。", success=False)
        task_data = str(kwargs.get("task_data") or "").strip()
        card = load_expert_card(expert_id)
        if not card:
            return ToolResult(content=f"Error: 找不到专家卡 {expert_id}。", success=False)
        system = (
            f"{card}\n\n"
            "你现在只处理这一次委派任务，不进入完整对话。"
            "按你的专家规则输出结构化结论给总控。"
        )
        user = f"委派任务：{brief}\n\n"
        if task_data:
            user += f"任务数据：\n{task_data}\n\n"
        user += "请输出你的结论（简洁、可被总控直接采用）。"
        try:
            from deeptutor.services.llm import complete

            raw = await complete(user, system_prompt=system)
        except Exception as e:
            return ToolResult(content=f"专家 {expert_id} 调用失败: {e}", success=False)
        content = f"专家 {expert_id} 结论：\n{raw}"
        return ToolResult(
            content=content,
            metadata={"delegate": {"expert": expert_id, "result": raw}},
        )


__all__ = ["DelegateExpertTool", "load_expert_card", "EXPERT_IDS"]
```

（`parents[1]` 从 `tools/` 上两级到 `deeptutor/`，再拼 skill 路径。若实际路径不符，implementer 校正 `EXPERTS_DIR`。）

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_delegate_expert_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/delegate_expert_tool.py tests/tools/test_delegate_expert_tool.py
git commit -m "feat: delegate_to_expert 工具 (专家卡委派, 上下文隔离)"
```

---

### Task 2: 注册 `delegate_to_expert`（4 处 + always_on）

**Files:**
- Modify: `deeptutor/tools/builtin/__init__.py`
- Modify: `deeptutor/agents/_shared/tool_composition.py`

- [ ] **Step 1: 注册 4 处**（在 kb_search 之后）

`deeptutor/tools/builtin/__init__.py`：

```python
# 1) import（kb_search_tool import 之后）
from deeptutor.tools.delegate_expert_tool import DelegateExpertTool

# 2) BUILTIN_TOOL_TYPES 列表（KbSearchTool 之后）
    DelegateExpertTool,

# 3) CONFIGURABLE_BUILTIN_TOOL_NAMES 元组（"kb_search" 之后）
    "delegate_to_expert",

# 4) __all__ 列表（"KbSearchTool" 之后）
    "DelegateExpertTool",
```

`deeptutor/agents/_shared/tool_composition.py`（always_on tuple，`"kb_search"` 之后）：

```python
        "delegate_to_expert",
```

- [ ] **Step 2: 验证注册 + 测试**

Run:
```powershell
python -c "from deeptutor.tools.builtin import BUILTIN_TOOL_TYPES, CONFIGURABLE_BUILTIN_TOOL_NAMES, __all__; print('DelegateExpertTool' in [t.__name__ for t in BUILTIN_TOOL_TYPES], 'delegate_to_expert' in CONFIGURABLE_BUILTIN_TOOL_NAMES, 'DelegateExpertTool' in __all__)"
```
Expected: `True True True`

Run: `python -m pytest tests/tools/test_delegate_expert_tool.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py
git commit -m "chore: 注册 delegate_to_expert (builtin 4 处 + always_on)"
```

---

### Task 3: PERSONA 加「总控委派」节

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`（源）+ 副本

- [ ] **Step 1: PERSONA 加「总控委派」节（知识检索节后）**

```markdown
## 总控委派（专人专事，上下文隔离）

需要专家深度处理时，用 `delegate_to_expert` 委派，**不把对话历史全量塞给专家**：
- 委派 brief 必须**自包含**（任务 + 必要数据），专家只见 brief，不见会话历史。
- 评分/检索等工具结果先由总控调好放进 `task_data`，再委派给专家分析。
- 专家返回结论后，总控汇总组织反馈给用户（专家不直接对用户说话）。
- 委派决策（派给谁、为什么）可记入 trace-log 供审计。
```

- [ ] **Step 2: 同步副本 + 校验 + Commit**

Run（PowerShell）:
```powershell
Copy-Item deeptutor/services/persona/presets/annotation-coach/PERSONA.md data/user/workspace/personas/annotation-coach/PERSONA.md -Force
python -c "from pathlib import Path; p=Path('deeptutor/services/persona/presets/annotation-coach/PERSONA.md'); t=p.read_text(encoding='utf-8'); assert t.startswith('---') and '总控委派' in t; print('OK')"
```
Expected: `OK`

```bash
git add deeptutor/services/persona/presets/annotation-coach/PERSONA.md
git commit -m "docs: PERSONA 加总控委派节 (delegate_to_expert 上下文隔离规则)"
```

---

### Task 4: 冒烟验证

- [ ] **Step 1: 真实 LLM 委派冒烟**

Run（PowerShell `$env:PYTHONIOENCODING="utf-8"`、`$env:PYTHONPATH=<项目根>`）：

```python
import asyncio
from deeptutor.tools.delegate_expert_tool import DelegateExpertTool

async def main():
    tool = DelegateExpertTool()
    r = await tool.execute(
        expert_id="grading_expert",
        brief="评测标注结果，给出 readiness 判定",
        task_data='{"f1": 0.83, "error_pattern": ["边界过紧"]}',
    )
    print("委派:", r.success)
    print(r.content[:300])

asyncio.run(main())
```

Expected: 委派成功，返回批改专家基于 F1=0.83 的 readiness 结论（应含 advance_with_caution 之类）。

- [ ] **Step 2: 收尾**

冒烟通过即完成 Phase 1。分管 agent 独立 AgentLoop + 全量受限工具集为后续 Phase。
