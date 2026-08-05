# 议题⑤ route_input 输入分诊 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `route_input` 工具，把用户输入结构化分类（task_start/answer_submit/question_confirm/question_deep/confuse/off_topic/greeting），让 Coach 按类分支（confuse→ask_user 澄清、off_topic→简短拉回）。

**Architecture:** 复用 `BaseTool` 模式（同 `render_ui_tool.py`）。`execute` 调 `deeptutor.services.llm.complete` 让 LLM 分类，输出结构化 JSON；`parse_route_result` 纯函数解析+校验+容错回退（可单测，不依赖 LLM）。结果放 `metadata.route`。

**Tech Stack:** Python 3.11+ / pytest-asyncio / DeepTutor BaseTool 协议

**依赖设计文档:** `docs/superpowers/specs/2026-08-05-input-routing-design.md`

---

## File Structure

- Create: `deeptutor/tools/route_input_tool.py` — `RouteInputTool` + `parse_route_result` 纯函数 + `CATEGORIES` 常量 + `_build_prompt`
- Create: `tests/tools/test_route_input.py` — 纯函数解析测试 + execute mock-LLM 测试
- Modify: `deeptutor/tools/builtin/__init__.py` — 4 处注册（import / BUILTIN_TOOL_TYPES / CONFIGURABLE_BUILTIN_TOOL_NAMES / __all__）
- Modify: `deeptutor/agents/_shared/tool_composition.py` — always_on tuple 加 `"route_input"`
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` + workspace 副本 — 「输入分诊」节

---

### Task 1: `route_input_tool.py`（纯函数解析 + 工具类）

**Files:**
- Create: `deeptutor/tools/route_input_tool.py`
- Test: `tests/tools/test_route_input.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_route_input.py
import pytest

from deeptutor.tools.route_input_tool import (
    CATEGORIES,
    RouteInputTool,
    parse_route_result,
)


def test_categories_include_all_branches():
    assert {"task_start", "answer_submit", "question_confirm", "question_deep",
            "confuse", "off_topic", "greeting"} == set(CATEGORIES)


def test_parse_valid_result():
    r = parse_route_result(
        '{"category":"confuse","confidence":0.87,"clarify_options":["开始新练习","查看进度"],'
        '"short_reply_hint":"听起来你有点不确定？","flag_struggle":true}'
    )
    assert r["category"] == "confuse"
    assert r["confidence"] == pytest.approx(0.87)
    assert r["clarify_options"] == ["开始新练习", "查看进度"]
    assert r["flag_struggle"] is True


def test_parse_invalid_json_falls_back_to_confuse():
    r = parse_route_result("not-json")
    assert r["category"] == "confuse"
    assert r["confidence"] == 0.0
    assert r["clarify_options"] == []


def test_parse_unknown_category_falls_back():
    r = parse_route_result('{"category":"hacking"}')
    assert r["category"] == "confuse"


def test_parse_confidence_clamped_to_01():
    assert parse_route_result('{"category":"off_topic","confidence":5}')["confidence"] == 1.0
    assert parse_route_result('{"category":"off_topic","confidence":-2}')["confidence"] == 0.0


def test_parse_options_capped_and_deduped():
    r = parse_route_result('{"category":"confuse","clarify_options":["A","A","B","C","D","E"]}')
    assert r["clarify_options"] == ["A", "B", "C", "D"]


async def test_execute_calls_llm_and_returns_route(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        return '{"category":"greeting","confidence":0.9}'

    monkeypatch.setattr(llm_mod, "complete", fake_complete)
    tool = RouteInputTool()
    result = await tool.execute(user_message="你好")
    assert result.success is True
    assert result.metadata["route"]["category"] == "greeting"


async def test_execute_empty_message_fails():
    tool = RouteInputTool()
    result = await tool.execute(user_message="   ")
    assert result.success is False


async def test_execute_llm_error_falls_back(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def broken_complete(prompt, system_prompt=None, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm_mod, "complete", broken_complete)
    tool = RouteInputTool()
    result = await tool.execute(user_message="hello")
    assert result.success is True
    assert result.metadata["route"]["category"] == "confuse"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_route_input.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.tools.route_input_tool'`

- [ ] **Step 3: Write minimal implementation**

```python
# deeptutor/tools/route_input_tool.py
"""RouteInputTool — classify user input intent and branch coach behaviour.

The coach calls this BEFORE answering: it returns a structured category so the
coach can branch (confuse -> ask_user clarify; off_topic -> short reply + pull
back; question_confirm -> answer directly; etc.). The LLM's JSON output is
parsed and validated by ``parse_route_result`` (a pure function, unit-testable
without an LLM).
"""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

CATEGORIES = (
    "task_start",
    "answer_submit",
    "question_confirm",
    "question_deep",
    "confuse",
    "off_topic",
    "greeting",
)

_FALLBACK: dict[str, Any] = {
    "category": "confuse",
    "confidence": 0.0,
    "clarify_options": [],
    "short_reply_hint": "",
    "flag_struggle": False,
    "requires_confirmation": False,
}


def parse_route_result(raw: str) -> dict[str, Any]:
    """Parse and validate the LLM's JSON classification; fall back to confuse."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return dict(_FALLBACK)
    if not isinstance(data, dict):
        return dict(_FALLBACK)
    category = str(data.get("category") or "").strip()
    if category not in CATEGORIES:
        category = _FALLBACK["category"]
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    confidence = max(0.0, min(1.0, float(confidence)))
    options = data.get("clarify_options")
    if not isinstance(options, list):
        options = []
    seen: list[str] = []
    for o in options:
        s = str(o).strip()
        if s and s not in seen:
            seen.append(s)
        if len(seen) >= 4:
            break
    return {
        "category": category,
        "confidence": confidence,
        "clarify_options": seen,
        "short_reply_hint": str(data.get("short_reply_hint") or "").strip(),
        "flag_struggle": bool(data.get("flag_struggle")),
        "requires_confirmation": bool(data.get("requires_confirmation")),
    }


def _build_prompt(message: str, recent_context: str) -> str:
    return (
        "Classify the student's latest message for an annotation-coach tutor.\n"
        "Choose EXACTLY ONE category:\n"
        "- task_start: wants to start/continue annotation practice\n"
        "- answer_submit: submitting annotation result / answer\n"
        "- question_confirm: one-line confirm-style question (e.g. \"X is right?\")\n"
        "- question_deep: asking about a knowledge point or standard\n"
        "- confuse: incomplete / vague input that needs clarification\n"
        "- off_topic: unrelated to annotation teaching\n"
        "- greeting: small talk / hello\n"
        "Return ONLY JSON:\n"
        '{"category":"<one of the above>","confidence":0.0-1.0,'
        '"clarify_options":["option1","option2"],"short_reply_hint":"<for off_topic/confuse, 1 short line>",'
        '"flag_struggle":false,"requires_confirmation":false}\n'
        "For confuse, give 2-4 clarify_options as candidate choices.\n\n"
        f"Recent context:\n{recent_context}\n\n"
        f"Student message:\n{message}"
    )


class RouteInputTool(BaseTool):
    """Classify user input intent to route the coach's response."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="route_input",
            description=(
                "Classify the user's input intent BEFORE responding. Returns a structured "
                "category: task_start / answer_submit / question_confirm / question_deep / "
                "confuse / off_topic / greeting. For confuse it also returns candidate "
                "clarify_options to present via ask_user. For off_topic it returns a short "
                "reply hint to pull the learner back to annotation practice."
            ),
            parameters=[
                ToolParameter(
                    name="user_message",
                    type="string",
                    description="The user's latest message.",
                    required=True,
                ),
                ToolParameter(
                    name="recent_context",
                    type="string",
                    description="Optional recent 1-2 turns of context (max ~2000 chars).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        message = str(kwargs.get("user_message") or "").strip()
        if not message:
            return ToolResult(content="Error: user_message is required.", success=False)
        recent_context = str(kwargs.get("recent_context") or "")[:2000]
        prompt = _build_prompt(message, recent_context)
        try:
            from deeptutor.services.llm import complete

            raw = await complete(prompt, system_prompt="You are a teaching-assistant intent router.")
        except Exception:
            raw = ""
        route = parse_route_result(raw)
        content = (
            f"Input routed as: {route['category']} "
            f"(confidence={route['confidence']:.2f})."
        )
        return ToolResult(content=content, metadata={"route": route})


__all__ = ["RouteInputTool", "parse_route_result", "CATEGORIES"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_route_input.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/route_input_tool.py tests/tools/test_route_input.py
git commit -m "feat: route_input 工具 (意图分诊, 结构化分类+容错回退)"
```

---

### Task 2: 注册 `route_input`（4 处 + always_on）

**Files:**
- Modify: `deeptutor/tools/builtin/__init__.py`
- Modify: `deeptutor/agents/_shared/tool_composition.py`

- [ ] **Step 1: 注册 4 处**

`deeptutor/tools/builtin/__init__.py`（参照 render_ui 的注册位置）：

```python
# 1) import 区（render_ui 的 import 附近，约 L39）
from deeptutor.tools.route_input_tool import RouteInputTool

# 2) BUILTIN_TOOL_TYPES 列表（约 L1623，RenderUiTool 附近）
    RouteInputTool,

# 3) CONFIGURABLE_BUILTIN_TOOL_NAMES 元组（约 L1699）
    "route_input",

# 4) __all__ 列表（约 L1761，RenderUiTool 附近）
    "RouteInputTool",
```

`deeptutor/agents/_shared/tool_composition.py`（always_on tuple，约 L190，`render_ui` 之后）：

```python
        "route_input",
```

- [ ] **Step 2: 跑注册自检 + 相关测试**

Run: `python test_registration.py`
Expected: OK，route_input 已注册

Run: `python -m pytest tests/tools/test_route_input.py tests/test_registration.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py
git commit -m "chore: 注册 route_input (builtin 4 处 + always_on)"
```

---

### Task 3: PERSONA 加「输入分诊」节

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`（源）
- Modify: `data/user/workspace/personas/annotation-coach/PERSONA.md`（运行时副本，如存在）

- [ ] **Step 1: 在 PERSONA.md「专家协作」节前加入分诊节**

```markdown
## 输入分诊（每次回应前）

每次用户发消息，先调用 `route_input` 分类，再按类分支：
- `confuse`（不完整/模糊）→ `ask_user` 弹候选选项 + 自由输入；追问上限 2 轮，
  仍不清则回到当前教学流程引导。
- `off_topic`（无关）→ 简短回应 1-2 句 + 拉回："我们可以继续标注练习，你想练哪个任务？"
- `question_confirm`（一句话确认疑问）→ 直接回答 + 问要不要展开。
- `question_deep`（问知识点/规范）→ 走 standards 规范库检索 + 引用溯源。
- `task_start` → teaching_flow 引导 / get_annotation_task 出题。
- `answer_submit` → annotation_check 评分。
- `greeting` → 简短回应 + 询问学习目标。

绝不猜测用户意图；意图不明确时必先澄清（NEVER GUESS, ALWAYS ASK）。
```

- [ ] **Step 2: 同步运行时副本（若存在）**

Run（PowerShell）:
```powershell
Copy-Item deeptutor/services/persona/presets/annotation-coach/PERSONA.md data/user/workspace/personas/annotation-coach/PERSONA.md -Force
```

- [ ] **Step 3: 校验 persona 一致性 + Commit**

Run: `python check_personas.py`
Expected: 无一致性错误

```bash
git add deeptutor/services/persona/presets/annotation-coach/PERSONA.md
git commit -m "docs: PERSONA 加输入分诊节 (route_input 分支规则)"
```

---

### Task 4: 冒烟验证

**Files:** 无新增（运行验证）

- [ ] **Step 1: 起后端 + 前端**

Run: `start_all.bat`（后端 8001 + 前端 3782）

- [ ] **Step 2: 对话冒烟**

在后端控制台/CLI 或前端 Chat 发：
`"这个怎么弄？"`（confuse）
Expected: Coach 弹候选选项（ask_user 卡片）+ 自由输入

再发：`"你好"`（greeting）
Expected: 简短回应 + 询问学习目标

- [ ] **Step 3: 记录结果并收尾**

确认冒烟通过后，如需调整 PERSONA 分支措辞则补 commit。
