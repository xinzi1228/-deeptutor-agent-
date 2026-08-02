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
        try:
            result = detector.detect(records=records)
        except Exception:
            # Design doc §6: detector internal exception degrades to no-signal.
            result = {"signals": [], "has_struggle": False, "max_severity": None}

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
