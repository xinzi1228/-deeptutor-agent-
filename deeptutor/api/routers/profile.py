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


@router.get("/knowledge-graph")
async def knowledge_graph() -> dict[str, Any]:
    """Learner knowledge graph: mastery snapshot + per-skill risk chains.

    Reads the persisted graph (built incrementally from learning records) and
    returns the learner's mastered/struggling skills plus, for each struggling
    skill, its missing prerequisites and affected downstream skills/tasks —
    the "风险链" used to personalise teaching.
    """
    from deeptutor.services.graph_query import GraphQueryService
    from deeptutor.services.knowledge_graph import KnowledgeGraphStore

    graph = KnowledgeGraphStore().get()
    if not graph:
        return {"graph": None, "mastery": {"mastered": [], "struggling": []}, "risk_chains": []}

    svc = GraphQueryService(graph)
    mastery = svc.mastery_snapshot()
    risk_chains = []
    for item in mastery["struggling"]:
        risk = svc.risk_path(item["id"])
        risk_chains.append(
            {
                "target": risk["target"],
                "name": risk["target_name"],
                "missing_prereqs": risk["missing_prereqs"],
                "affected_downstream": risk["affected_downstream"],
                "confidence": risk["confidence"],
            }
        )
    # also surface risk chains for not-yet-touched core skills (first 3 by id)
    touched = {x["id"] for x in mastery["mastered"] + mastery["struggling"]}
    for node_id, node in graph.get("nodes", {}).items():
        if node.get("type") != "Skill" or node_id in touched:
            continue
        risk = svc.risk_path(node_id)
        if risk["missing_prereqs"] or risk["struggling"]:
            risk_chains.append(
                {
                    "target": risk["target"],
                    "name": risk["target_name"],
                    "missing_prereqs": risk["missing_prereqs"],
                    "affected_downstream": risk["affected_downstream"],
                    "confidence": risk["confidence"],
                }
            )
    risk_chains.sort(key=lambda x: x["name"])
    return {"graph": {"nodes": len(graph.get("nodes", {})), "edges": len(graph.get("edges", []))}, "mastery": mastery, "risk_chains": risk_chains}


@router.get("/course-plan")
async def course_plan() -> dict[str, Any]:
    """Return the persisted course plan, rebuilding from the latest brief if
    absent (lumen-style re-runnable build)."""
    from deeptutor.services.course_plan import rebuild

    plan = rebuild(force=False)
    return {"plan": plan if plan is not None else {}}


@router.get("/course-plan/docx")
async def course_plan_docx() -> dict[str, Any]:
    """Generate the 学习路径手册 .docx and return its download URL."""
    from deeptutor.services.course_plan import CoursePlanStore, rebuild

    plan = rebuild(force=False) or {}
    artifact = CoursePlanStore().export_docx(plan)
    return {"docx": artifact}


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


@router.get("/coach-metrics")
async def coach_metrics() -> dict[str, Any]:
    """Coach success metrics (agency-agents KPI borrowing)."""
    from deeptutor.services.learning_records import LearningStats

    return LearningStats().coach_metrics()


@router.get("/facts")
async def facts() -> dict[str, Any]:
    """Atomic facts: knowledge points evidenced as mastered (EverOS atomic_facts)."""
    from deeptutor.services.learning_records import LearningRecordStore

    return LearningRecordStore().facts()


@router.get("/teaching-changes")
async def teaching_changes(limit: int = 20) -> dict[str, Any]:
    """Versioned teaching-flow improvement log (Self-Improving loop)."""
    from deeptutor.services.learning_records import TeachingChangelog

    rows = TeachingChangelog().list_changes(limit=max(1, min(limit, 100)))
    return {"changes": rows}
