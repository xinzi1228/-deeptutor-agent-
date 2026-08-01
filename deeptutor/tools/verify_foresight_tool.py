"""Verify foresight tool — EverOS-style predict-then-verify loop.

The coach records a ``foresight`` (a prediction about what the learner will
struggle with / master next) when writing a learning record. On the next
session, after observing the actual result, the coach calls this tool to mark
the prediction hit or miss — closing the correction loop and turning the
learner model into a self-validating profile.
"""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints


class VerifyForesightTool(BaseTool):
    """Mark a recorded foresight as hit or miss."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="verify_foresight",
            description=(
                "Resolve an open foresight: mark whether the coach's earlier prediction "
                "about the learner was correct. Call at the START of a session when the "
                "learner demonstrates the next skill/error — before teaching. Closing the "
                "loop makes the learner model self-validating (EverOS foresight pattern). "
                "Open foresights can be listed via get_learning_records (they carry a "
                "'foresight' field and no 'foresight_verified')."
            ),
            parameters=[
                ToolParameter(
                    name="record_index",
                    type="integer",
                    description="Position of the foresight record (from open foresights listing).",
                ),
                ToolParameter(
                    name="hit",
                    type="boolean",
                    description="True = prediction came true, False = it didn't.",
                ),
                ToolParameter(
                    name="note",
                    type="string",
                    description="Optional one-line observation of what actually happened.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.learning_records import LearningRecordStore

        store = LearningRecordStore()
        index = kwargs.get("record_index")
        if index is None:
            return ToolResult(content="Error: record_index is required.", success=False)
        hit = kwargs.get("hit")
        if not isinstance(hit, bool):
            return ToolResult(content="Error: hit must be a boolean.", success=False)
        note = str(kwargs.get("note") or "").strip()

        try:
            target = store.resolve_foresight(int(index), hit, note)
        except (TypeError, ValueError):
            return ToolResult(content="Error: record_index must be an integer.", success=False)
        if target is None:
            return ToolResult(
                content=f"Error: record_index {index} out of range.",
                success=False,
            )

        outcome = "命中" if hit else "未命中"
        return ToolResult(
            content=(
                f"Foresight resolved: {outcome} — record #{index} "
                f"(predicted: {target.get('foresight', {}).get('predicted_next', '?')}). "
                f"{'注: ' + note if note else ''}"
            ),
            metadata={
                "record_index": index,
                "hit": hit,
                "foresight": target.get("foresight"),
            },
        )

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


__all__ = ["VerifyForesightTool"]
