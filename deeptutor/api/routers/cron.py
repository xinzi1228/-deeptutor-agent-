"""Cron job management REST API (list/delete/toggle)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from deeptutor.services.cron import get_cron_service

router = APIRouter()


class JobToggleRequest(BaseModel):
    enabled: bool


def _owner_key() -> str:
    """Chat jobs are scoped to the local admin in single-user runs."""
    return "chat:local-admin"


def _job_to_dict(job) -> dict[str, Any]:
    return {
        "id": job.id,
        "name": job.name,
        "message": job.message,
        "schedule": {
            "kind": job.schedule.kind,
            "every_seconds": job.schedule.every_seconds,
            "at_ms": job.schedule.at_ms,
            "expr": job.schedule.expr,
            "tz": job.schedule.tz,
        },
        "enabled": job.enabled,
        "next_run_at_ms": job.state.next_run_at_ms,
        "last_status": job.state.last_status,
        "last_error": job.state.last_error,
    }


@router.get("/cron/jobs")
async def list_jobs() -> dict[str, Any]:
    service = get_cron_service()
    return {"jobs": [_job_to_dict(j) for j in service.list_jobs(owner_key=_owner_key())]}


@router.delete("/cron/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, Any]:
    service = get_cron_service()
    if service.cancel_job(job_id, owner_key=_owner_key()):
        return {"ok": True}
    return {"ok": False, "error": "任务不存在或无权删除"}


@router.patch("/cron/jobs/{job_id}")
async def toggle_job(job_id: str, payload: JobToggleRequest) -> dict[str, Any]:
    service = get_cron_service()
    if service.set_job_enabled(job_id, payload.enabled, owner_key=_owner_key()):
        return {"ok": True, "enabled": payload.enabled}
    return {"ok": False, "error": "任务不存在或无权操作"}
