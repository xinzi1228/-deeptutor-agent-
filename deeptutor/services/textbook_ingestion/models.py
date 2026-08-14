from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewIssue(BaseModel):
    category: str
    message: str
    page: int | None = None
    severity: Literal["review", "error"] = "review"
    resource: str = ""


class TextbookArtifact(BaseModel):
    job_id: str
    markdown_path: str
    manifest_path: str
    source_hash: str
    parser_signature: str
    parser_engine: str
    total_pages: int = 1
    successful_page_count: int = 0
    review_page_count: int = 0
    failed_page_count: int = 0
    review_issues: list[ReviewIssue] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)


class TextbookJob(BaseModel):
    id: str
    original_name: str
    source_path: str
    source_hash: str
    engine: str | None = None
    status: Literal["queued", "running", "needs_review", "completed", "failed", "cancelled"] = "queued"
    progress_message: str = "等待解析"
    total_pages: int = 0
    successful_pages: int = 0
    review_pages: int = 0
    failed_pages: int = 0
    resume_cursor: int = 0
    markdown_path: str = ""
    manifest_path: str = ""
    parser_signature: str = ""
    parser_engine: str = ""
    error: str = ""
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)

