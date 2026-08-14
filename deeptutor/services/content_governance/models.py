from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SourceType = Literal[
    "national_standard",
    "industry_standard",
    "official_documentation",
    "textbook",
    "paper",
    "project_experience",
]
ClaimScope = Literal["mandatory_requirement", "recommendation", "example_threshold", "background"]
ContentType = Literal["knowledge_article", "question", "scoring_rule", "coach_prompt"]
RevisionStatus = Literal["candidate", "changes_requested", "rejected", "published"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceRecordCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    source_type: SourceType
    normative: bool = True
    claim_scope: ClaimScope = "background"
    standard_number: str = ""
    isbn: str = ""
    edition: str = ""
    publisher: str = ""
    chapter: str = ""
    pages: str = ""
    url: str = ""
    file_hash: str = ""
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_traceability(self):
        if self.source_type in {"national_standard", "industry_standard"} and not self.standard_number:
            raise ValueError("标准来源必须填写标准号")
        if self.source_type == "textbook" and not (self.isbn or self.file_hash):
            raise ValueError("教材来源至少需要 ISBN 或文件哈希")
        if self.source_type == "project_experience":
            if self.normative or self.claim_scope == "mandatory_requirement":
                raise ValueError("项目经验只能标记为建议、示例阈值或背景，不能冒充强制标准")
        if not any((self.standard_number, self.isbn, self.url, self.file_hash)):
            raise ValueError("来源至少需要标准号、ISBN、链接或文件哈希之一")
        return self


class SourceRecord(SourceRecordCreate):
    id: str
    created_by: str
    created_at: str
    schema_version: int = 1


class ContentRevisionCreate(BaseModel):
    content_id: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,160}$")
    content_type: ContentType
    base_version: int = Field(default=0, ge=0)
    change_summary: str = Field(min_length=1, max_length=1000)
    proposed_content: dict[str, Any]
    source_ids: list[str] = Field(min_length=1)
    proposer_kind: Literal["ai", "human"] = "ai"


class ContentRevision(ContentRevisionCreate):
    id: str
    proposed_by: str
    proposed_at: str
    status: RevisionStatus = "candidate"
    published_version: int | None = None
    schema_version: int = 1


class ReviewDecisionCreate(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    comment: str = Field(default="", max_length=4000)


class ReviewDecision(ReviewDecisionCreate):
    id: str
    revision_id: str
    reviewer_id: str
    reviewer_kind: Literal["human"] = "human"
    created_at: str
    schema_version: int = 1


class StandardConflictCreate(BaseModel):
    claim: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=2)


class StandardConflict(StandardConflictCreate):
    id: str
    status: Literal["open", "resolved"] = "open"
    resolution: str = ""
    reported_by: str
    created_at: str
    resolved_by: str = ""
    resolved_at: str = ""
    schema_version: int = 1


class HistoricalImpact(BaseModel):
    id: str
    revision_id: str
    content_id: str
    content_type: ContentType
    original_score_preserved: bool = True
    recalculation_policy: Literal["none", "secondary_result_only"] = "secondary_result_only"
    affected_attempt_ids: list[str] = Field(default_factory=list)
    created_at: str
    schema_version: int = 1


class PublishedContent(BaseModel):
    content_id: str
    content_type: ContentType
    version: int = Field(ge=1)
    revision_id: str
    review_decision_id: str
    content: dict[str, Any]
    source_ids: list[str]
    published_by: str
    published_at: str
    schema_version: int = 1


__all__ = [
    "ContentRevision",
    "ContentRevisionCreate",
    "HistoricalImpact",
    "PublishedContent",
    "ReviewDecision",
    "ReviewDecisionCreate",
    "SourceRecord",
    "SourceRecordCreate",
    "StandardConflict",
    "StandardConflictCreate",
    "utc_now",
]
