"""Profile API — aggregate learning data for the personal centre dashboard.

Reads learning records from the user's L3 memory (written by the
annotation-coach persona during teaching sessions) and returns
structured dashboards: radar dimensions, F1 trend, skill tree progress.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deeptutor.api.routers.auth import TokenPayload, require_admin

from deeptutor.services.learning_records import LearningStats
from deeptutor.services.learning_communication import (
    audit_learning_copy,
    build_learning_communication_summary,
    render_learning_report,
)

router = APIRouter()


class WorkspaceRebuildRequest(BaseModel):
    rebuild_course: bool = False
    confirmed: bool = False


class InboxCreateRequest(BaseModel):
    raw_text: str
    source: str = "chat"
    context: dict[str, Any] = {}

class InboxOrganizeRequest(BaseModel):
    resolved_to: list[str] = []


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


@router.get("/report-summary")
async def report_summary() -> dict[str, Any]:
    """A concise, evidence-backed learning report for the progress overview."""
    summary = build_learning_communication_summary(_all_records())
    text = render_learning_report(summary)
    return {
        "summary": summary.to_dict(),
        "text": text,
        "quality_warnings": audit_learning_copy(text, kind="report", summary=summary),
    }


@router.get("/workspace")
async def workspace_overview() -> dict[str, Any]:
    from deeptutor.services.learning_workspace import LearningWorkspaceService
    return {"manifest": LearningWorkspaceService().manifest()}


@router.get("/workspace/inbox")
async def list_workspace_inbox() -> dict[str, Any]:
    from deeptutor.services.learning_workspace import LearningWorkspaceService
    return {"items": LearningWorkspaceService().list_inbox()}


@router.get("/workspace/views")
async def workspace_views() -> dict[str, Any]:
    from deeptutor.services.learning_workspace import LearningWorkspaceService
    service = LearningWorkspaceService()
    return {"views": service.views(), "assets": service.asset_versions()}


@router.post("/workspace/inbox")
async def create_workspace_inbox(request: InboxCreateRequest) -> dict[str, Any]:
    from deeptutor.services.learning_workspace import LearningWorkspaceService
    try:
        return {"item": LearningWorkspaceService().add_inbox(request.raw_text, source=request.source, context=request.context)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/workspace/inbox/{item_id}/organize")
async def organize_workspace_inbox(item_id: str, request: InboxOrganizeRequest) -> dict[str, Any]:
    from deeptutor.services.learning_workspace import LearningWorkspaceService
    try: return {"item": LearningWorkspaceService().organize_inbox(item_id, resolved_to=request.resolved_to)}
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/workspace/rebuild")
async def rebuild_workspace(request: WorkspaceRebuildRequest, _: TokenPayload = Depends(require_admin)) -> dict[str, Any]:
    from deeptutor.services.learning_workspace import LearningWorkspaceService
    try:
        return {"result": LearningWorkspaceService().rebuild(rebuild_course=request.rebuild_course, confirmed=request.confirmed)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/trace-log")
async def trace_log(limit: int = 30) -> dict[str, Any]:
    """Teaching-turn trace: records + time-adjacent decisions/interventions, desc by time."""
    from datetime import datetime, timezone

    from deeptutor.services.learning_records import LearningRecordStore

    records = _all_records()
    decisions = LearningRecordStore().list_decisions(limit=100000)

    def _ts(ts_str):
        try:
            parsed = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    def _near(a, b, minutes=10):
        if not a or not b:
            return False
        return abs((a - b).total_seconds()) <= minutes * 60

    traces = []
    for r in records:
        rt = _ts(r.get("timestamp"))
        if not rt:
            continue
        trace = {
            "timestamp": r.get("timestamp"),
            "date": str(rt.date()) if rt else None,
            "type": r.get("type"),
            "task_id": r.get("task_id"),
            "knowledge_point": r.get("knowledge_point"),
            "f1": r.get("f1"),
            "precision": r.get("precision"),
            "recall": r.get("recall"),
            "readiness": r.get("readiness"),
            "knowledge_points": r.get("knowledge_points"),
            "foresight_verified": r.get("foresight_verified"),
            "foresight_hit": r.get("foresight_hit"),
            "intervention": None,
            "decision": None,
        }
        for d in decisions:
            dt = _ts(d.get("timestamp"))
            if not _near(rt, dt):
                continue
            kind = str(d.get("kind") or "")
            if "struggle" in kind:
                trace["intervention"] = {
                    "kind": kind,
                    "target": d.get("target"),
                    "rationale": d.get("rationale"),
                    "timestamp": d.get("timestamp"),
                }
            elif any(k in kind for k in ("task_recommendation", "route_choice", "推进", "readiness")):
                trace["decision"] = {
                    "kind": kind,
                    "target": d.get("target"),
                    "rationale": d.get("rationale"),
                }
        traces.append(trace)

    traces.sort(key=lambda trace: trace["timestamp"] or "", reverse=True)
    return {"traces": traces[: max(1, min(limit, 200))]}


@router.get("/teaching-flow")
async def teaching_flow_state() -> dict[str, Any]:
    """当前教学流程 6 步状态（TeachingFlowEngine flow_state.json 只读）。"""
    from deeptutor.services.teaching_flow import TeachingFlowEngine

    state = TeachingFlowEngine().get_state()
    return {
        "has_flow": bool(state.get("task_id")),
        "task_id": state.get("task_id"),
        "current_step": state.get("current_step"),
        "expert": state.get("expert"),
        "blocked": state.get("blocked"),
        "steps": state.get("steps", {}),
    }


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


@router.get("/competency-tree")
async def competency_tree() -> dict[str, Any]:
    """Full competency tree from data/user/workspace/competency_tree.json."""
    from pathlib import Path

    tree_path = Path(__file__).parent.parent.parent.parent / "data" / "user" / "workspace" / "competency_tree.json"
    if not tree_path.exists():
        return {"tree": None, "error": "competency_tree.json not found"}
    return json.loads(tree_path.read_text(encoding="utf-8"))


@router.get("/annotation-tasks")
async def get_annotation_tasks(modal: str = "") -> dict[str, Any]:
    """Return annotation tasks from the knowledge base DB, optionally filtered by modality."""
    import sqlite3
    from pathlib import Path

    db_path = Path(__file__).parent.parent.parent.parent / "data" / "data_annotation_kb.db"
    if not db_path.exists():
        return {"tasks": {}, "error": "Database not found"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    modal_map_reverse = {"image": 1, "audio": 2, "video": 3, "text": 5}
    mod_id = modal_map_reverse.get(modal) if modal else None

    quizzes = conn.execute("""
        SELECT q.*, kp.point_name FROM quiz q
        JOIN knowledge_point kp ON q.point_id = kp.id
        WHERE q.is_deleted = 0
        """ + ("AND kp.modality_id = ?" if mod_id else "") + """
        ORDER BY q.sort
    """, ((mod_id,) if mod_id else ())).fetchall()

    tasks = {}
    idx = 1
    for q in quizzes:
        options = conn.execute(
            "SELECT * FROM quiz_option WHERE quiz_id = ? ORDER BY sort", (q["id"],)
        ).fetchall()
        if len(options) < 2:
            continue

        letters = [chr(65 + i) for i in range(len(options))]
        correct_idx = next((i for i, o in enumerate(options) if o["is_correct"]), 0)
        correct_label = letters[correct_idx] if correct_idx < len(letters) else "A"

        tid = f"task_q{idx}"
        tasks[tid] = {
            "question": q["question_text"],
            "labels": letters,
            "type": "classification",
            "difficulty": "easy",
            "ground_truth": {"label": correct_label},
            "options": [{"id": letters[i], "text": options[i]["option_text"]} for i in range(len(options))],
            "explanation": q["explanation"] or "",
            "knowledge_point": q["point_name"] or "",
        }
        idx += 1

    conn.close()
    return {"tasks": tasks, "count": len(tasks)}
