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
                "9 tasks across 3 difficulty levels (easy/medium/hard) and 2 types (bbox/classification). "
                "task1-4: bbox detection, task5/9: classification, task6-8: advanced bbox."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="task1-task9. easy: task1/3/5, medium: task2/4/9, hard: task6/7/8",
                    enum=["task1", "task2", "task3", "task4", "task5", "task6", "task7", "task8", "task9"],
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
            kps = ", ".join(task.get("knowledge_points", []))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"![Task Image]({task['image_url']})\n\n"
                f"{task['instruction']}\n\n"
                f"**标签**: {', '.join(task['labels'])} | **数量**: {task['object_count']} 个\n"
                f"**格式**: 每个框 `{fmt}`，放入 JSON 数组。例: `[{fmt}]`\n"
                f"**训练技能**: {kps}\n\n"
                f"---\n"
                f"Ground Truth (用于评分):\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 用户提交的 JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: bbox\n\n"
                f"完成后续推荐: {task.get('next_task','请根据F1分数决定')}"
            )
        else:
            items_text = "\n".join(f"  {i['id']}. {i['text']}" for i in task.get("items", []))
            kps = ", ".join(task.get("knowledge_points", []))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"![Task Image]({task['image_url']})\n\n"
                f"{task['instruction']}\n\n{items_text}\n\n"
                f"**标签**: {', '.join(task['labels'])}\n"
                f"**训练技能**: {kps}\n\n"
                f"Ground Truth:\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`，task_type: classification\n\n"
                f"完成后续推荐: {task.get('next_task','请根据准确率决定')}"
            )

        return ToolResult(content=content, metadata={"task_id": tid, "ground_truth": gt})
