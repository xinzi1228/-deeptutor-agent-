from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult


class CreateVisualizationTool(BaseTool):
    """Shared chart/diagram specialist with deterministic truth guards."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="create_visualization",
            description=(
                "Create a validated reusable chart or Mermaid diagram. Before every chart, call "
                "read_learning_chart_data and pass its snapshot_id as source_ref. The server copies and verifies "
                "dataset_ref, source, unit, labels and datasets; never invent or alter values. Use diagram for processes, structure, "
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
            load_verified_dataset_snapshot,
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
            profile_root = get_current_learning_profile_root(require_unlocked=True)
            if profile_root is None:
                raise PermissionError("请先解锁学习档案")
            if payload.get("kind") == "chart":
                source_ref = str(payload.get("source_ref") or "").strip()
                if not source_ref.startswith("dataset_"):
                    raise ValueError("请先用 read_learning_chart_data 获取可信 dataset_ref")
                snapshot = load_verified_dataset_snapshot(profile_root, source_ref)
                expected = snapshot.get("content") or {}
                supplied = payload.get("content") or {}
                if supplied.get("labels") is not None and supplied.get("labels") != expected.get("labels"):
                    raise ValueError("图表标签与可信数据快照不一致，禁止修改")
                if supplied.get("datasets") is not None and supplied.get("datasets") != expected.get("datasets"):
                    raise ValueError("图表数值与可信数据快照不一致，禁止修改或补写数字")
                chart_type = str(supplied.get("chart_type") or "line")
                payload["content"] = {**expected, "chart_type": chart_type}
                payload["source"] = snapshot.get("source", "")
                payload["unit"] = snapshot.get("unit", "")
                payload["source_updated_at"] = snapshot.get("source_updated_at", "")
                payload["dataset_ref"] = snapshot.get("dataset_ref")
            artifact = validate_visualization_request(
                payload,
                profile_id=Path(profile_root).name,
                session_id=str(kwargs.get("_session_id") or ""),
                message_id=str(kwargs.get("_message_id") or ""),
            )
            VisualizationArtifactStore(profile_root).save(artifact)
        except (ValueError, PermissionError) as exc:
            return ToolResult(content=f"无法生成可视化：{exc}", success=False)
        return ToolResult(
            content=f"已生成并校验“{artifact.title}”。{artifact.validation_message}",
            metadata={"chart": {"type": "visualization", "data": artifact.to_dict()}},
        )


__all__ = ["CreateVisualizationTool"]
