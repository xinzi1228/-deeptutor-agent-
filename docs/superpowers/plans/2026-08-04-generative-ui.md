# 生成式 UI 实施计划（quiz_card 练习卡片）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 agent 出题时输出可交互练习卡片（题目+选项+点击即时对错反馈），通过 `render_ui` 工具 + 扩展 `ChatChartCard` 落地到现有 `metadata.chart` 通道。借鉴 AG-UI structured-message 思想，零框架依赖。

**Architecture:** 后端 `render_ui` 工具（校验组件 JSON → 返回 `metadata.chart`）；前端 `ChatChartCard` 加 `quiz_card` 类型（本地判断对错）；PERSONA 教 Coach 出题时用。

**Tech Stack:** Python FastAPI, Next.js, react-i18next。

**Spec:** `docs/specs/generative-ui-design.md`（已提交 `cb947f08`）

---

### Task 1: 后端 `render_ui` 工具

**Files:**
- Create: `deeptutor/tools/render_ui_tool.py`
- Modify: `deeptutor/tools/builtin/__init__.py`（注册 + import）
- Modify: `deeptutor/agents/_shared/tool_composition.py`（always_on）
- Test: `tests/tools/test_render_ui_tool.py`

- [ ] **Step 1: 读现有工具注册模式**

Read:
1. `deeptutor/tools/teaching_flow_tool.py` — a tool implementation to mirror (BaseTool, get_definition, execute, ToolResult)
2. `deeptutor/tools/builtin/__init__.py` — how tools are registered (import + BUILTIN_TOOL_TYPES + __all__ + class definition). Find where `TeachingFlowTool`/`AnnotationCheckTool` are defined/registered.
3. `deeptutor/agents/_shared/tool_composition.py` — the always_on tuple (add "render_ui" there)

- [ ] **Step 2: 写失败测试**

Create `tests/tools/test_render_ui_tool.py`:

```python
"""render_ui tool — validate structured component JSON → metadata.chart."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_quiz_card_valid():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    component = {
        "type": "quiz_card",
        "data": {
            "question": "两个框完全不重叠时 IOU 是多少？",
            "options": ["0", "0.5", "1"],
            "answer_index": 0,
            "explanation": "无交集 → IOU=0",
        },
    }
    import json
    result = await RenderUiTool().execute(component=json.dumps(component, ensure_ascii=False))
    assert result.success
    assert result.metadata["chart"]["type"] == "quiz_card"
    assert result.metadata["chart"]["data"]["answer_index"] == 0


@pytest.mark.asyncio
async def test_missing_fields_fails():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    import json
    result = await RenderUiTool().execute(component=json.dumps({"type": "quiz_card", "data": {"question": "x"}}))
    assert not result.success


@pytest.mark.asyncio
async def test_unknown_type_fails():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    import json
    result = await RenderUiTool().execute(component=json.dumps({"type": "unknown_card", "data": {}}))
    assert not result.success
```

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_render_ui_tool.py -v 2>&1 | Select-Object -Last 6`
Expected: FAIL (ImportError)

- [ ] **Step 3: 实现 render_ui_tool.py**

Create `deeptutor/tools/render_ui_tool.py`:

```python
"""RenderUiTool — coach tool to render an interactive teaching component.

The coach passes a structured component JSON (AG-UI structured-message style);
the tool validates it and returns it as ``metadata.chart`` so the existing
ChatChartCard channel renders it as an interactive card (e.g. quiz_card).
"""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult


def validate_component(component: Any) -> dict[str, Any] | None:
    """Validate a component dict; returns the normalized dict or None."""
    if not isinstance(component, dict):
        return None
    ctype = str(component.get("type") or "")
    data = component.get("data")
    if not isinstance(data, dict):
        return None
    if ctype == "quiz_card":
        if not isinstance(data.get("question"), str) or not data["question"].strip():
            return None
        options = data.get("options")
        if not isinstance(options, list) or len(options) < 2:
            return None
        answer_index = data.get("answer_index")
        if not isinstance(answer_index, int) or not (0 <= answer_index < len(options)):
            return None
        return {"type": "quiz_card", "data": {
            "question": data["question"].strip(),
            "options": [str(o) for o in options],
            "answer_index": answer_index,
            "explanation": str(data.get("explanation") or "").strip() or None,
            "knowledge_point": str(data.get("knowledge_point") or "").strip() or None,
        }}
    return None  # unknown type


class RenderUiTool(BaseTool):
    """Render an interactive teaching component (e.g. quiz_card)."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="render_ui",
            description=(
                "Render an interactive teaching component as a card in the chat. "
                "Pass a structured component JSON. Supported types:\n"
                "- quiz_card: {\"type\":\"quiz_card\",\"data\":{\"question\":\"...\","
                "\"options\":[\"A\",\"B\",...],\"answer_index\":0,\"explanation\":\"...\","
                "\"knowledge_point\":\"...\"}} — renders a clickable quiz with "
                "instant right/wrong feedback."
            ),
            parameters=[
                ToolParameter(
                    name="component",
                    type="string",
                    description="Component JSON (see description for schema).",
                    required=True,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        raw = kwargs.get("component", "{}")
        try:
            component = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as e:
            return ToolResult(content=f"组件 JSON 解析失败: {e}", success=False)
        validated = validate_component(component)
        if validated is None:
            return ToolResult(
                content=(
                    "组件 JSON 格式不合法。quiz_card 需要 type='quiz_card' 且 data 含 "
                    "question/options(≥2)/answer_index(合法下标)。"
                ),
                success=False,
            )
        return ToolResult(content="已生成练习卡片（见上方）。", metadata={"chart": validated})


__all__ = ["RenderUiTool", "validate_component"]
```

- [ ] **Step 4: 注册到 builtin + always_on**

In `deeptutor/tools/builtin/__init__.py`:
1. Add the import (find where other tools like `TeachingFlowTool` are imported)
2. Add `RenderUiTool` to the registration (BUILTIN_TOOL_TYPES / __all__ — read how the file registers tools, e.g. the CronTool at line 1498 is defined inline; if tools are defined inline, add a similar class or import from render_ui_tool and register)

In `deeptutor/agents/_shared/tool_composition.py`:
- Add `"render_ui"` to the always_on tuple (near "teaching_flow")

NOTE: read both files carefully. The builtin/__init__.py may define tools inline (CronTool at 1498) or import them. If inline-style, add `from deeptutor.tools.render_ui_tool import RenderUiTool` and register its name. Match the existing pattern exactly.

- [ ] **Step 5: 运行测试确认通过**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_render_ui_tool.py -v 2>&1 | Select-Object -Last 6`
Expected: PASS.

- [ ] **Step 6: Ruff + Commit**

Ruff: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m ruff check deeptutor/tools/render_ui_tool.py deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py tests/tools/test_render_ui_tool.py`

```bash
git add deeptutor/tools/render_ui_tool.py deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py tests/tools/test_render_ui_tool.py
git commit -m "feat: render_ui 工具 (校验组件JSON→metadata.chart, 复用chat卡片通道)"
```

---

### Task 2: 前端 ChatChartCard 扩展 quiz_card

**Files:**
- Modify: `web/components/chat/home/ChatChartCard.tsx`

- [ ] **Step 1: 读现有 ChatChartCard**

Read `web/components/chat/home/ChatChartCard.tsx` (124 lines). It has a `ChartData` union (scorecard/radar/progress/graph) + per-type render functions.

- [ ] **Step 2: 加 quiz_card 类型**

Edit the file:
1. Add `import { useState } from "react";` at top (currently only useEffect/useRef imported)
2. Add to `ChartData` union:
```ts
| { type: "quiz_card"; data: { question: string; options: string[]; answer_index: number; explanation?: string | null; knowledge_point?: string | null } }
```
3. Add a `QuizCard` component + render branch:

```tsx
function QuizCard({ data }: { data: { question: string; options: string[]; answer_index: number; explanation?: string | null; knowledge_point?: string | null } }) {
  const [selected, setSelected] = useState<number | null>(null);
  const answered = selected !== null;
  return (
    <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      {data.knowledge_point && (
        <div className="mb-1 text-[10px] uppercase tracking-wide text-[var(--muted-foreground)]">
          {data.knowledge_point}
        </div>
      )}
      <div className="mb-2 text-sm font-medium text-[var(--foreground)]">{data.question}</div>
      <div className="space-y-1.5">
        {data.options.map((opt, idx) => {
          const isCorrect = idx === data.answer_index;
          const isSelected = idx === selected;
          let style = "border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--muted)]";
          if (answered) {
            if (isCorrect) style = "border-emerald-500/40 bg-emerald-500/10 text-emerald-600";
            else if (isSelected) style = "border-rose-500/40 bg-rose-500/10 text-rose-600";
            else style = "border-[var(--border)] text-[var(--muted-foreground)] opacity-50";
          }
          return (
            <button
              key={idx}
              type="button"
              onClick={() => setSelected(idx)}
              disabled={answered}
              className={`w-full rounded-lg border bg-[var(--card)] px-3 py-1.5 text-left text-xs transition-colors ${style}`}
            >
              <span className="font-semibold">{String.fromCharCode(65 + idx)}.</span> {opt}
              {answered && isCorrect && <span className="ml-1 text-emerald-600">✓</span>}
              {answered && isSelected && !isCorrect && <span className="ml-1 text-rose-600">✗</span>}
            </button>
          );
        })}
      </div>
      {answered && data.explanation && (
        <div className="mt-2 rounded bg-[var(--muted)]/40 px-3 py-2 text-xs text-[var(--muted-foreground)]">
          {data.explanation}
        </div>
      )}
    </div>
  );
}
```

And in the main component add before `return null`:
```tsx
if (chart.type === "quiz_card") {
  return <QuizCard data={chart.data} />;
}
```

- [ ] **Step 3: tsc 验证**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors

- [ ] **Step 4: Commit**

```bash
git add web/components/chat/home/ChatChartCard.tsx
git commit -m "feat: ChatChartCard 支持 quiz_card 可交互练习卡片"
```

---

### Task 3: PERSONA + 验证

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` (+ sync workspace copy)

- [ ] **Step 1: PERSONA 提示**

In `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` 交互规范 section, add:

```markdown
- 出练习题（选择/判断）时用 `render_ui` 输出练习卡片（component JSON: {"type":"quiz_card","data":{"question":"...","options":["A","B","C","D"],"answer_index":0,"explanation":"...","knowledge_point":"..."}}），学生点击选项即时看到对错反馈。
```

Sync to `data/user/workspace/personas/annotation-coach/PERSONA.md`.

- [ ] **Step 2: Commit PERSONA**

```bash
git add deeptutor/services/persona/presets/annotation-coach/PERSONA.md
git commit -m "feat: PERSONA 教 Coach 出题用 render_ui 输出练习卡片"
```

- [ ] **Step 3: 后端测试**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_render_ui_tool.py -q 2>&1 | Select-Object -Last 3`
Expected: PASS.

- [ ] **Step 4: 前端 tsc + build**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors; `Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY -ErrorAction SilentlyContinue; npx next build 2>&1 | Select-Object -Last 4` → succeeds

- [ ] **Step 5: Playwright 冒烟**

With backend (8001) + frontend (3782):
1. Restart backend (pick up render_ui + PERSONA)
2. Restart frontend (pick up ChatChartCard)
3. In chat, ask Coach "出一道 IOU 的选择题" (or a question that triggers a quiz)
4. Coach should call render_ui → a quiz_card appears with options
5. Click an option → instant right/wrong feedback + explanation
6. Screenshot for record

- [ ] **Step 6: 提交修复（如有）**

If smoke found issues, fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §4 后端 render_ui → Task 1
- §5 前端 quiz_card → Task 2
- §6 PERSONA → Task 3
- §7 测试 → Task 3
✅ 全覆盖

**2. Placeholder scan:** 所有步骤含具体代码/命令。Task 1 Step 4 明确"读文件后匹配现有注册模式"。✅

**3. Type consistency:** `validate_component` 返回 `{type, data}` 结构 Task 1 定义，Task 2 前端 ChartData union 一致（question/options/answer_index/explanation/knowledge_point）；`render_ui` 返回 `metadata.chart` 与 ChatMessages 读取的 `toolMeta.chart` 一致。✅

**已知风险（沿用 spec §9）：**
1. Coach 是否稳定调用 render_ui——PERSONA 提示；不调用退化为文本题目
2. 组件 JSON 解析失败 → 工具报错，Coach 重试
3. 前端未知 type 静默忽略（安全）
