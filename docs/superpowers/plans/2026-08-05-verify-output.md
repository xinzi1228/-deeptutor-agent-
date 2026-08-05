# 议题⑥ verify_output 输出质检 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `verify_output` 工具，让 Coach 在关键输出（评分结论/规范断言/知识性解释）前先 LLM 自检（编造来源/角色漂移/AI 标识/证据缺失），检出问题按 `revision_advice` 修正重出。

**Architecture:** 复用 `BaseTool` 模式（同 `route_input_tool.py`）。`execute` 调 `deeptutor.services.llm.complete` 让 LLM 做质检，输出结构化 verdict；`parse_verify_result` 纯函数解析+校验+容错回退（缺省 PASS，保守不误拦）。结果放 `metadata.verify`。

**Tech Stack:** Python 3.11+ / pytest-asyncio / DeepTutor BaseTool 协议

**依赖设计文档:** `docs/superpowers/specs/2026-08-05-output-guardrails-design.md`

---

## File Structure

- Create: `deeptutor/tools/verify_output_tool.py` — `VerifyOutputTool` + `parse_verify_result` 纯函数 + `_build_prompt`
- Create: `tests/tools/test_verify_output_tool.py` — 纯函数解析测试 + execute mock-LLM 测试
- Modify: `deeptutor/tools/builtin/__init__.py` — 4 处注册（import / BUILTIN_TOOL_TYPES / CONFIGURABLE_BUILTIN_TOOL_NAMES / __all__）
- Modify: `deeptutor/agents/_shared/tool_composition.py` — always_on tuple 加 `"verify_output"`
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` + workspace 副本 — 「输出护栏」节

---

### Task 1: `verify_output_tool.py`（纯函数解析 + 工具类）

**Files:**
- Create: `deeptutor/tools/verify_output_tool.py`
- Test: `tests/tools/test_verify_output_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_verify_output_tool.py
import pytest

from deeptutor.tools.verify_output_tool import VerifyOutputTool, parse_verify_result


def test_parse_valid_pass():
    r = parse_verify_result(
        '{"fabrication_leak":false,"role_drift":false,"ai_label_missing":false,'
        '"evidence_missing":[],"pass":true,"revision_advice":""}'
    )
    assert r["pass"] is True
    assert r["fabrication_leak"] is False
    assert r["evidence_missing"] == []


def test_parse_detects_issues():
    r = parse_verify_result(
        '{"fabrication_leak":true,"role_drift":false,"ai_label_missing":true,'
        '"evidence_missing":["目标检测遮挡阈值50%无规范依据"],"pass":false,'
        '"revision_advice":"请标注来源或改为通用建议"}'
    )
    assert r["pass"] is False
    assert r["fabrication_leak"] is True
    assert r["evidence_missing"] == ["目标检测遮挡阈值50%无规范依据"]
    assert r["revision_advice"] == "请标注来源或改为通用建议"


def test_parse_invalid_json_defaults_pass():
    r = parse_verify_result("not-json")
    assert r["pass"] is True
    assert r["fabrication_leak"] is False
    assert r["evidence_missing"] == []


def test_parse_explicit_pass_false_wins():
    # LLM 明确标 pass=false 即使无具体 issue 也应保留 false
    r = parse_verify_result('{"pass":false}')
    assert r["pass"] is False


def test_parse_evidence_capped():
    r = parse_verify_result('{"evidence_missing":["a","b","c","d","e","f","g"]}')
    assert len(r["evidence_missing"]) == 6


async def test_execute_calls_llm_and_returns_verdict(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        return '{"fabrication_leak":false,"pass":true}'

    monkeypatch.setattr(llm_mod, "complete", fake_complete)
    tool = VerifyOutputTool()
    result = await tool.execute(draft_answer="依据 GB/T 41867，遮挡目标需标注。")
    assert result.success is True
    assert result.metadata["verify"]["pass"] is True


async def test_execute_empty_draft_fails():
    tool = VerifyOutputTool()
    result = await tool.execute(draft_answer="   ")
    assert result.success is False


async def test_execute_llm_error_defaults_pass(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def broken_complete(prompt, system_prompt=None, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm_mod, "complete", broken_complete)
    tool = VerifyOutputTool()
    result = await tool.execute(draft_answer="hello")
    assert result.success is True
    assert result.metadata["verify"]["pass"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_verify_output_tool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.tools.verify_output_tool'`

- [ ] **Step 3: Write minimal implementation**

```python
# deeptutor/tools/verify_output_tool.py
"""VerifyOutputTool — coach pre-output quality self-check.

The coach calls this BEFORE emitting a high-risk answer (grading conclusions,
standard citations, knowledge assertions). The LLM audits the draft and returns
a structured verdict; ``parse_verify_result`` validates it with a conservative
PASS fallback (never over-block). If issues are found, the coach must revise
per ``revision_advice`` and re-emit.
"""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

_FALLBACK: dict[str, Any] = {
    "fabrication_leak": False,
    "role_drift": False,
    "ai_label_missing": False,
    "evidence_missing": [],
    "pass": True,
    "revision_advice": "",
}


def parse_verify_result(raw: str) -> dict[str, Any]:
    """Parse and validate the LLM's audit verdict; conservative PASS fallback."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return dict(_FALLBACK)
    if not isinstance(data, dict):
        return dict(_FALLBACK)
    fabrication = bool(data.get("fabrication_leak"))
    role = bool(data.get("role_drift"))
    label = bool(data.get("ai_label_missing"))
    evidence = data.get("evidence_missing")
    if not isinstance(evidence, list):
        evidence = []
    evidence = [str(e) for e in evidence if str(e).strip()][:6]
    issues = fabrication or role or label or bool(evidence)
    # 显式 pass=false 优先；未显式给 pass 时按 issues 推断
    if "pass" in data:
        passed = bool(data.get("pass"))
    else:
        passed = not issues
    return {
        "fabrication_leak": fabrication,
        "role_drift": role,
        "ai_label_missing": label,
        "evidence_missing": evidence,
        "pass": passed,
        "revision_advice": str(data.get("revision_advice") or "").strip(),
    }


def _build_prompt(draft: str, claims: str) -> str:
    return (
        "You are a strict output-quality auditor for an annotation-coach tutor.\n"
        "Audit the draft answer below. Flag:\n"
        "- fabrication_leak: invented standards/specs/scores/sources not in the knowledge base\n"
        "- role_drift: answer leaves the annotation-coach role\n"
        "- ai_label_missing: lacks a required AI-generated content label\n"
        "- evidence_missing: knowledge assertions (standards like GB/T, grading conclusions) "
        "without a citation marker like 〔规范: 文档§章节〕\n"
        "Return ONLY JSON:\n"
        '{"fabrication_leak":false,"role_drift":false,"ai_label_missing":false,'
        '"evidence_missing":["<specific missing citation>"],"pass":true|false,'
        '"revision_advice":"<short fix instruction if not pass, else empty>"}\n\n'
        f"Optional claims to verify:\n{claims}\n\n"
        f"Draft answer:\n{draft}"
    )


class VerifyOutputTool(BaseTool):
    """Audit a draft answer for fabrication/role/evidence issues before emitting."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="verify_output",
            description=(
                "Audit a draft answer BEFORE emitting a high-risk response (grading "
                "conclusion, standard citation, knowledge assertion). Returns a verdict: "
                "pass=true to emit, or issues (fabrication_leak / role_drift / "
                "ai_label_missing / evidence_missing) + revision_advice to fix and re-emit."
            ),
            parameters=[
                ToolParameter(
                    name="draft_answer",
                    type="string",
                    description="The draft answer text to audit.",
                    required=True,
                ),
                ToolParameter(
                    name="claims",
                    type="string",
                    description="Optional key assertions to verify (one per line).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        draft = str(kwargs.get("draft_answer") or "").strip()
        if not draft:
            return ToolResult(content="Error: draft_answer is required.", success=False)
        claims = str(kwargs.get("claims") or "").strip()
        prompt = _build_prompt(draft, claims)
        try:
            from deeptutor.services.llm import complete

            raw = await complete(prompt, system_prompt="You are a strict output quality auditor.")
        except Exception:
            raw = ""
        verdict = parse_verify_result(raw)
        if verdict["pass"]:
            content = "Verify PASS: 未发现编造/越界/缺依据问题，可输出。"
        else:
            issues = []
            if verdict["fabrication_leak"]:
                issues.append("编造来源")
            if verdict["role_drift"]:
                issues.append("角色漂移")
            if verdict["ai_label_missing"]:
                issues.append("缺 AI 标识")
            for e in verdict["evidence_missing"]:
                issues.append(f"缺依据: {e}")
            content = f"Verify ISSUES: {'; '.join(issues)}。{verdict['revision_advice']}"
        return ToolResult(content=content, metadata={"verify": verdict})


__all__ = ["VerifyOutputTool", "parse_verify_result"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_verify_output_tool.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/verify_output_tool.py tests/tools/test_verify_output_tool.py
git commit -m "feat: verify_output 工具 (输出质检, 防编造/越界/缺依据)"
```

---

### Task 2: 注册 `verify_output`（4 处 + always_on）

**Files:**
- Modify: `deeptutor/tools/builtin/__init__.py`
- Modify: `deeptutor/agents/_shared/tool_composition.py`

- [ ] **Step 1: 注册 4 处**

`deeptutor/tools/builtin/__init__.py`（route_input 之后）：

```python
# 1) import 区（route_input_tool import 之后）
from deeptutor.tools.verify_output_tool import VerifyOutputTool

# 2) BUILTIN_TOOL_TYPES 列表（RouteInputTool 之后）
    VerifyOutputTool,

# 3) CONFIGURABLE_BUILTIN_TOOL_NAMES 元组（"route_input" 之后）
    "verify_output",

# 4) __all__ 列表（"RouteInputTool" 之后）
    "VerifyOutputTool",
```

`deeptutor/agents/_shared/tool_composition.py`（always_on tuple，`"route_input"` 之后）：

```python
        "verify_output",
```

- [ ] **Step 2: 验证注册 + 测试**

Run:
```powershell
python -c "from deeptutor.tools.builtin import BUILTIN_TOOL_TYPES, CONFIGURABLE_BUILTIN_TOOL_NAMES, __all__; print('VerifyOutputTool' in [t.__name__ for t in BUILTIN_TOOL_TYPES], 'verify_output' in CONFIGURABLE_BUILTIN_TOOL_NAMES, 'VerifyOutputTool' in __all__)"
```
Expected: `True True True`

Run: `python -m pytest tests/tools/test_verify_output_tool.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py
git commit -m "chore: 注册 verify_output (builtin 4 处 + always_on)"
```

---

### Task 3: PERSONA 加「输出护栏」节

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`（源）
- Modify: `data/user/workspace/personas/annotation-coach/PERSONA.md`（运行时副本，如存在）

- [ ] **Step 1: 在 PERSONA.md「输入分诊」节后加「输出护栏」节**

```markdown
## 输出护栏（关键输出前自检）

涉及以下高风险输出时，**先调 `verify_output` 自检再输出**：
- 评分结论 / 成绩判定
- 规范/标准断言（引用 GB/T、COCO、VOC 等）
- 知识性解释（知识点、标注原则）

`verify_output` 检出问题时（编造来源/角色漂移/缺 AI 标识/缺依据），按 `revision_advice` **修正后重出**。

护栏规则：
- 绝不编造规范、标准、成绩、来源；无依据时明说"知识库未收录此内容"。
- 规范断言必须带引用 `〔规范: 文档§章节〕`。
- 不跳出标注教练角色。
- 输出含 AI 生成内容标识。
```

- [ ] **Step 2: 同步运行时副本（若存在）**

Run（PowerShell）:
```powershell
Copy-Item deeptutor/services/persona/presets/annotation-coach/PERSONA.md data/user/workspace/personas/annotation-coach/PERSONA.md -Force
```

- [ ] **Step 3: 校验 frontmatter 合法 + Commit**

Run:
```powershell
python -c "from pathlib import Path; p=Path('deeptutor/services/persona/presets/annotation-coach/PERSONA.md'); t=p.read_text(encoding='utf-8'); assert t.startswith('---') and '输出护栏' in t; print('OK')"
```
Expected: `OK`

```bash
git add deeptutor/services/persona/presets/annotation-coach/PERSONA.md
git commit -m "docs: PERSONA 加输出护栏节 (verify_output 自检规则)"
```

---

### Task 4: 冒烟验证

- [ ] **Step 1: 真实 LLM 冒烟**

写临时脚本（PowerShell 设 `$env:PYTHONIOENCODING="utf-8"`、`$env:PYTHONPATH=<项目根>`）：

```python
import asyncio
from deeptutor.tools.verify_output_tool import VerifyOutputTool

async def main():
    tool = VerifyOutputTool()
    cases = [
        "依据 GB/T 41867，遮挡超过50%的目标需标注。",           # 期望 pass 或 evidence ok
        "本任务成绩 98 分，达到优秀。",                          # 期望检出 evidence_missing（无依据）
        "这家餐厅很好吃，推荐去。",                              # 期望 role_drift
    ]
    for draft in cases:
        r = await tool.execute(draft_answer=draft)
        v = r.metadata["verify"]
        print(f"{draft[:20]!r:24} pass={v['pass']} fab={v['fabrication_leak']} role={v['role_drift']} evidence={v['evidence_missing']}")

asyncio.run(main())
```

Expected: 前 2 条按断言判定；第 3 条 role_drift=true（越界）。记录实际结果。

- [ ] **Step 2: 收尾**

冒烟通过即完成；如需调整 prompt 措辞则补 commit。
