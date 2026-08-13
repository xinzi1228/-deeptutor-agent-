from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult


class CreateVisualizationTool(BaseTool):
    """Shared chart/diagram specialist with deterministic truth guards."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="create_visualization",
            description=(
                "Create a validated reusable chart or Mermaid diagram. Use chart only when real numeric data, "
                "source and unit are available; never invent missing values. Use diagram for processes, structure, "
                "causes or concept relationships. For a fun conceptual illustration, use imagegen instead and clearly "
                "call it a concept illustration. Payload schema: {kind:'chart'|'diagram', title, description, alt_text, "
                "source, unit, source_updated_at, content}. Chart content={chart_type:'line|bar|pie|doughnut|radar|scatter', "
                "labels:[...], datasets:[{label,data:[numbers]}]}; diagram content={mermaid:'flowchart ...'}."
            ),
            parameters=[ToolParameter(name="artifact", type="string", description="Visualization artifact JSON", required=True)],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        # Lazy imports keep the global built-in registry independent from the
        # runtime path-service bootstrap (and avoid pulling storage into startup).
        from deeptutor.multi_user.paths import get_current_learning_profile_root
        from deeptutor.services.visualization_artifacts import (
            VisualizationArtifactStore,
            validate_visualization_request,
        )

        raw = kwargs.get("artifact", "{}")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as exc:
            return ToolResult(content=f"可视化 JSON 解析失败：{exc}", success=False)
        if not isinstance(payload, dict):
            return ToolResult(content="可视化参数必须是对象。", success=False)
        try:
            artifact = validate_visualization_request(payload, session_id=str(kwargs.get("_session_id") or ""))
            profile_root = get_current_learning_profile_root(require_unlocked=True)
            if profile_root is None:
                raise PermissionError("请先解锁学习档案")
            VisualizationArtifactStore(profile_root).save(artifact)
        except (ValueError, PermissionError) as exc:
            return ToolResult(content=f"无法生成可视化：{exc}", success=False)
        return ToolResult(
            content=f"已生成并校验“{artifact.title}”。{artifact.validation_message}",
            metadata={"chart": {"type": "visualization", "data": artifact.to_dict()}},
        )


__all__ = ["CreateVisualizationTool"]
