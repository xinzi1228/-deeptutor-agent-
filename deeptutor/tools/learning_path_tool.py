"""A learner-installed tool that exposes a compact learning-path diagram."""
from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolResult


class RenderLearningPathTool(BaseTool):
    name = "render_learning_path"

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description="Render the current learner's approved learning-path diagram when they ask to view their learning route or next steps.",
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.extension_marketplace import ExtensionMarketplaceService

        try:
            diagram = ExtensionMarketplaceService().learning_path()
        except PermissionError as exc:
            return ToolResult(content="该学习路径扩展尚未启用。", success=False, metadata={"reason": str(exc)})
        return ToolResult(
            content="已生成当前学习路径图。请结合图中的“下一步”继续学习。",
            metadata={"extension_id": "learning-path-diagram", "diagram": diagram},
        )


__all__ = ["RenderLearningPathTool"]
