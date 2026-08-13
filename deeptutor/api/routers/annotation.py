"""Annotation grading router — HTTP wrapper over annotation_check metrics."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from deeptutor.multi_user.context import require_learning_profile_write_access
from deeptutor.multi_user.paths import get_current_learning_profile_root
from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.coach_context import build_annotation_coach_context
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


class ActivityRequest(BaseModel):
    task_id: str = Field(max_length=120)
    mode: str = Field(default="teaching", max_length=40)
    stage: str = Field(default="selected", max_length=60)
    summary: dict[str, Any] = Field(default_factory=dict)


class DraftRequest(BaseModel):
    task_id: str = Field(max_length=120)
    mode: str = Field(default="teaching", max_length=40)
    payload: dict[str, Any]


class AttemptRequest(BaseModel):
    task_id: str = Field(max_length=120)
    task_type: str = Field(default="bbox", max_length=60)
    mode: str = Field(default="teaching", max_length=40)
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=160)
    metrics: dict[str, Any] | None = None
    report: str = Field(default="", max_length=8000)
    grade: bool = True


def _private_store(*, write: bool = False) -> AnnotationAttemptStore:
    if write:
        try:
            require_learning_profile_write_access()
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        root = get_current_learning_profile_root(require_unlocked=True)
    except PermissionError as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    if root is None:
        raise HTTPException(status_code=423, detail="请先解锁学习档案")
    return AnnotationAttemptStore(root)


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


def _grade_annotation(body: dict[str, Any]) -> dict[str, Any]:
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


@router.post("/check")
async def check_annotation(body: dict[str, Any]) -> dict[str, Any]:
    """Grade a single annotation submission without persisting it."""
    return _grade_annotation(body)


@router.post("/activity")
async def update_annotation_activity(body: ActivityRequest) -> dict[str, Any]:
    """Record what the learner is doing so the coach can offer timely help."""
    try:
        current = _private_store(write=True).set_current(
            task_id=body.task_id, mode=body.mode, stage=body.stage, summary=body.summary
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"current": current}


@router.put("/drafts/{task_id}")
async def save_annotation_draft(task_id: str, body: DraftRequest) -> dict[str, Any]:
    if body.task_id != task_id:
        raise HTTPException(status_code=422, detail="路径任务编号与请求内容不一致")
    try:
        draft = _private_store(write=True).save_draft(task_id, body.mode, body.payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"draft": draft}


@router.get("/drafts/{task_id}")
async def get_annotation_draft(task_id: str) -> dict[str, Any]:
    return {"draft": _private_store().get_draft(task_id)}


@router.post("/attempts", status_code=status.HTTP_201_CREATED)
async def submit_annotation_attempt(body: AttemptRequest) -> dict[str, Any]:
    metrics = body.metrics or {}
    report = body.report
    grade_result: dict[str, Any] | None = None
    if body.grade:
        task = _task_bank().get(body.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"找不到任务 {body.task_id}")
        predictions = body.payload.get("predictions", body.payload.get("annotations", []))
        try:
            grade_result = _grade_annotation({
                "task_type": body.task_type,
                "predictions": predictions,
                "ground_truth": task.get("ground_truth", []),
                "image_size": body.payload.get("image_size", ""),
                "pre_annotation": body.payload.get("pre_annotation"),
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"标注内容无法评分：{exc}") from exc
        metrics = grade_result.get("metrics", {})
        report = str(grade_result.get("report", ""))
    try:
        attempt, created = _private_store(write=True).append_attempt(
            task_id=body.task_id,
            task_type=body.task_type,
            mode=body.mode,
            payload=body.payload,
            metrics=metrics,
            report=report,
            idempotency_key=body.idempotency_key,
            source="professional_gateway" if body.mode == "professional" else "teaching_workbench",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"attempt": attempt, "created": created, "grade": grade_result}


@router.get("/attempts")
async def list_annotation_attempts(
    task_id: str = "", limit: int = Query(default=20, ge=1, le=100)
) -> dict[str, Any]:
    return {"attempts": _private_store().list_attempts(task_id=task_id, limit=limit)}


@router.get("/coach-context")
async def annotation_coach_context() -> dict[str, Any]:
    store = _private_store()
    return build_annotation_coach_context(store.root.parent)


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
