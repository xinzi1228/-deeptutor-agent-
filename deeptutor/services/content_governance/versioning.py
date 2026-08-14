from __future__ import annotations

from uuid import uuid4

from .models import ContentRevision, HistoricalImpact, PublishedContent, ReviewDecision, utc_now
from .store import ContentGovernanceStore


class ContentVersioningService:
    def __init__(self, store: ContentGovernanceStore):
        self.store = store

    def publish(
        self,
        revision: ContentRevision,
        decision: ReviewDecision,
    ) -> PublishedContent:
        if decision.decision != "approve" or decision.reviewer_kind != "human":
            raise PermissionError("只有人工审核通过的候选修订可以发布")
        existing = self.list_versions(revision.content_id)
        latest = existing[-1].version if existing else 0
        version = max(latest + 1, revision.base_version + 1)
        published = PublishedContent(
            content_id=revision.content_id,
            content_type=revision.content_type,
            version=version,
            revision_id=revision.id,
            review_decision_id=decision.id,
            content=revision.proposed_content,
            source_ids=revision.source_ids,
            published_by=decision.reviewer_id,
            published_at=utc_now(),
        )
        self.store.save_published(published)
        if revision.content_type in {"question", "scoring_rule"}:
            self.store.save_impact(
                HistoricalImpact(
                    id=f"impact_{uuid4().hex}",
                    revision_id=revision.id,
                    content_id=revision.content_id,
                    content_type=revision.content_type,
                    original_score_preserved=True,
                    recalculation_policy="secondary_result_only",
                    created_at=utc_now(),
                )
            )
        return published

    def list_versions(self, content_id: str) -> list[PublishedContent]:
        return self.store.list_published(content_id)


__all__ = ["ContentVersioningService"]
