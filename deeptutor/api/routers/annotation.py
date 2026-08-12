"""Annotation grading router — HTTP wrapper over annotation_check metrics."""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen
from typing import Any

from fastapi import APIRouter, HTTPException

from deeptutor.tools import annotation_check

router = APIRouter()

_SCORERS = {
    "bbox": annotation_check._bbox_dict,
    "classification": annotation_check._classify_dict,
    "judgment": annotation_check._judgment_dict,
    "standard": annotation_check._standard_dict,
    "error_case": annotation_check._error_case_dict,
    "audio_event": annotation_check._audio_event_dict,
    "audio_transcription": annotation_check._audio_transcription_dict,
    "video_tracking": annotation_check._video_tracking_dict,
    "video_event": annotation_check._video_event_dict,
    "ner": annotation_check._ner_dict,
}

_REPORTERS = {
    "classification": annotation_check._classify_report,
    "judgment": annotation_check._judgment_report,
    "standard": annotation_check._standard_report,
    "error_case": annotation_check._error_case_report,
    "audio_event": annotation_check._audio_event_report,
    "audio_transcription": annotation_check._audio_transcription_report,
    "video_tracking": annotation_check._video_tracking_report,
    "video_event": annotation_check._video_event_report,
    "ner": annotation_check._ner_report,
}


def _task_bank() -> dict[str, dict[str, Any]]:
    from deeptutor.services.path_service import get_path_service

    bank_path = get_path_service().get_workspace_dir() / "task_bank.json"
    if not bank_path.exists():
        raise HTTPException(status_code=404, detail="task_bank 不存在")
    try:
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="task_bank 格式错误") from exc
    if not isinstance(bank, dict):
        raise HTTPException(status_code=500, detail="task_bank 必须是对象")
    return {str(key): value for key, value in bank.items() if isinstance(value, dict)}


def _load_json_list(raw: Any, field: str) -> list[dict]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"{field} 不是合法 JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail=f"{field} 必须是 JSON 数组")
    if not all(isinstance(item, dict) for item in raw):
        raise HTTPException(
            status_code=400, detail=f"{field} 的每一项必须是 JSON 对象"
        )
    return raw


@router.post("/check")
async def check_annotation(body: dict[str, Any]) -> dict[str, Any]:
    """Grade a single annotation submission against ground truth.

    Body: ``{task_type, predictions, ground_truth, image_size?, pre_annotation?}``.
    Returns ``{task_type, metrics, report}``. ``task_type`` defaults to ``bbox``.
    When ``pre_annotation`` (AI 预标注, bbox only) is provided, also returns
    ``pre_annotation_metrics`` + ``improvement`` (学生 F1 - AI 预标注 F1) for
    the AI 辅助标注审阅教学 double-scoring flow.
    """
    task_type = str(body.get("task_type") or "bbox").strip()
    if task_type not in _SCORERS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 task_type: {task_type}（可选: {', '.join(sorted(_SCORERS))}）",
        )
    predictions = _load_json_list(body.get("predictions"), "predictions")
    ground_truth = _load_json_list(body.get("ground_truth"), "ground_truth")

    metrics = _SCORERS[task_type](predictions, ground_truth)

    pre_annotation_metrics: dict[str, Any] | None = None
    improvement: float | None = None

    if task_type == "bbox":
        image_size = (1000, 1000)
        raw_size = str(body.get("image_size") or "").strip()
        if raw_size:
            try:
                img_w, img_h = raw_size.split("x")
                image_size = (int(img_w.strip()), int(img_h.strip()))
            except (ValueError, AttributeError):
                pass
        report, _ = annotation_check._bbox_report(
            predictions, ground_truth, image_size=image_size
        )
        raw_pre = body.get("pre_annotation")
        if raw_pre:
            # 双评: 同一 ground_truth 额外评 AI 预标注; 畸形则忽略
            # (合法 JSON 但缺 x/y/w/h 字段会让 _bbox_dict 抛 KeyError), 不阻塞正常评分
            try:
                pre_annotation = _load_json_list(raw_pre, "pre_annotation")
                pre_annotation_metrics = annotation_check._bbox_dict(pre_annotation, ground_truth)
                improvement = round(metrics["f1"] - pre_annotation_metrics["f1"], 4)
            except Exception:
                pre_annotation_metrics = None
                improvement = None
    else:
        report = _REPORTERS[task_type](predictions, ground_truth)

    resp: dict[str, Any] = {"task_type": task_type, "metrics": metrics, "report": report}
    if pre_annotation_metrics is not None:
        resp["pre_annotation_metrics"] = pre_annotation_metrics
        resp["improvement"] = improvement
    return resp


@router.get("/ground-truth/{task_id}")
async def ground_truth(task_id: str) -> dict[str, Any]:
    """Look up a task's ground truth by task id (from task_bank.json)."""
    bank = _task_bank()
    if task_id in bank:
        return {"task_id": task_id, "ground_truth": bank[task_id].get("ground_truth", [])}
    raise HTTPException(status_code=404, detail=f"找不到任务 {task_id}")


@router.get("/tasks")
async def list_annotation_tasks() -> dict[str, Any]:
    """Return safe task summaries for the learner-owned annotation workbench."""
    tasks = []
    for task_id, task in _task_bank().items():
        tasks.append({
            "id": task_id,
            "title": task.get("title", task_id),
            "type": task.get("type", "bbox"),
            "modal": task.get("modal", "image"),
            "difficulty": task.get("difficulty", ""),
            "instruction": task.get("instruction", ""),
        })
    return {"tasks": tasks}


@router.get("/tasks/{task_id}")
async def get_annotation_task(task_id: str) -> dict[str, Any]:
    task = _task_bank().get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"找不到任务 {task_id}")
    return {"task": {"id": task_id, **task}}


@router.get("/label-studio-status")
async def label_studio_status() -> dict[str, Any]:
    """Probe the local optional service so the UI can explain an unavailable iframe."""
    url = "http://127.0.0.1:8080/"
    try:
        with urlopen(Request(url, method="HEAD"), timeout=2) as response:
            available = 200 <= response.status < 500
            return {"available": available, "url": url, "status": response.status}
    except (URLError, OSError, TimeoutError) as exc:
        return {"available": False, "url": url, "detail": str(exc.reason) if isinstance(exc, URLError) else "服务未启动"}
