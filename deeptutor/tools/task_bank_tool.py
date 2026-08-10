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
                "18 tasks across 3 difficulty levels, 3 modalities (image/text/video) and 10 types. "
                "task1-4: bbox detection, task5/9: classification, task6-8: advanced bbox, "
                "task10: judgment, task11: standard, task12: error_case, "
                "task13-14: audio, task15-16: video tracking, task17-18: video events, "
                "task19-22: text annotation (NER/classification/judgment/error_case)."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="task1-task22. Available tasks across image/text/video modalities.",
                    enum=["task1", "task2", "task3", "task4", "task5", "task6", "task7", "task8", "task9", "task10", "task11", "task12", "task13", "task14", "task15", "task16", "task17", "task18", "task19", "task20", "task21", "task22"],
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
        gt_json = json.dumps(gt, ensure_ascii=False)
        ttype = task["type"]
        modal = task.get("modal", "image")
        kps = ", ".join(task.get("knowledge_points", []))

        if ttype == "bbox":
            fmt = json.dumps(gt[0]) if gt else '{"x":0,"y":0,"w":100,"h":100,"label":"?"}'
            if modal == "video":
                media_url = task.get("media_url", task.get("image_url", ""))
                content = (
                    f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                    f"🎬 视频文件: `{media_url}`\n\n"
                    f"{task['instruction']}\n\n"
                    f"**标签**: {', '.join(task['labels'])} | **数量**: {task['object_count']} 个\n"
                    f"**格式**: 每个框 `{fmt}`，放入 JSON 数组。例: `[{fmt}]`\n"
                    f"**训练技能**: {kps}\n\n"
                    f"---\n"
                    f"Ground Truth (用于评分):\n```json\n{gt_json}\n```\n"
                    f"评分时调用 `annotation_check`，task_type: bbox\n\n"
                    f"完成后续推荐: {task.get('next_task','请根据F1分数决定')}"
                )
            else:
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
                    f"完成后续推荐: {task.get('next_task','请根据F1分数决定')}\n\n"
                    f"---\n"
                    f"[必做] 展示任务后调用 `log_decision` 记录推荐理由 "
                    f"(kind=task_recommendation, target={tid}, 依据 readiness)。"
                )
        elif modal == "text":
            items_text = "\n".join(f"  {i['id']}. {i['text']}" for i in task.get("items", []))
            text_content = task.get("text", "")
            text_block = f"\n📝 **文本内容**:\n> {text_content}\n" if text_content else ""

            if ttype == "ner":
                fmt = '{"start":0, "end":5, "label":"term"}'
                content = (
                    f"## {task['title']} — 难度: {task['difficulty']}\n{text_block}\n"
                    f"{task['instruction']}\n\n"
                    f"**实体类型**: {', '.join(task['labels'])}\n"
                    f"**格式**: `{fmt}`（start=起始字符位置, end=结束字符位置），JSON 数组\n"
                    f"**训练技能**: {kps}\n\n"
                    f"Ground Truth:\n```json\n{gt_json}\n```\n"
                    f"评分时调用 `annotation_check`，task_type: ner\n\n"
                    f"完成后续推荐: {task.get('next_task','请根据F1分数决定')}"
                )
            elif ttype == "classification":
                content = (
                    f"## {task['title']} — 难度: {task['difficulty']}\n{text_block}\n"
                    f"{task['instruction']}\n\n{items_text}\n\n"
                    f"**类别**: {', '.join(task['labels'])}\n"
                    f"**训练技能**: {kps}\n\n"
                    f"Ground Truth:\n```json\n{gt_json}\n```\n"
                    f"评分时调用 `annotation_check`，task_type: classification\n\n"
                    f"完成后续推荐: {task.get('next_task','请根据准确率决定')}"
                )
            elif ttype == "judgment":
                content = (
                    f"## {task['title']} — 难度: {task['difficulty']}\n{text_block}\n"
                    f"{task['instruction']}\n\n{items_text}\n\n"
                    f"**判定词**: `correct` / `wrong` | **格式**: `[{{\"id\":N,\"label\":\"correct\"}}]`\n"
                    f"**训练技能**: {kps}\n\n"
                    f"Ground Truth:\n```json\n{gt_json}\n```\n"
                    f"评分时调用 `annotation_check`，task_type: judgment\n\n"
                    f"完成后续推荐: {task.get('next_task','请根据准确率决定')}"
                )
            elif ttype == "error_case":
                content = (
                    f"## {task['title']} — 难度: {task['difficulty']}\n{text_block}\n"
                    f"{task['instruction']}\n\n{items_text}\n\n"
                    f"**输出**: 列出有错误案例编号 `[1, 3]`\n"
                    f"**训练技能**: {kps}\n\n"
                    f"Ground Truth:\n```json\n{gt_json}\n```\n"
                    f"评分: 调 `annotation_check`，task_type: error_case\n\n"
                    f"完成后续推荐: {task.get('next_task','请根据检出准确率决定')}"
                )
            else:
                content = (
                    f"## {task['title']} — 难度: {task['difficulty']}\n{text_block}\n"
                    f"{task['instruction']}\n\n{items_text}\n\n"
                    f"**训练技能**: {kps}\n\n"
                    f"Ground Truth:\n```json\n{gt_json}\n```\n"
                    f"评分时调用 `annotation_check`，task_type: {ttype}"
                )
        elif ttype == "classification":
            items_text = "\n".join(f"  {i['id']}. {i['text']}" for i in task.get("items", []))
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
        elif ttype == "judgment":
            items_text = "\n".join(f"  {i['id']}. {i['text']}" for i in task.get("items", []))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"![Task Image]({task['image_url']})\n\n"
                f"{task['instruction']}\n\n{items_text}\n\n"
                f"**判定词**: `correct` (标注正确) / `wrong` (标注错误)\n"
                f"**格式**: 每条 `{{\"id\":编号,\"label\":\"correct\"}}`，放入 JSON 数组。"
                f"例: `[{{\"id\":1,\"label\":\"correct\"}}]`\n"
                f"**训练技能**: {kps}\n\n"
                f"Ground Truth:\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 用户提交的 JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: judgment\n\n"
                f"完成后续推荐: {task.get('next_task','请根据准确率决定')}"
            )
        elif ttype == "standard":
            required = gt[0].get("required_fields", ["x", "y", "w", "h", "label"]) if gt else ["x", "y", "w", "h", "label"]
            labels = gt[0].get("labels", []) if gt else []
            fmt = "{" + ", ".join(f'"{f}":…' for f in required) + "}"
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"![Task Image]({task['image_url']})\n\n"
                f"{task['instruction']}\n\n"
                f"**格式规范**: 每个标注必须包含字段 {required}，标签必须是 {labels} 之一。\n"
                f"**格式**: JSON 数组，例: `[{fmt}]`\n"
                f"**训练技能**: {kps}\n\n"
                f"Ground Truth:\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 用户提交的 JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: standard\n\n"
                f"完成后续推荐: {task.get('next_task','请根据合规率决定')}"
            )
        elif ttype == "error_case":
            items_text = "\n".join(f"  {i['id']}. {i['text']}" for i in task.get("items", []))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"![Task Image]({task['image_url']})\n\n"
                f"{task['instruction']}\n\n{items_text}\n\n"
                f"**输出格式**: 标错的案例 id 列表，如 `[1, 3]`（列出你认为有错误的案例编号）\n"
                f"**训练技能**: {kps}\n\n"
                f"Ground Truth:\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 把 id 列表转为 `[{{\"id\":N,\"flagged\":true/…}}]`"
                f"（列出的→true，未列出的→false）\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: error_case\n\n"
                f"完成后续推荐: {task.get('next_task','请根据检出准确率决定')}"
            )
        elif ttype == "audio_event":
            fmt = json.dumps(gt[0]) if gt else '{"start_time":0.0,"end_time":1.0,"label":"?"}'
            media_url = task.get("media_url", task.get("image_url", ""))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"🎵 音频文件: `{media_url}`\n\n"
                f"{task['instruction']}\n\n"
                f"**事件类型**: {', '.join(task['labels'])} | **事件数**: {task.get('object_count', '?')} 个\n"
                f"**格式**: 每个事件段 `{fmt}`，放入 JSON 数组。例: `[{fmt}]`\n"
                f"**训练技能**: {kps}\n\n"
                f"---\n"
                f"Ground Truth (用于评分):\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 用户提交的 JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: audio_event\n\n"
                f"完成后续推荐: {task.get('next_task','请根据F1分数决定')}"
            )
        elif ttype == "audio_transcription":
            media_url = task.get("media_url", task.get("image_url", ""))
            items_text = "\n".join(f"  段落 {i.get('id', idx+1)}: 请听对应音频片段" for idx, i in enumerate(task.get("items", [])))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"🎵 音频文件: `{media_url}`\n\n"
                f"{task['instruction']}\n\n{items_text}\n\n"
                f"**格式**: JSON 数组 `[{{\"id\":段落编号,\"text\":\"转写内容\"}},...]`\n"
                f"**训练技能**: {kps}\n\n"
                f"Ground Truth:\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 用户提交的 JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: audio_transcription\n\n"
                f"完成后续推荐: {task.get('next_task','请根据WER决定')}"
            )
        elif ttype == "video_tracking":
            media_url = task.get("media_url", task.get("image_url", ""))
            fmt_eg = json.dumps(gt[0]["boxes"][0]) if gt and gt[0].get("boxes") else '{"x":0,"y":0,"w":100,"h":100,"label":"?"}'
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"🎬 视频文件: `{media_url}`\n\n"
                f"{task['instruction']}\n\n"
                f"**标签**: {', '.join(task['labels'])} | **帧数**: {task.get('object_count', '?')} 帧\n"
                f"**格式**: 逐帧标注 `[{{\"frame\":0,\"boxes\":[{fmt_eg}]}}, ...]`\n"
                f"**训练技能**: {kps}\n\n"
                f"---\n"
                f"Ground Truth (用于评分):\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 用户提交的 JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: video_tracking\n\n"
                f"完成后续推荐: {task.get('next_task','请根据平均F1决定')}"
            )
        elif ttype == "video_event":
            fmt = json.dumps(gt[0]) if gt else '{"start_time":0.0,"end_time":1.0,"label":"?"}'
            media_url = task.get("media_url", task.get("image_url", ""))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"🎬 视频文件: `{media_url}`\n\n"
                f"{task['instruction']}\n\n"
                f"**事件类型**: {', '.join(task['labels'])} | **事件数**: {task.get('object_count', '?')} 个\n"
                f"**格式**: 每个事件段 `{fmt}`，放入 JSON 数组。例: `[{fmt}]`\n"
                f"**训练技能**: {kps}\n\n"
                f"---\n"
                f"Ground Truth (用于评分):\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`:\n"
                f"- predictions: 用户提交的 JSON\n"
                f"- ground_truth: {gt_json}\n"
                f"- task_type: video_event\n\n"
                f"完成后续推荐: {task.get('next_task','请根据F1分数决定')}"
            )
        else:
            items_text = "\n".join(f"  {i['id']}. {i['text']}" for i in task.get("items", []))
            content = (
                f"## {task['title']} — 难度: {task['difficulty']}\n\n"
                f"![Task Image]({task['image_url']})\n\n"
                f"{task['instruction']}\n\n{items_text}\n\n"
                f"**标签**: {', '.join(task['labels'])}\n"
                f"**训练技能**: {kps}\n\n"
                f"Ground Truth:\n```json\n{gt_json}\n```\n"
                f"评分时调用 `annotation_check`，task_type: {ttype}"
            )

        metadata: dict[str, Any] = {"task_id": tid, "ground_truth": gt}
        for key in ("pre_annotation", "pre_annotation_mode", "pre_annotation_note"):
            if key in task:
                metadata[key] = task[key]
        if "pre_annotation" in task:
            content += (
                "\n\n> 🤖 **AI 预标注**: 本任务附带 AI 预标注（"
                f"mode={task.get('pre_annotation_mode', 'review')}）。"
                "请在标注台审阅/修正后提交；评分时会同时对比 AI 预标注与你修正后的结果。"
            )
        return ToolResult(content=content, metadata=metadata)
