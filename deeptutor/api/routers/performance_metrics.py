from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from deeptutor.multi_user.context import require_learning_profile_write_access
from deeptutor.multi_user.paths import get_current_learning_profile_root
from deeptutor.services.performance_metrics import (
    PerformanceMetricInput,
    PerformanceMetricStore,
)

router = APIRouter()


class PerformanceMetricBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[PerformanceMetricInput]


def _private_store(*, write: bool = False) -> PerformanceMetricStore:
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
    return PerformanceMetricStore(root)


@router.post("/events")
async def create_event(body: PerformanceMetricInput) -> dict[str, bool]:
    _private_store(write=True).append(body)
    return {"accepted": True}


@router.post("/events/batch")
async def create_batch(body: PerformanceMetricBatch) -> dict[str, int]:
    if len(body.events) > 50:
        raise HTTPException(status_code=413, detail="单次最多提交50条性能指标")
    accepted = _private_store(write=True).append_many(body.events)
    return {"accepted": accepted}


@router.get("/summary")
async def get_summary() -> dict:
    return _private_store().summary()
