from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deeptutor.services.current_learning_task.models import StartTaskCommand, TaskPhase
from deeptutor.services.current_learning_task.service import get_current_learning_task_service

router = APIRouter()


class StartTaskRequest(StartTaskCommand):
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=160)


class TransitionRequest(BaseModel):
    phase: TaskPhase
    expected_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=160)


class ContextPatchRequest(BaseModel):
    draft_ref: str | None = None
    latest_submission_ref: str | None = None
    coach_session_id: str | None = None
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=160)


def _service():
    try:
        return get_current_learning_task_service()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.get("")
async def get_current_task():
    task = _service().get()
    return {"task": task.model_dump(mode="json") if task else None}


@router.put("")
async def start_task(payload: StartTaskRequest):
    command = StartTaskCommand.model_validate(payload.model_dump(exclude={"expected_version", "idempotency_key"}))
    try:
        task, created = _service().start(
            command,
            expected_version=payload.expected_version,
            idempotency_key=payload.idempotency_key,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"task": task.model_dump(mode="json"), "created": created}


@router.post("/transition")
async def transition_task(payload: TransitionRequest):
    try:
        task, created = _service().transition(
            payload.phase,
            expected_version=payload.expected_version,
            idempotency_key=payload.idempotency_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"task": task.model_dump(mode="json"), "created": created}


@router.patch("/context")
async def patch_task_context(payload: ContextPatchRequest):
    try:
        task, created = _service().patch_context(
            draft_ref=payload.draft_ref,
            latest_submission_ref=payload.latest_submission_ref,
            coach_session_id=payload.coach_session_id,
            expected_version=payload.expected_version,
            idempotency_key=payload.idempotency_key,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"task": task.model_dump(mode="json"), "created": created}
