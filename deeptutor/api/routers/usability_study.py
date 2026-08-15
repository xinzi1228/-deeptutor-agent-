"""Usability study API router.

Admin-gated endpoints for the competition evidence workflow: research plan,
consent records, immutable study runs, event import, report generation,
deletion requests, and evidence-package export. Teacher accounts can only
reach their own authorised tests through profile grants (the learning-profiles
policy), never raw study materials.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deeptutor.api.routers.auth import require_admin
from deeptutor.multi_user.paths import get_admin_path_service
from deeptutor.services.usability_study.models import (
    ConsentRecord,
    DeletionRequest,
    Issue,
    ManualCorrection,
    Quote,
    StudyEvent,
    StudyRun,
)
from deeptutor.services.usability_study.report import DRAFT_MARK, UsabilityReportGenerator
from deeptutor.services.usability_study.store import UsabilityStudyStore

router = APIRouter(dependencies=[Depends(require_admin)])


def _store() -> UsabilityStudyStore:
    root = get_admin_path_service().get_workspace_dir() / "competition-evidence"
    return UsabilityStudyStore(root)


def _generator() -> UsabilityReportGenerator:
    return UsabilityReportGenerator(_store())


class RunCreateRequest(BaseModel):
    participant_id: str
    round: str  # "A" | "B"
    scenario: str = "traffic-road-vehicle-pedestrian"
    task_version: str
    content_version: str = ""
    model_config_ref: str = ""
    label_studio_status: str = "n/a"
    device_conditions: str = ""
    consent: list[ConsentRecord] = Field(default_factory=list)


class EventsCreateRequest(BaseModel):
    events: list[StudyEvent]


class CorrectionRequest(BaseModel):
    run_id: str
    metric_path: str
    original: Any = None
    corrected: Any = None
    reason: str
    operator: str


class DeletionCreateRequest(BaseModel):
    participant_id: str
    scope: str = "retention"
    requested_by: str = ""


class IssueCreateRequest(BaseModel):
    severity: str
    summary: str
    evidence: str = ""
    fix_commit: str = ""
    retest_result: str = ""
    category: str = "observed"


class QuoteCreateRequest(BaseModel):
    participant_id: str
    round: str
    text: str
    approved: bool = False
    context: str = ""


@router.get("/runs")
async def list_runs() -> dict[str, Any]:
    store = _store()
    return {
        "runs": [run.model_dump(mode="json") for run in store.list_runs()],
        "issues": [issue.model_dump(mode="json") for issue in store.list_issues()],
        "quotes": [quote.model_dump(mode="json") for quote in store.list_quotes()],
        "deletions": [
            req.model_dump(mode="json") for req in store.list_deletion_requests()
        ],
        "corrections": [
            c.model_dump(mode="json") for c in store.list_corrections()
        ],
    }


@router.post("/runs")
async def create_run(payload: RunCreateRequest) -> dict[str, Any]:
    try:
        run = StudyRun(
            participant_id=payload.participant_id,
            round=payload.round,  # type: ignore[arg-type]
            scenario=payload.scenario,
            task_version=payload.task_version,
            content_version=payload.content_version,
            model_config_ref=payload.model_config_ref,
            label_studio_status=payload.label_studio_status,
            device_conditions=payload.device_conditions,
            consent=payload.consent,
        )
        _store().add_run(run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run": run.model_dump(mode="json")}


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    store = _store()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    events = store.list_events(run_id)
    return {
        "run": run.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in events],
    }


@router.post("/runs/{run_id}/events")
async def add_events(run_id: str, payload: EventsCreateRequest) -> dict[str, Any]:
    store = _store()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    events = [StudyEvent(**{**event.model_dump(), "run_id": run_id}) for event in payload.events]
    store.add_events(events)
    return {"count": len(events)}


@router.post("/corrections")
async def add_correction(payload: CorrectionRequest) -> dict[str, Any]:
    store = _store()
    if store.get_run(payload.run_id) is None:
        raise HTTPException(status_code=404, detail="运行不存在")
    correction = ManualCorrection(
        run_id=payload.run_id,
        metric_path=payload.metric_path,
        original=payload.original,
        corrected=payload.corrected,
        reason=payload.reason,
        operator=payload.operator,
    )
    store.add_correction(correction)
    return {"correction": correction.model_dump(mode="json")}


@router.post("/deletions")
async def request_deletion(payload: DeletionCreateRequest) -> dict[str, Any]:
    store = _store()
    request = DeletionRequest(
        participant_id=payload.participant_id,
        scope=payload.scope,  # type: ignore[arg-type]
        requested_by=payload.requested_by,
    )
    store.add_deletion_request(request)
    return {"request": request.model_dump(mode="json")}


@router.post("/deletions/{participant_id}/action")
async def action_deletion(participant_id: str, scope: str = "retention") -> dict[str, Any]:
    store = _store()
    done = store.mark_deletion_actioned(participant_id, scope=scope, requested_by="admin")
    if not done:
        raise HTTPException(status_code=404, detail="删除请求不存在")
    # Regenerate the report excluding the participant, bumping the version.
    report = _generator().recompute_after_deletion(participant_id)
    return {"actioned": True, "report": report}


@router.post("/issues")
async def add_issue(payload: IssueCreateRequest) -> dict[str, Any]:
    issue = Issue(
        severity=payload.severity,  # type: ignore[arg-type]
        summary=payload.summary,
        evidence=payload.evidence,
        fix_commit=payload.fix_commit,
        retest_result=payload.retest_result,
        category=payload.category,  # type: ignore[arg-type]
    )
    _store().add_issue(issue)
    return {"issue": issue.model_dump(mode="json")}


@router.post("/quotes")
async def add_quote(payload: QuoteCreateRequest) -> dict[str, Any]:
    quote = Quote(
        participant_id=payload.participant_id,
        round=payload.round,  # type: ignore[arg-type]
        text=payload.text,
        approved=payload.approved,
        context=payload.context,
    )
    _store().add_quote(quote)
    return {"quote": quote.model_dump(mode="json")}


@router.get("/report")
async def get_report() -> dict[str, Any]:
    return _generator().generate()


@router.get("/export")
async def export_package() -> dict[str, Any]:
    store = _store()
    package = _generator().export_package(store.root)
    package["draft_mark"] = DRAFT_MARK if package["draft"] else ""
    return package
