from __future__ import annotations

from fastapi import APIRouter, HTTPException

from deeptutor.services.student_dashboard import get_student_dashboard_service

router = APIRouter()


def _service():
    try:
        return get_student_dashboard_service()
    except PermissionError as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc


@router.get("/home")
async def student_home() -> dict:
    return _service().home()


@router.get("/growth")
async def student_growth() -> dict:
    return _service().growth()


__all__ = ["router", "student_growth", "student_home"]
