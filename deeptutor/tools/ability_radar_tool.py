"""AbilityRadarTool — learner five-dimension ability radar.

Computes the learner's ability scores from learning records (LearningStats.radar)
and returns them as a ``metadata.chart`` radar contract for the chat UI.
"""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolResult
from deeptutor.tools.chart_cards import radar_chart
from deeptutor.tools.prompting import load_prompt_hints


def _load_learning_stats() -> Any:
    """Resolve ``LearningStats`` lazily to avoid the builtin↔services import cycle."""
    from deeptutor.services.learning_records import LearningStats

    return LearningStats


class AbilityRadarTool(BaseTool):
    """Show the learner's five-dimension ability radar."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ability_radar",
            description=(
                "Show the learner's five-dimension ability radar (框精度/标签准确/"
                "完整性/一致性/知识掌握) computed from their practice records. "
                "Use when the learner asks how they're doing or before planning "
                "the next concept."
            ),
            parameters=[],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        radar = _load_learning_stats()().radar()
        dims = radar.get("dimensions", [])
        labels = [d.get("name", "") for d in dims]
        values = [float(d.get("score", 0)) for d in dims]

        chart = radar_chart(labels=labels, values=values)

        if not any(v > 0 for v in values):
            content = "暂无练习记录 — 完成标注练习后，这里会展示你的五维能力雷达。"
        else:
            lines = ["## 五维能力雷达\n"]
            for d in dims:
                lines.append(
                    f"- **{d.get('name', '')}**: {d.get('score', 0)} / {d.get('max', 100)}"
                )
            content = "\n".join(lines)

        return ToolResult(content=content, metadata={"chart": chart, "radar": radar})

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


__all__ = ["AbilityRadarTool"]
