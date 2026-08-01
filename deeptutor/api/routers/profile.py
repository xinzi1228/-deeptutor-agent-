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


@router.get("/decisions")
async def decisions(limit: int = 20) -> dict[str, Any]:
    """Recent coach decisions with rationale (lumen audit trail)."""
    from deeptutor.services.learning_records import LearningRecordStore

    rows = LearningRecordStore().list_decisions(limit=max(1, min(limit, 100)))
    return {"decisions": rows}


@router.get("/evaluations")
async def evaluations(limit: int = 10) -> dict[str, Any]:
    """Recent adversarial teaching-plan evaluations."""
    from deeptutor.services.learning_records import LearningRecordStore

    rows = LearningRecordStore().list_evaluations(limit=max(1, min(limit, 50)))
    return {"evaluations": rows}


@router.post("/reflect")
async def reflect() -> dict[str, Any]:
    """Manually trigger memory evolution (EverOS Reflection): merge duplicate
    practice records, promote repeated error patterns to confirmed, archive
    superseded entries. Reversible — nothing is deleted."""
    from deeptutor.services.learning_records import LearningRecordStore

    store = LearningRecordStore()
    result = store.reflect()

    # Mirror a one-line reflection summary into recent.md (async safe path).
    try:
        from deeptutor.services.memory import get_memory_store
        from deeptutor.services.memory.trace import TraceEvent

        memo = get_memory_store()
        event = TraceEvent.new("chat", "memory_reflection", result)
        await memo.emit(event)
        summary = (
            f"记忆整理: 合并 {result['clusters_merged']} 组重复记录, "
            f"归档 {result['records_archived']} 条, 当前 {result['active_records']} 条活跃"
        )
        await memo.append_learning_summary(text=summary, ref=event.id)
    except Exception:
        pass

    return {"reflect": result}


@router.get("/episodes")
async def episodes(days: int = 14) -> dict[str, Any]:
    """Learning records grouped into daily episodes (EverOS timeline)."""
    from deeptutor.services.learning_records import LearningRecordStore

    rows = LearningRecordStore().episodes(days=max(1, min(days, 90)))
    return {"episodes": rows}


@router.get("/foresights")
async def foresights() -> dict[str, Any]:
    """Foresight prediction statistics (hit rate of coach predictions)."""
    from deeptutor.services.learning_records import LearningStats

    return LearningStats().foresight_stats()


@router.get("/facts")
async def facts() -> dict[str, Any]:
    """Atomic facts: knowledge points evidenced as mastered (EverOS atomic_facts)."""
    from deeptutor.services.learning_records import LearningRecordStore

    return LearningRecordStore().facts()
