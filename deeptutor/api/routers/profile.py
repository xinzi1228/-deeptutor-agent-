"""Profile API — aggregate learning data for the personal centre dashboard.

Reads learning records from the user's L3 memory (written by the
annotation-coach persona during teaching sessions) and returns
structured dashboards: radar dimensions, F1 trend, skill tree progress.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from deeptutor.core.i18n import t
from deeptutor.services.learning_records import LearningStats

router = APIRouter()


def _all_records(scope: str | None = None) -> list[dict[str, Any]]:
    """Load learning records: canonical JSONL store first, L3 memory fallback."""
    try:
        from deeptutor.services.learning_records import LearningRecordStore

        records = LearningRecordStore().list_records(scope=scope)
        if records:
            return records
    except Exception:
        pass
    entries = _parse_memory_entries()
    if scope and entries:
        entries = [e for e in entries if e.get("scope", "learner" if e.get("type") == "diagnosis" else "progress") == scope]
    return entries


def _parse_memory_entries() -> list[dict[str, Any]]:
    from deeptutor.services.memory import get_memory_store

    text = get_memory_store().read_l3_concat()
    entries: list[dict[str, Any]] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict) and entry.get("type"):
                entries.append(entry)
        except (json.JSONDecodeError, AttributeError):
            continue
    return entries


@router.get("")
async def profile_overview() -> dict[str, Any]:
    return {"overview": LearningStats().overview()}


@router.get("/radar")
async def radar_dimensions() -> dict[str, Any]:
    return LearningStats().radar()


@router.get("/f1-trend")
async def f1_trend() -> dict[str, Any]:
    return LearningStats().f1_trend()


@router.get("/skill-tree")
async def skill_tree_progress() -> dict[str, Any]:
    return LearningStats().skill_tree()


@router.get("/course-plan")
async def course_plan() -> dict[str, Any]:
    """Return the persisted course plan, rebuilding from the latest brief if
    absent (lumen-style re-runnable build)."""
    from deeptutor.services.course_plan import rebuild

    plan = rebuild(force=False)
    return {"plan": plan if plan is not None else {}}
