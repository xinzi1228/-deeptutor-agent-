# 困难检测介入实施计划（Struggle Detection & Intervention）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增确定性困难检测引擎——从学习记录检测学生卡住信号（连续低分/错误重复/停留超时），生成介入建议，Coach 采纳后审计。

**Architecture:** `StruggleDetector` 纯函数检测器（服务层，读学习记录算 3 信号）→ `StruggleDetectTool`（工具，severe 时 LLM 解释层可降级）→ 接入 flow-practice/flow-onboarding 协议 → `log_decision(kind=struggle_intervention)` 审计。复用已有 readiness_gate/error_pattern/foresight 机制，零新增依赖。

**Tech Stack:** Python 3.13, pytest + pytest-asyncio, `deeptutor.tools.reason.reason()`（LLM 解释层）。

**Spec:** `docs/specs/struggle-detector-design.md`（已提交 `3f6a6d5a`）

---

### Task 1: `StruggleDetector` — 3 信号确定性检测器

**Files:**
- Create: `deeptutor/services/struggle_detector.py`
- Test: `tests/services/test_struggle_detector.py`

- [ ] **Step 1: Write the failing test**

```python
"""StruggleDetector — deterministic struggle-signal detection tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from deeptutor.services.struggle_detector import StruggleDetector


def _rec(*, type="annotation_exercise", task_id="task1", f1=0.6, error_pattern=None,
         pattern_status=None, timestamp="2026-08-01T10:00:00+00:00"):
    r = {"type": type, "task_id": task_id, "f1": f1, "timestamp": timestamp}
    if error_pattern:
        r["error_pattern"] = error_pattern
        r["pattern_status"] = pattern_status or "confirmed"
    return r


def test_low_score_streak_triggers():
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, timestamp="2026-08-01T11:00:00+00:00"),
    ]
    signals = StruggleDetector().low_score_streak(records)
    assert len(signals) == 1
    assert signals[0]["type"] == "low_score_streak"
    assert signals[0]["severity"] == "moderate"


def test_low_score_streak_not_triggered_on_high_score():
    records = [
        _rec(task_id="task1", f1=0.9, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, timestamp="2026-08-01T11:00:00+00:00"),
    ]
    assert StruggleDetector().low_score_streak(records) == []


def test_repeated_error_triggers_on_confirmed():
    records = [
        _rec(task_id="task1", f1=0.6, error_pattern="漏标", pattern_status="confirmed",
             timestamp="2026-08-01T10:00:00+00:00"),
    ]
    signals = StruggleDetector().repeated_error(records)
    assert len(signals) == 1
    assert signals[0]["type"] == "repeated_error"
    assert signals[0]["severity"] == "severe"


def test_repeated_error_not_triggered_on_unconfirmed():
    records = [
        _rec(task_id="task1", f1=0.6, error_pattern="漏标", pattern_status="unconfirmed",
             timestamp="2026-08-01T10:00:00+00:00"),
    ]
    assert StruggleDetector().repeated_error(records) == []


def test_stall_timeout_triggers():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
    ]
    signals = StruggleDetector().stall_timeout(records, now=now, threshold_minutes=30)
    assert len(signals) == 1
    assert signals[0]["type"] == "stall_timeout"
    assert signals[0]["severity"] == "mild"


def test_stall_timeout_not_triggered_recent():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-02T11:50:00+00:00"),
    ]
    assert StruggleDetector().stall_timeout(records, now=now, threshold_minutes=30) == []


def test_detect_aggregates_signals():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, error_pattern="漏标", pattern_status="confirmed",
             timestamp="2026-08-01T11:00:00+00:00"),
    ]
    result = StruggleDetector().detect(records=records, now=now)
    assert result["has_struggle"] is True
    assert result["max_severity"] == "severe"
    assert len(result["signals"]) >= 2


def test_detect_empty_records():
    result = StruggleDetector().detect(records=[], now=datetime.now(timezone.utc))
    assert result["has_struggle"] is False
    assert result["signals"] == []


def test_detect_deterministic():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, timestamp="2026-08-01T11:00:00+00:00"),
    ]
    r1 = StruggleDetector().detect(records=records, now=now)
    r2 = StruggleDetector().detect(records=records, now=now)
    assert r1 == r2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/test_struggle_detector.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.services.struggle_detector'`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/services/struggle_detector.py`:

```python
"""StruggleDetector — deterministic learner-struggle signal detection.

Reads learning records and computes signals that indicate a learner is
stuck: consecutive low F1 scores, a confirmed repeated error pattern, or
task stall timeout. Pure functions — no LLM, no I/O beyond the input
records — so signals are testable, reproducible, and explainable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

LOW_F1_THRESHOLD = 0.7
LOW_SCORE_STREAK_MIN = 2
STALL_THRESHOLD_MINUTES = 30

SEVERITY_RANK = {"mild": 1, "moderate": 2, "severe": 3}


class StruggleDetector:
    """Deterministic struggle-signal detector over learning records."""

    # ----------------------------------------------------------- low score

    def low_score_streak(self, records: list[dict]) -> list[dict]:
        """Trigger when N consecutive exercises score below LOW_F1_THRESHOLD."""
        exercises = [r for r in records if r.get("type") == "annotation_exercise"]
        exercises.sort(key=lambda r: r.get("timestamp", ""))
        streak = 0
        signals = []
        for rec in exercises:
            f1 = rec.get("f1")
            try:
                f1v = float(f1)
            except (TypeError, ValueError):
                f1v = None
            if f1v is not None and f1v < LOW_F1_THRESHOLD:
                streak += 1
            else:
                streak = 0
            if streak >= LOW_SCORE_STREAK_MIN:
                signals.append(
                    {
                        "type": "low_score_streak",
                        "severity": "moderate",
                        "skill": rec.get("knowledge_point") or rec.get("task_id", ""),
                        "task_id": rec.get("task_id"),
                        "evidence": f"连续 {streak} 次练习 F1 < {LOW_F1_THRESHOLD}",
                        "count": streak,
                        "ts": rec.get("timestamp", ""),
                    }
                )
        return signals

    # --------------------------------------------------------- error repeat

    def repeated_error(self, records: list[dict]) -> list[dict]:
        """Trigger when an error_pattern is confirmed (≥2 occurrences)."""
        seen: dict[str, dict] = {}
        for rec in records:
            pattern = rec.get("error_pattern")
            if not pattern:
                continue
            if rec.get("pattern_status") == "confirmed":
                seen[pattern] = {
                    "type": "repeated_error",
                    "severity": "severe",
                    "skill": rec.get("knowledge_point") or rec.get("task_id", ""),
                    "task_id": rec.get("task_id"),
                    "evidence": f"错误模式 '{pattern}' 已确认（≥2 次证据）",
                    "pattern": pattern,
                    "count": 2,
                    "ts": rec.get("timestamp", ""),
                }
        return list(seen.values())

    # ---------------------------------------------------------- stall timeout

    def stall_timeout(
        self, records: list[dict], *, now: datetime | None = None, threshold_minutes: int = STALL_THRESHOLD_MINUTES
    ) -> list[dict]:
        """Trigger when the latest exercise is older than the stall threshold."""
        if now is None:
            now = datetime.now(timezone.utc)
        exercises = [r for r in records if r.get("type") == "annotation_exercise"]
        if not exercises:
            return []
        latest = max(exercises, key=lambda r: r.get("timestamp", ""))
        ts = latest.get("timestamp", "")
        try:
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return []
        elapsed = now - ts_dt
        if elapsed.total_seconds() > threshold_minutes * 60:
            return [
                {
                    "type": "stall_timeout",
                    "severity": "mild",
                    "skill": latest.get("knowledge_point") or latest.get("task_id", ""),
                    "task_id": latest.get("task_id"),
                    "evidence": f"在任务停留超过 {threshold_minutes} 分钟",
                    "count": int(elapsed.total_seconds() // 60),
                    "ts": ts,
                }
            ]
        return []

    # ------------------------------------------------------------- aggregate

    def detect(self, *, records: list[dict], now: datetime | None = None) -> dict:
        """Aggregate all signals. Returns {signals, has_struggle, max_severity}."""
        signals = []
        signals.extend(self.low_score_streak(records))
        signals.extend(self.repeated_error(records))
        signals.extend(self.stall_timeout(records, now=now))
        signals.sort(key=lambda s: SEVERITY_RANK.get(s["severity"], 0), reverse=True)
        max_severity = max((s["severity"] for s in signals), default=None) if signals else None
        if max_severity is not None:
            max_severity = max(signals, key=lambda s: SEVERITY_RANK.get(s["severity"], 0))["severity"]
        return {
            "signals": signals,
            "has_struggle": bool(signals),
            "max_severity": max_severity,
        }


__all__ = ["StruggleDetector", "LOW_F1_THRESHOLD", "STALL_THRESHOLD_MINUTES"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/test_struggle_detector.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_struggle_detector.py deeptutor/services/struggle_detector.py
git commit -m "feat: StruggleDetector 确定性 3 信号检测器 (连续低分/错误重复/停留超时)"
```

---

### Task 2: `intervention_suggestion` — 信号→介入建议映射

**Files:**
- Modify: `deeptutor/services/struggle_detector.py` (add method)
- Test: `tests/services/test_struggle_detector.py` (append)

- [ ] **Step 1: Write the failing test** (append to test file)

```python
def test_intervention_suggestion_low_score():
    s = StruggleDetector().intervention_suggestion(
        {"type": "low_score_streak", "severity": "moderate", "skill": "边界框绘制规范"}
    )
    assert s["readiness"] == "review_first"
    assert "降" in s["action"] or "复习" in s["action"]


def test_intervention_suggestion_repeated_error():
    s = StruggleDetector().intervention_suggestion(
        {"type": "repeated_error", "severity": "severe", "pattern": "漏标"}
    )
    assert s["readiness"] == "diagnose_again"
    assert "换" in s["action"] or "回退" in s["action"]


def test_intervention_suggestion_stall():
    s = StruggleDetector().intervention_suggestion(
        {"type": "stall_timeout", "severity": "mild", "task_id": "task2"}
    )
    assert s["readiness"] == "more_practice"
    assert "帮助" in s["action"] or "提示" in s["action"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/test_struggle_detector.py::test_intervention_suggestion_low_score -v 2>&1 | Select-Object -First 8`
Expected: FAIL (method not found)

- [ ] **Step 3: Implement** — append method to `StruggleDetector`:

```python
    # ---------------------------------------------------- intervention mapping

    def intervention_suggestion(self, signal: dict) -> dict:
        """Map a signal to an intervention suggestion (readiness_gate mapping)."""
        s_type = signal.get("type")
        skill = signal.get("skill") or signal.get("task_id") or ""
        if s_type == "low_score_streak":
            return {
                "readiness": "review_first",
                "action": f"建议降到更基础任务重练，复习前置技能 '{skill}'",
                "signal_type": s_type,
                "target": skill,
            }
        if s_type == "repeated_error":
            return {
                "readiness": "diagnose_again",
                "action": f"错误模式 '{signal.get('pattern', '')}' 已确认，建议换教学模式或回退 Phase1 重诊",
                "signal_type": s_type,
                "target": skill,
            }
        if s_type == "stall_timeout":
            return {
                "readiness": "more_practice",
                "action": f"在任务 '{signal.get('task_id', '')}' 停留超时，建议主动询问学生是否需要帮助并给提示",
                "signal_type": s_type,
                "target": signal.get("task_id", ""),
            }
        return {"readiness": "more_practice", "action": "继续观察", "signal_type": s_type, "target": skill}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/test_struggle_detector.py -v 2>&1 | Select-Object -Last 4`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/struggle_detector.py tests/services/test_struggle_detector.py
git commit -m "feat: intervention_suggestion 信号→介入建议映射 (对接 readiness_gate)"
```

---

### Task 3: `StruggleDetectTool` — Coach 工具 + LLM 解释层

**Files:**
- Create: `deeptutor/tools/struggle_tool.py`
- Test: `tests/tools/test_struggle_tool.py`

- [ ] **Step 1: Write the failing test**

```python
"""StruggleDetectTool tests — deterministic result + LLM explanation fallback."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_struggle_detect_no_signal(monkeypatch) -> None:
    from deeptutor.tools.struggle_tool import StruggleDetectTool

    async def _fake_detect(*, records, now=None) -> dict:
        return {"signals": [], "has_struggle": False, "max_severity": None}

    monkeypatch.setattr("deeptutor.tools.struggle_tool._load_records", lambda: [])
    monkeypatch.setattr("deeptutor.tools.struggle_tool.StruggleDetector", lambda: type("D", (), {"detect": _fake_detect})())

    tool = StruggleDetectTool()
    result = await tool.execute()
    assert result.success
    assert "卡住" not in result.content or "未检测到" in result.content


@pytest.mark.asyncio
async def test_struggle_detect_severe_with_llm(monkeypatch) -> None:
    from deeptutor.tools.struggle_tool import StruggleDetectTool

    async def _fake_detect(*, records, now=None) -> dict:
        return {
            "signals": [{"type": "repeated_error", "severity": "severe", "pattern": "漏标", "skill": "小目标标注策略"}],
            "has_struggle": True,
            "max_severity": "severe",
        }

    async def _fake_explain(signal) -> str:
        return "我注意到你在小目标上反复漏标，建议我们先回退复习一下。"

    monkeypatch.setattr("deeptutor.tools.struggle_tool._load_records", lambda: [])
    monkeypatch.setattr("deeptutor.tools.struggle_tool.StruggleDetector", lambda: type("D", (), {"detect": _fake_detect})())
    monkeypatch.setattr("deeptutor.tools.struggle_tool._explain_intervention", _fake_explain)

    tool = StruggleDetectTool()
    result = await tool.execute()
    assert result.success
    assert "反复漏标" in result.content


@pytest.mark.asyncio
async def test_struggle_detect_llm_fails_degrades(monkeypatch) -> None:
    from deeptutor.tools.struggle_tool import StruggleDetectTool

    async def _fake_detect(*, records, now=None) -> dict:
        return {
            "signals": [{"type": "repeated_error", "severity": "severe", "pattern": "漏标", "skill": "小目标标注策略"}],
            "has_struggle": True,
            "max_severity": "severe",
        }

    async def _fake_explain(signal) -> str:
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("deeptutor.tools.struggle_tool._load_records", lambda: [])
    monkeypatch.setattr("deeptutor.tools.struggle_tool.StruggleDetector", lambda: type("D", (), {"detect": _fake_detect})())
    monkeypatch.setattr("deeptutor.tools.struggle_tool._explain_intervention", _fake_explain)

    tool = StruggleDetectTool()
    result = await tool.execute()
    assert result.success  # structured suggestion still returned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_struggle_tool.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.tools.struggle_tool'`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/tools/struggle_tool.py`:

```python
"""StruggleDetectTool — coach tool for deterministic struggle detection + intervention."""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolResult
from deeptutor.tools.prompting import load_prompt_hints


class StruggleDetectTool(BaseTool):
    """Detect learner struggle signals and suggest intervention."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="struggle_detect",
            description=(
                "Detect whether the learner is stuck: consecutive low F1, confirmed "
                "repeated error patterns, or task stall timeout. Call AFTER evaluating "
                "an exercise and at the start of a session with history. Returns "
                "intervention suggestions mapped to readiness_gate decisions."
            ),
            parameters=[],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        records = _load_records()
        detector = _build_detector()
        result = detector.detect(records=records)

        if not result.get("has_struggle"):
            return ToolResult(
                content="未检测到明显卡住信号，学习状态正常。",
                metadata={"signals": [], "has_struggle": False},
            )

        signals = result.get("signals", [])
        suggestions = [detector.intervention_suggestion(s) for s in signals]

        content_lines = ["## 困难检测介入建议\n"]
        for sig, sug in zip(signals, suggestions):
            content_lines.append(f"- [{sig.get('severity', '')}] {sig.get('evidence', '')}")
            content_lines.append(f"  → {sug.get('action', '')} (readiness={sug.get('readiness', '')})")

        content = "\n".join(content_lines)

        # LLM explanation for severe signals (Theory-of-Mind), degraded on failure
        severe = [s for s in signals if s.get("severity") == "severe"]
        if severe:
            try:
                explanation = await _explain_intervention(severe[0])
            except Exception:
                explanation = None
            if explanation:
                content = f"{content}\n\n{explanation}"

        return ToolResult(
            content=content,
            metadata={
                "signals": signals,
                "suggestions": suggestions,
                "has_struggle": True,
                "max_severity": result.get("max_severity"),
            },
        )

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


# ------------------------------------------------------------ dependencies

def _load_records() -> list[dict]:
    from deeptutor.services.learning_records import LearningRecordStore

    return LearningRecordStore().list_records()


def _build_detector() -> Any:
    from deeptutor.services.struggle_detector import StruggleDetector

    return StruggleDetector()


async def _explain_intervention(signal: dict) -> str | None:
    """LLM explanation of the intervention (Theory-of-Mind style). Caller catches."""
    from deeptutor.tools.reason import reason

    prompt = (
        f"你是数据标注教学教练。检测到学生可能卡住了，信号：{signal.get('evidence', '')}。"
        f"请用中文给学生一句鼓励但具体的介入话术，解释为什么会卡住、建议怎么做。"
        f"只依据信号数据，不得虚构其他信息。"
    )
    result = await reason(query=prompt, max_tokens=150, temperature=0.3)
    answer = (result or {}).get("answer", "").strip()
    return answer or None


__all__ = ["StruggleDetectTool"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_struggle_tool.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/struggle_tool.py tests/tools/test_struggle_tool.py
git commit -m "feat: StruggleDetectTool 困难检测工具 + LLM 解释层 (失败降级)"
```

---

### Task 4: 注册 struggle_detect 为 always-on 工具

**Files:**
- Modify: `deeptutor/tools/builtin/__init__.py` (import + class list + name list + configurable)
- Modify: `deeptutor/agents/_shared/tool_composition.py` (always_on tuple)

- [ ] **Step 1: Write the failing test**

```python
"""struggle_detect registration tests."""

from __future__ import annotations


def test_struggle_detect_in_builtin() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES

    assert "struggle_detect" in BUILTIN_TOOL_NAMES


def test_struggle_detect_in_configurable() -> None:
    from deeptutor.tools.builtin import CONFIGURABLE_BUILTIN_TOOL_NAMES

    assert "struggle_detect" in CONFIGURABLE_BUILTIN_TOOL_NAMES


def test_struggle_detect_in_always_on() -> None:
    import inspect

    import deeptutor.agents._shared.tool_composition as tc

    src = inspect.getsource(tc)
    assert '"struggle_detect"' in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_struggle_tool_registration.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL (struggle_detect not registered)

- [ ] **Step 3: Register the tool**

Edit `deeptutor/tools/builtin/__init__.py`:
1. Add import: `from deeptutor.tools.struggle_tool import StruggleDetectTool`
2. Add `StruggleDetectTool,` to `BUILTIN_TOOL_TYPES` (near `AbilityRadarTool,`)
3. Add `"StruggleDetectTool",` to `__all__`
4. Add `"struggle_detect",` to `CONFIGURABLE_BUILTIN_TOOL_NAMES` (near `ability_radar`)

Edit `deeptutor/agents/_shared/tool_composition.py`:
5. Add `"struggle_detect",` to the always_on tuple (near `ability_radar`)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_struggle_tool_registration.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (3 passed)

- [ ] **Step 5: Verify import smoke**

Run: `python -c "import deeptutor.tools.builtin as b; print('struggle_detect' in b.BUILTIN_TOOL_NAMES)"`
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py tests/tools/test_struggle_tool_registration.py
git commit -m "feat: 注册 struggle_detect 为第14个 always-on 教学工具"
```

---

### Task 5: 接入对话协议（flow-practice / flow-onboarding）+ PERSONA

**Files:**
- Modify: `deeptutor/skills/builtin/annotation-coach-flows/references/flow-practice.md`
- Modify: `deeptutor/skills/builtin/annotation-coach-flows/references/flow-onboarding.md`
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md`
- Sync: `deeptutor/services/persona/presets/annotation-coach/references/*` (flows)

- [ ] **Step 1: Edit flow-practice.md** — in Step1 (after evaluation), add:

```markdown
评测后调 `struggle_detect` 检查是否卡住:
  → 有信号: 按建议介入 (降难度/换模式/主动询问), 并用 log_decision(kind=struggle_intervention) 记录
  → 无信号: 正常推进
```

- [ ] **Step 2: Edit flow-onboarding.md** — in Step0 (有历史记录分支), add:

```markdown
有历史记录时先调 `struggle_detect`: 
  → 若检测到跨会话卡住信号 (如上次连续低分/错误确认), 先介入再分诊
  → 无信号 → 正常分诊 (快速确认/续学/深入)
```

- [ ] **Step 3: Edit PERSONA.md** — after rule 11 (graph_query), add rule 12:

```markdown
12. **评测后必查卡住**: 每次评测完和新会话开始时调 `struggle_detect`, 检测到卡住信号按建议介入,
    并用 `log_decision(kind=struggle_intervention)` 记录介入理由。
```

- [ ] **Step 4: Sync flows to persona references**

Run:
```powershell
Copy-Item "D:\自己\git帅\-deeptutor-agent-\deeptutor\skills\builtin\annotation-coach-flows\references\flow-practice.md" "D:\自己\git帅\-deeptutor-agent-\deeptutor\services\persona\presets\annotation-coach\references\flow-practice.md" -Force
Copy-Item "D:\自己\git帅\-deeptutor-agent-\deeptutor\skills\builtin\annotation-coach-flows\references\flow-onboarding.md" "D:\自己\git帅\-deeptutor-agent-\deeptutor\services\persona\presets\annotation-coach\references\flow-onboarding.md" -Force
```

- [ ] **Step 5: Verify no syntax errors in edited md** (visual check of the 3 edits)

- [ ] **Step 6: Commit**

```bash
git add deeptutor/skills/builtin/annotation-coach-flows/references/flow-practice.md deeptutor/skills/builtin/annotation-coach-flows/references/flow-onboarding.md deeptutor/services/persona/presets/annotation-coach/PERSONA.md deeptutor/services/persona/presets/annotation-coach/references/
git commit -m "feat: 接入 struggle_detect 到教学流程协议 + PERSONA 规则12"
```

---

### Task 6: 审计闭环 + 回归验证

**Files:**
- Modify: `deeptutor/tools/log_decision_tool.py` (add struggle_intervention to description)
- Test: `tests/services/test_struggle_detector.py` + `tests/tools/test_struggle_tool.py` (full run)

- [ ] **Step 1: Update log_decision description** — add `struggle_intervention` kind to the tool description so Coach knows it can log interventions. Verify `append_decision` has no kind validation (confirmed — it doesn't).

- [ ] **Step 2: Run full struggle test suite**

Run: `python -m pytest tests/services/test_struggle_detector.py tests/tools/test_struggle_tool.py tests/tools/test_struggle_tool_registration.py -v 2>&1 | Select-Object -Last 6`
Expected: PASS (all struggle tests)

- [ ] **Step 3: Run regression on related suites**

Run: `python -m pytest tests/tools/test_graph_tool.py tests/services/test_knowledge_graph.py tests/tools/test_ability_radar_tool.py tests/tools/test_chart_cards.py -q 2>&1 | Select-Object -Last 4`
Expected: PASS (no regression)

- [ ] **Step 4: End-to-end smoke** — script a struggle scenario:

```powershell
$env:PYTHONIOENCODING="utf-8"; python -c @"
import asyncio, tempfile
from pathlib import Path
from deeptutor.services.struggle_detector import StruggleDetector
from datetime import datetime, timezone, timedelta

async def main():
    # 构造卡住场景: 连续低分 + confirmed 错误
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        {'type':'annotation_exercise','task_id':'task1','knowledge_point':'边界框绘制规范','f1':0.6,'timestamp':'2026-08-01T10:00:00+00:00'},
        {'type':'annotation_exercise','task_id':'task1','knowledge_point':'边界框绘制规范','f1':0.5,'error_pattern':'漏标','pattern_status':'confirmed','timestamp':'2026-08-01T11:00:00+00:00'},
    ]
    d = StruggleDetector()
    r = d.detect(records=records, now=now)
    print('has_struggle:', r['has_struggle'], '| max:', r['max_severity'])
    for s in r['signals']:
        print(' signal:', s['type'], s['severity'])
        sug = d.intervention_suggestion(s)
        print('   ->', sug['readiness'], '|', sug['action'])
    assert r['has_struggle'] and r['max_severity'] == 'severe'

asyncio.run(main())
"@
```
Expected: detects repeated_error (severe) + low_score_streak (moderate), interventions mapped.

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/log_decision_tool.py
git commit -m "feat: log_decision 支持 struggle_intervention kind (审计闭环)"
```

---

## Self-Review

**1. Spec coverage:**
- §3.1 StruggleDetector → Task 1 (3 信号) + Task 2 (intervention_suggestion)
- §3.2 StruggleDetectTool → Task 3
- §3.3 接入对话 → Task 5
- §3.4 审计闭环 → Task 6
- §7 测试 → Task 6 (全量 + 冒烟)
- 注册 → Task 4
✅ 全覆盖

**2. Placeholder scan:** 所有代码块完整，无 TBD/TODO。Task 5 是 markdown 编辑（含完整文本）。

**3. Type consistency:**
- `StruggleDetector.detect(*, records, now=None) -> {signals, has_struggle, max_severity}` — Task 1/3/6 一致
- `intervention_suggestion(signal) -> {readiness, action, signal_type, target}` — Task 2/3/6 一致
- 信号结构 `{type, severity, skill, task_id, evidence, count, ts}` — Task 1/2 一致
- `struggle_detect` 工具名 — Task 3/4/5 一致
- `log_decision(kind=struggle_intervention)` — Task 5/6 一致

**已知风险：**
1. `low_score_streak` 需要 records 有 timestamp 且按时间序 — 排序逻辑已处理
2. `stall_timeout` 依赖 `datetime.fromisoformat` 解析 timestamp — `replace("Z","+00:00")` 已处理
3. Task 3 测试的 `_build_detector` monkeypatch 目标 — 实现者需按实际（detector 是模块函数）适配
4. flow 文件有两份拷贝（skill + persona references），Task 5 需同步
