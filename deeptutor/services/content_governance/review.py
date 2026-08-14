from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from deeptutor.services.path_service import get_path_service

from .models import (
    ContentRevision,
    ContentRevisionCreate,
    PublishedContent,
    ReviewDecision,
    ReviewDecisionCreate,
    SourceRecord,
    SourceRecordCreate,
    StandardConflict,
    StandardConflictCreate,
    utc_now,
)
from .store import ContentGovernanceStore
from .versioning import ContentVersioningService


class ContentGovernanceService:
    def __init__(self, store: ContentGovernanceStore):
        self.store = store
        self.versioning = ContentVersioningService(store)

    def create_source(self, payload: SourceRecordCreate, *, actor_id: str) -> SourceRecord:
        source = SourceRecord(
            **payload.model_dump(),
            id=f"source_{uuid4().hex}",
            created_by=actor_id,
            created_at=utc_now(),
        )
        return self.store.save_source(source)

    def submit_revision(
        self,
        payload: ContentRevisionCreate,
        *,
        actor_id: str,
    ) -> ContentRevision:
        missing = [source_id for source_id in payload.source_ids if not self.store.get_source(source_id)]
        if missing:
            raise ValueError(f"候选修订引用了不存在的来源：{', '.join(missing)}")
        revision = ContentRevision(
            **payload.model_dump(),
            id=f"revision_{uuid4().hex}",
            proposed_by=actor_id,
            proposed_at=utc_now(),
            status="candidate",
        )
        return self.store.save_revision(revision)

    def review_revision(
        self,
        revision_id: str,
        payload: ReviewDecisionCreate,
        *,
        reviewer_id: str,
        reviewer_kind: str,
    ) -> tuple[ReviewDecision, PublishedContent | None]:
        if reviewer_kind != "human":
            raise PermissionError("AI 只能提交候选修订，不能执行最终审核")
        revision = self.store.get_revision(revision_id)
        if revision is None:
            raise FileNotFoundError("找不到候选修订")
        if revision.status not in {"candidate", "changes_requested"}:
            raise ValueError("该候选修订已经完成审核")
        decision = ReviewDecision(
            **payload.model_dump(),
            id=f"decision_{uuid4().hex}",
            revision_id=revision.id,
            reviewer_id=reviewer_id,
            reviewer_kind="human",
            created_at=utc_now(),
        )
        self.store.save_decision(decision)
        published: PublishedContent | None = None
        if decision.decision == "approve":
            published = self.versioning.publish(revision, decision)
            revision.status = "published"
            revision.published_version = published.version
        elif decision.decision == "request_changes":
            revision.status = "changes_requested"
        else:
            revision.status = "rejected"
        self.store.save_revision(revision)
        return decision, published

    def report_conflict(
        self,
        payload: StandardConflictCreate,
        *,
        actor_id: str,
    ) -> StandardConflict:
        missing = [source_id for source_id in payload.source_ids if not self.store.get_source(source_id)]
        if missing:
            raise ValueError(f"来源冲突引用了不存在的来源：{', '.join(missing)}")
        conflict = StandardConflict(
            **payload.model_dump(),
            id=f"conflict_{uuid4().hex}",
            reported_by=actor_id,
            created_at=utc_now(),
        )
        return self.store.save_conflict(conflict)

    def resolve_conflict(
        self,
        conflict_id: str,
        *,
        resolution: str,
        reviewer_id: str,
    ) -> StandardConflict:
        conflict = self.store.get_conflict(conflict_id)
        if conflict is None:
            raise FileNotFoundError("找不到来源冲突记录")
        if conflict.status == "resolved":
            raise ValueError("该来源冲突已经解决")
        conflict.status = "resolved"
        conflict.resolution = resolution.strip()
        conflict.resolved_by = reviewer_id
        conflict.resolved_at = utc_now()
        return self.store.save_conflict(conflict)


_service: ContentGovernanceService | None = None


def get_content_governance_service(root: Path | None = None) -> ContentGovernanceService:
    global _service
    if root is not None:
        return ContentGovernanceService(ContentGovernanceStore(root))
    if _service is None:
        governance_root = get_path_service().workspace_root / "content-governance"
        _service = ContentGovernanceService(ContentGovernanceStore(governance_root))
    return _service


__all__ = ["ContentGovernanceService", "get_content_governance_service"]
