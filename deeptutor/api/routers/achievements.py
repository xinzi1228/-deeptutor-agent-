"""achievements router — check-in calendar + badge wall derived from learning records.

Read-only endpoint: the payload is always derived at request time from the
learning records via :class:`deeptutor.services.achievements.AchievementService`;
nothing here writes. Auth is applied at mount time (``dependencies=_auth`` in
``deeptutor/api/main.py``), matching the sibling routers.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/achievements")
async def get_achievements() -> dict:
    """Return the learner's check-in calendar + badge set (derived, no writes)."""
    return _derive_payload()


def _derive_payload() -> dict:
    from deeptutor.services.achievements import AchievementService

    svc = AchievementService()
    return {"checkin": svc.checkin(), "badges": svc.badges()}


__all__ = ["router", "get_achievements"]
