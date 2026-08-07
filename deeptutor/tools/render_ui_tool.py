"""RenderUiTool — coach tool to render an interactive teaching component.

The coach passes a structured component JSON (AG-UI structured-message style);
the tool validates it and returns it as ``metadata.chart`` so the existing
ChatChartCard channel renders it as an interactive card (e.g. quiz_card).
"""

from __future__ import annotations

import json
import os
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

LS_BASE_URL = os.environ.get("LABEL_STUDIO_URL", "http://localhost:8080")


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
    if ctype == "ls_task_card":
        project_id = data.get("project_id")
        task_index = data.get("task_index")
        title = data.get("title")
        if isinstance(project_id, bool) or not isinstance(project_id, int):
            return None
        if isinstance(task_index, bool) or not isinstance(task_index, int) or task_index < 0:
            return None
        if not isinstance(title, str) or not title.strip():
            return None
        task_type = str(data.get("task_type") or "bbox").strip() or "bbox"
        instructions = str(data.get("instructions") or "").strip()
        return {"type": "ls_task_card", "data": {
            "project_id": project_id,
            "task_index": task_index,
            "title": title.strip(),
            "task_type": task_type,
            "instructions": instructions,
            "url": f"{LS_BASE_URL}/projects/{project_id}/labeling?task={task_index}",
        }}
    if ctype == "progress_card":
        completed = data.get("completed")
        total = data.get("total")
        if isinstance(completed, bool) or not isinstance(completed, int) or completed < 0:
            return None
        if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            return None
        if completed > total:
            return None
        modules_raw = data.get("modules")
        if not isinstance(modules_raw, list):
            return None
        modules = []
        for module in modules_raw:
            if not isinstance(module, dict):
                return None
            name = module.get("name")
            done = module.get("done")
            module_total = module.get("total")
            if not isinstance(name, str) or not name.strip():
                return None
            if isinstance(done, bool) or not isinstance(done, int) or done < 0:
                return None
            if isinstance(module_total, bool) or not isinstance(module_total, int) or module_total <= 0:
                return None
            if done > module_total:
                return None
            modules.append({
                "name": name.strip(),
                "done": done,
                "total": module_total,
            })
        return {"type": "progress", "data": {
            "completed": completed,
            "total": total,
            "modules": modules,
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
                "instant right/wrong feedback.\n"
                "- ls_task_card: {\"type\":\"ls_task_card\",\"data\":{\"project_id\":3,"
                "\"task_index\":0,\"title\":\"遮挡检测练习\",\"task_type\":\"bbox\","
                "\"instructions\":\"在图片中标出被遮挡的目标\"}} — renders a card "
                "whose button opens the specific Label Studio labeling task "
                "(url auto-built as {LS_BASE_URL}/projects/{project_id}/labeling?task={task_index}).\n"
                "- progress_card: {\"type\":\"progress_card\",\"data\":{\"completed\":3,"
                "\"total\":5,\"modules\":[{\"name\":\"遮挡检测\",\"done\":1,\"total\":2}]}} "
                "— renders a capability-goal progress card (reuses the built-in "
                "progress renderer)."
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
                    "question/options(≥2)/answer_index(合法下标)；ls_task_card 需要 "
                    "type='ls_task_card' 且 data 含 project_id(int)/task_index(int≥0)/title(非空str)；"
                    "progress_card 需要 type='progress_card' 且 data 含 completed(int≥0)/total(int>0)/"
                    "modules(list, 每项 name 非空 str、done/total 为合法 int)。"
                ),
                success=False,
            )
        return ToolResult(content="已生成练习卡片（见上方）。", metadata={"chart": validated})


__all__ = ["RenderUiTool", "validate_component"]
