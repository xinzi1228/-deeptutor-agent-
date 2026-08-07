"""Annotation grading router — HTTP wrapper over annotation_check metrics."""

from __future__ import annotations

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


def _load_json_list(raw: Any, field: str) -> list[dict]:
    import json

    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"{field} 不是合法 JSON: {exc}") from exc
        if isinstance(parsed, list):
            return parsed
    raise HTTPException(status_code=400, detail=f"{field} 必须是 JSON 数组")


@router.post("/check")
async def check_annotation(body: dict[str, Any]) -> dict[str, Any]:
    """Grade a single annotation submission against ground truth.

    Body: ``{task_type, predictions, ground_truth, image_size?}``.
    Returns ``{task_type, metrics, report}``. ``task_type`` defaults to ``bbox``.
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

    report = ""
    if task_type == "bbox":
        report, _ = annotation_check._bbox_report(predictions, ground_truth)
    elif task_type == "classification":
        report = annotation_check._classify_report(predictions, ground_truth)
    elif task_type == "ner":
        report = annotation_check._ner_report(predictions, ground_truth)
    elif task_type == "audio_event":
        report = annotation_check._audio_event_report(predictions, ground_truth)
    elif task_type == "video_event":
        report = annotation_check._video_event_report(predictions, ground_truth)
    elif task_type == "video_tracking":
        report = annotation_check._video_tracking_report(predictions, ground_truth)

    return {"task_type": task_type, "metrics": metrics, "report": report}
