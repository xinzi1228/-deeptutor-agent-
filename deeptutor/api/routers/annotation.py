"""Annotation grading router — HTTP wrapper over annotation_check metrics."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from deeptutor.multi_user.context import (
    get_current_learning_profile,
    require_learning_profile_write_access,
)
from deeptutor.multi_user.paths import get_current_learning_profile_root
from deeptutor.services.annotation_attempts import (
    AnnotationAttemptStore,
    AnnotationEditLeaseStore,
    EditLeaseConflict,
    EditLeaseVersionMismatch,
)
from deeptutor.services.annotation_scoring import AnnotationScoreStore, BboxScorer
from deeptutor.services.coach_context import build_annotation_coach_context
from deeptutor.services.label_studio_gateway import (
    LabelStudioClient,
    LabelStudioProfileMap,
    LabelStudioUnavailable,
)
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

PRACTICE_TASK_TYPES = {"bbox", "audio_event", "audio_transcription", "video_event", "video_tracking", "ner"}


class ActivityRequest(BaseModel):
    task_id: str = Field(max_length=120)
    mode: str = Field(default="teaching", max_length=40)
    stage: str = Field(default="selected", max_length=60)
    summary: dict[str, Any] = Field(default_factory=dict)


class DraftRequest(BaseModel):
    task_id: str = Field(max_length=120)
    mode: str = Field(default="teaching", max_length=40)
    payload: dict[str, Any]
    browser_session_id: str = Field(min_length=8, max_length=160)
    lease_version: int = Field(ge=1)


class AttemptRequest(BaseModel):
    task_id: str = Field(max_length=120)
    task_type: str = Field(default="bbox", max_length=60)
    mode: str = Field(default="teaching", max_length=40)
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=160)
    metrics: dict[str, Any] | None = None
    report: str = Field(default="", max_length=8000)
    grade: bool = True
    browser_session_id: str = Field(min_length=8, max_length=160)
    lease_version: int = Field(ge=1)


class EditLeaseRequest(BaseModel):
    mode: str = Field(max_length=40)
    browser_session_id: str = Field(min_length=8, max_length=160)
    takeover: bool = False
    expected_version: int | None = Field(default=None, ge=1)
    saved_draft_version: int = Field(default=0, ge=0)


class EditCheckpointRequest(BaseModel):
    mode: str = Field(max_length=40)
    browser_session_id: str = Field(min_length=8, max_length=160)
    expected_version: int = Field(ge=1)
    draft_version: int = Field(ge=1)


class EditLeaseReleaseRequest(BaseModel):
    browser_session_id: str = Field(min_length=8, max_length=160)
    expected_version: int = Field(ge=1)


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


def _edit_lease_store(*, write: bool = False) -> AnnotationEditLeaseStore:
    store = _private_store(write=write)
    return AnnotationEditLeaseStore(store.root.parent)


def _require_owned_lease(
    task_id: str, *, mode: str, browser_session_id: str, lease_version: int
) -> dict[str, Any]:
    lease = _edit_lease_store().get(task_id)
    if not lease:
        raise HTTPException(status_code=409, detail="编辑权已过期，请重新进入任务")
    if (
        lease.get("mode") != mode
        or lease.get("browser_session_id") != browser_session_id
        or int(lease.get("version") or 0) != lease_version
    ):
        raise HTTPException(status_code=409, detail="该任务的编辑权已变化，当前页面已转为只读")
    return lease


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
    raw_ground_truth = body.get("ground_truth")
    if isinstance(raw_ground_truth, dict):
        raw_ground_truth = [raw_ground_truth]
    ground_truth = _load_json_list(raw_ground_truth, "ground_truth")

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
        reference_version = str(body.get("reference_version") or "provided-ground-truth")
        score = BboxScorer().score(
            predictions,
            ground_truth,
            reference_version=reference_version,
            image_size=image_size,
        )
        metrics = score.metrics
        report = score.report
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
    if task_type == "bbox":
        resp["scoring"] = {
            "rule_version": score.rule_version,
            "reference_version": score.reference_version,
            "score_hash": score.score_hash,
        }
    if pre_annotation_metrics is not None:
        resp["pre_annotation_metrics"] = pre_annotation_metrics
        resp["improvement"] = improvement
    return resp


def _payload_image_size(payload: dict[str, Any]) -> tuple[int, int]:
    raw = str(payload.get("image_size") or "").lower()
    try:
        width, height = raw.split("x", maxsplit=1)
        return max(1, int(width)), max(1, int(height))
    except (TypeError, ValueError):
        return 1000, 1000


def _reference_version(task_id: str, ground_truth: Any) -> str:
    canonical = json.dumps(ground_truth, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"task-bank:{task_id}:sha256:{digest}"


def _record_formal_score(store: AnnotationAttemptStore, attempt: dict[str, Any]) -> dict[str, Any] | None:
    if attempt.get("task_type") != "bbox":
        return None
    task_id = str(attempt.get("task_id") or "")
    task = _task_bank().get(task_id)
    payload = attempt.get("payload") if isinstance(attempt.get("payload"), dict) else {}
    predictions = payload.get("predictions", [])
    ground_truth = task.get("ground_truth", []) if isinstance(task, dict) else []
    if not isinstance(predictions, list) or not isinstance(ground_truth, list):
        return None
    score = BboxScorer().score(
        [row for row in predictions if isinstance(row, dict)],
        [row for row in ground_truth if isinstance(row, dict)],
        reference_version=_reference_version(task_id, ground_truth),
        image_size=_payload_image_size(payload),
    )
    return AnnotationScoreStore(store.root.parent).record(
        task_id=task_id,
        attempt_id=str(attempt.get("id") or ""),
        metrics=score.metrics,
        rule_version=score.rule_version,
        reference_version=score.reference_version,
        score_hash=score.score_hash,
    )


async def _sync_pending_submission(
    store: AnnotationAttemptStore, pending: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    if pending.get("sync_status") == "synced" and isinstance(pending.get("revision"), dict):
        return store.finalize_submission(str(pending.get("idempotency_key") or ""))
    task_id = str(pending.get("task_id") or "")
    task = _task_bank().get(task_id)
    if task is None:
        raise ValueError(f"找不到任务 {task_id}")
    access = get_current_learning_profile()
    if access is None:
        raise PermissionError("请先解锁学习档案")
    root = store.root.parent
    mapping = LabelStudioProfileMap.load(root, access.profile_id)
    client = LabelStudioClient()
    _project_id, ls_task_id = await client.ensure_task(mapping, task_id, task, root)
    payload = pending.get("payload") if isinstance(pending.get("payload"), dict) else {}
    raw_predictions = payload.get("predictions", payload.get("annotations", []))
    predictions = raw_predictions if isinstance(raw_predictions, list) else []
    revision = await client.create_annotation_revision(
        ls_task_id=ls_task_id,
        task_type=str(pending.get("task_type") or "bbox"),
        predictions=[row for row in predictions if isinstance(row, dict)],
        idempotency_key=str(pending.get("idempotency_key") or ""),
        image_size=_payload_image_size(payload),
    )
    store.mark_submission_synced(str(pending["idempotency_key"]), revision=revision)
    store.mark_draft_sync_status(task_id, "synced", revision=revision)
    return store.finalize_submission(str(pending["idempotency_key"]))


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


@router.get("/edit-leases/{task_id}")
async def get_annotation_edit_lease(task_id: str) -> dict[str, Any]:
    return {"lease": _edit_lease_store().get(task_id)}


@router.post("/edit-leases/{task_id}")
async def acquire_annotation_edit_lease(
    task_id: str, body: EditLeaseRequest
) -> dict[str, Any]:
    try:
        lease = _edit_lease_store(write=True).acquire(
            task_id,
            mode=body.mode,
            browser_session_id=body.browser_session_id,
            takeover=body.takeover,
            expected_version=body.expected_version,
            saved_draft_version=body.saved_draft_version,
        )
    except EditLeaseConflict as exc:
        current = _edit_lease_store().get(task_id)
        raise HTTPException(
            status_code=409, detail={"message": str(exc), "lease": current}
        ) from exc
    except EditLeaseVersionMismatch as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"lease": lease}


@router.post("/edit-leases/{task_id}/checkpoint")
async def checkpoint_annotation_edit_lease(
    task_id: str, body: EditCheckpointRequest
) -> dict[str, Any]:
    try:
        lease = _edit_lease_store(write=True).mark_checkpoint(
            task_id,
            mode=body.mode,
            browser_session_id=body.browser_session_id,
            expected_version=body.expected_version,
            draft_version=body.draft_version,
        )
    except EditLeaseConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EditLeaseVersionMismatch as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"lease": lease}


@router.delete("/edit-leases/{task_id}")
async def release_annotation_edit_lease(
    task_id: str, body: EditLeaseReleaseRequest
) -> dict[str, Any]:
    released = _edit_lease_store(write=True).release(
        task_id,
        browser_session_id=body.browser_session_id,
        expected_version=body.expected_version,
    )
    return {"released": released}


@router.put("/drafts/{task_id}")
async def save_annotation_draft(task_id: str, body: DraftRequest) -> dict[str, Any]:
    if body.task_id != task_id:
        raise HTTPException(status_code=422, detail="路径任务编号与请求内容不一致")
    _require_owned_lease(
        task_id,
        mode=body.mode,
        browser_session_id=body.browser_session_id,
        lease_version=body.lease_version,
    )
    try:
        draft = _private_store(write=True).save_draft(task_id, body.mode, body.payload)
        lease = _edit_lease_store(write=True).mark_checkpoint(
            task_id,
            mode=body.mode,
            browser_session_id=body.browser_session_id,
            expected_version=body.lease_version,
            draft_version=int(draft["version"]),
        )
    except (EditLeaseConflict, EditLeaseVersionMismatch) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"draft": draft, "lease": lease}


@router.get("/drafts/{task_id}")
async def get_annotation_draft(task_id: str) -> dict[str, Any]:
    return {"draft": _private_store().get_draft(task_id)}


@router.post("/attempts", status_code=status.HTTP_201_CREATED)
async def submit_annotation_attempt(body: AttemptRequest) -> dict[str, Any]:
    _require_owned_lease(
        body.task_id,
        mode=body.mode,
        browser_session_id=body.browser_session_id,
        lease_version=body.lease_version,
    )
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
                "reference_version": _reference_version(body.task_id, task.get("ground_truth", [])),
                "image_size": body.payload.get("image_size", ""),
                "pre_annotation": body.payload.get("pre_annotation", task.get("pre_annotation")),
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"标注内容无法评分：{exc}") from exc
        metrics = grade_result.get("metrics", {})
        report = str(grade_result.get("report", ""))
    store = _private_store(write=True)
    try:
        pending, _queued = store.queue_submission(
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
    try:
        attempt, created = await _sync_pending_submission(store, pending)
    except LabelStudioUnavailable as exc:
        retry = store.mark_submission_retry(body.idempotency_key, str(exc))
        store.mark_draft_sync_status(body.task_id, "retry_pending", detail=str(exc))
        return {
            "finalized": False,
            "sync_status": "retry_pending",
            "pending": {key: retry.get(key) for key in ("id", "task_id", "retry_count", "last_error")},
            "local_check": grade_result,
            "detail": "已暂存到当前学习档案；Label Studio 恢复后会自动重试。当前结果仅为本地检查，不计入正式成绩。",
        }
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    score_record = _record_formal_score(store, attempt)
    return {
        "finalized": True,
        "sync_status": "synced",
        "attempt": attempt,
        "created": created,
        "grade": grade_result,
        "revision": attempt.get("revision", {}),
        "score_record": score_record,
    }


@router.post("/attempts/retry-pending")
async def retry_pending_annotation_attempts() -> dict[str, Any]:
    store = _private_store(write=True)
    completed: list[dict[str, Any]] = []
    still_pending: list[dict[str, Any]] = []
    for pending in store.list_pending_submissions(limit=10):
        try:
            attempt, created = await _sync_pending_submission(store, pending)
            completed.append({"attempt": attempt, "created": created, "score_record": _record_formal_score(store, attempt)})
        except LabelStudioUnavailable as exc:
            retry = store.mark_submission_retry(str(pending.get("idempotency_key") or ""), str(exc))
            store.mark_draft_sync_status(str(pending.get("task_id") or ""), "retry_pending", detail=str(exc))
            still_pending.append({key: retry.get(key) for key in ("id", "task_id", "retry_count", "last_error")})
        except (PermissionError, ValueError) as exc:
            still_pending.append({"id": pending.get("id"), "task_id": pending.get("task_id"), "last_error": str(exc)})
    return {"completed": completed, "pending": still_pending}


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
async def list_annotation_tasks(practice_only: bool = False) -> dict[str, Any]:
    """Return safe task summaries for the learner-owned annotation workbench.

    ``practice_only`` keeps only hands-on annotation tasks (bbox/audio/video/ner);
    theory tasks (classification/judgment/standard/error_case) belong to the chat.
    """
    tasks = []
    for task_id, task in _task_bank().items():
        task_type = task.get("type", "bbox")
        if practice_only and task_type not in PRACTICE_TASK_TYPES:
            continue
        tasks.append({
            "id": task_id,
            "title": task.get("title", task_id),
            "type": task_type,
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
    safe_task = {
        key: value
        for key, value in task.items()
        if key not in {"ground_truth", "pre_annotation", "pre_annotation_note"}
    }
    return {"task": {"id": task_id, **safe_task}}


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
