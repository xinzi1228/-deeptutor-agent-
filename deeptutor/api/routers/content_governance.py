from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from deeptutor.multi_user.context import get_current_user
from deeptutor.services.content_governance.models import (
    ContentRevisionCreate,
    ReviewDecisionCreate,
    SourceRecordCreate,
    StandardConflictCreate,
)
from deeptutor.services.content_governance.review import get_content_governance_service

router = APIRouter()


class SourceRequest(SourceRecordCreate):
    pass


class RevisionRequest(ContentRevisionCreate):
    pass


class ReviewRequest(ReviewDecisionCreate):
    pass


class ConflictRequest(StandardConflictCreate):
    pass


class ConflictResolutionRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)


@router.post("/sources")
async def create_source(payload: SourceRequest) -> dict[str, Any]:
    source = get_content_governance_service().create_source(
        payload,
        actor_id=get_current_user().id,
    )
    return source.model_dump(mode="json")


@router.get("/sources")
async def list_sources() -> dict[str, Any]:
    rows = get_content_governance_service().store.list_sources()
    return {"sources": [row.model_dump(mode="json") for row in rows]}


@router.post("/revisions")
async def create_revision(payload: RevisionRequest) -> dict[str, Any]:
    try:
        revision = get_content_governance_service().submit_revision(
            payload,
            actor_id=get_current_user().id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return revision.model_dump(mode="json")


@router.get("/revisions")
async def list_revisions(status: str | None = Query(default=None)) -> dict[str, Any]:
    rows = get_content_governance_service().store.list_revisions(status=status)
    return {"revisions": [row.model_dump(mode="json") for row in rows]}


@router.post("/revisions/{revision_id}/review")
async def review_revision(revision_id: str, payload: ReviewRequest) -> dict[str, Any]:
    service = get_content_governance_service()
    try:
        decision, published = service.review_revision(
            revision_id,
            payload,
            reviewer_id=get_current_user().id,
            reviewer_kind="human",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    revision = service.store.get_revision(revision_id)
    return {
        "decision": decision.model_dump(mode="json"),
        "revision": revision.model_dump(mode="json") if revision else None,
        "published": published.model_dump(mode="json") if published else None,
    }


@router.get("/conflicts")
async def list_conflicts() -> dict[str, Any]:
    rows = get_content_governance_service().store.list_conflicts()
    return {"conflicts": [row.model_dump(mode="json") for row in rows]}


@router.post("/conflicts")
async def create_conflict(payload: ConflictRequest) -> dict[str, Any]:
    try:
        conflict = get_content_governance_service().report_conflict(
            payload,
            actor_id=get_current_user().id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return conflict.model_dump(mode="json")


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    payload: ConflictResolutionRequest,
) -> dict[str, Any]:
    try:
        conflict = get_content_governance_service().resolve_conflict(
            conflict_id,
            resolution=payload.comment,
            reviewer_id=get_current_user().id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return conflict.model_dump(mode="json")


@router.get("/impacts")
async def list_impacts() -> dict[str, Any]:
    rows = get_content_governance_service().store.list_impacts()
    return {"impacts": [row.model_dump(mode="json") for row in rows]}


@router.get("/published/{content_id}")
async def list_published(content_id: str) -> dict[str, Any]:
    rows = get_content_governance_service().versioning.list_versions(content_id)
    return {"versions": [row.model_dump(mode="json") for row in rows]}
