"""StruggleDetectTool tests — deterministic result + LLM explanation fallback."""

from __future__ import annotations

import pytest


class _FakeDetector:
    """Mirrors the real StruggleDetector API (sync detect + intervention_suggestion)."""

    def __init__(self, result: dict) -> None:
        self._result = result

    def detect(self, *, records, now=None) -> dict:
        return self._result

    def intervention_suggestion(self, signal) -> dict:
        return {
            "readiness": "diagnose_again",
            "action": f"错误模式 '{signal.get('pattern', '')}' 已确认，建议换教学模式或回退 Phase1 重诊",
            "signal_type": signal.get("type"),
            "target": signal.get("skill") or signal.get("task_id") or "",
        }


def _no_signal() -> dict:
    return {"signals": [], "has_struggle": False, "max_severity": None}


def _severe_signal() -> dict:
    return {
        "signals": [{"type": "repeated_error", "severity": "severe", "pattern": "漏标", "skill": "小目标标注策略"}],
        "has_struggle": True,
        "max_severity": "severe",
    }


@pytest.mark.asyncio
async def test_struggle_detect_no_signal(monkeypatch) -> None:
    from deeptutor.tools.struggle_tool import StruggleDetectTool

    monkeypatch.setattr("deeptutor.tools.struggle_tool._load_records", lambda: [])
    monkeypatch.setattr("deeptutor.tools.struggle_tool._build_detector", lambda: _FakeDetector(_no_signal()))

    tool = StruggleDetectTool()
    result = await tool.execute()
    assert result.success
    assert "未检测到" in result.content


@pytest.mark.asyncio
async def test_struggle_detect_severe_with_llm(monkeypatch) -> None:
    from deeptutor.tools.struggle_tool import StruggleDetectTool

    async def _fake_explain(signal) -> str:
        return "我注意到你在小目标上反复漏标，建议我们先回退复习一下。"

    monkeypatch.setattr("deeptutor.tools.struggle_tool._load_records", lambda: [])
    monkeypatch.setattr("deeptutor.tools.struggle_tool._build_detector", lambda: _FakeDetector(_severe_signal()))
    monkeypatch.setattr("deeptutor.tools.struggle_tool._explain_intervention", _fake_explain)

    tool = StruggleDetectTool()
    result = await tool.execute()
    assert result.success
    assert "反复漏标" in result.content


@pytest.mark.asyncio
async def test_struggle_detect_llm_fails_degrades(monkeypatch) -> None:
    from deeptutor.tools.struggle_tool import StruggleDetectTool

    async def _fake_explain(signal) -> str:
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("deeptutor.tools.struggle_tool._load_records", lambda: [])
    monkeypatch.setattr("deeptutor.tools.struggle_tool._build_detector", lambda: _FakeDetector(_severe_signal()))
    monkeypatch.setattr("deeptutor.tools.struggle_tool._explain_intervention", _fake_explain)

    tool = StruggleDetectTool()
    result = await tool.execute()
    assert result.success  # structured suggestion still returned
