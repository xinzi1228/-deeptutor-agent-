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
