"""Task bank tool — loads tasks from course dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

BANK_PATH = Path(__file__).parent.parent.parent / "data" / "user" / "workspace" / "task_bank.json"


def _load_bank() -> dict:
    if BANK_PATH.exists():
        return json.loads(BANK_PATH.read_text(encoding="utf-8"))
    return {}


class GetAnnotationTaskTool(BaseTool):
    """Return annotation tasks from the course dataset with real images and ground truth."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_annotation_task",
            description=(
                "Get a REAL annotation practice task with ground truth from the course dataset. "
                "Available: task1 (1 car), task2 (4 cars), task3 (1 car closeup), "
                "task4 (4 horses), task5 (animal classification)."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="task1/task2/task3/task4/task5",
                    enum=["task1", "task2", "task3", "task4", "task5"],
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        bank = _load_bank()
        tid = kwargs.get("task_id", "task1")
        task = bank.get(tid)
        if not task:
            ids = ", ".join(bank.keys())
            return ToolResult(content=f"Unknown task: {tid}. Available: {ids}", success=False)

        gt = task["ground_truth"]
        gt_json = json.dumps(gt)

        if task["type"] == "bbox":
            fmt = json.dumps(gt[0]) if gt else '{"x":0,"y":0,"w":100,"h":100,"label":"?"}'
            content = (
                f"## {task['title']} ({task['difficulty']}) — {task['object_count']} object(s)\n\n"
                f"![Task Image]({task['image_url']})\n\n"
                f"{task['instruction']}\n\n"
                f"**Labels**: {', '.join(task['labels'])}\n"
                f"**Format**: each box as `{fmt}` in a JSON array. Example: `[{fmt}]`\n\n"
                f"---\n"
                f"Ground Truth (for scoring):\n```json\n{gt_json}\n```\n"
                f"After user submits, call `annotation_check`:\n"
                f"- predictions: user's JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: bbox\n\n"
                f"Next task: {task.get('next_task','none')}"
            )
        else:
            items_text = "\n".join(f"  {i['id']}. {i['text']}" for i in task.get("items", []))
            content = (
                f"## {task['title']} ({task['difficulty']})\n\n"
                f"{task['instruction']}\n\n{items_text}\n\n"
                f"**Labels**: {', '.join(task['labels'])}\n"
                f"**Format**: `[{task['format']}, ...]`\n\n"
                f"Ground Truth:\n```json\n{gt_json}\n```\n"
                f"After user submits, call `annotation_check` with task_type: classification"
            )

        return ToolResult(content=content, metadata={"task_id": tid, "ground_truth": gt})
