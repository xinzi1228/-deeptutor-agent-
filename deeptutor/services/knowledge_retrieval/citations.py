from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, Field

TrustLevel = Literal["authoritative", "high", "medium", "limited"]

_TRUST_BY_SOURCE: dict[str, TrustLevel] = {
    "national_standard": "authoritative",
    "industry_standard": "authoritative",
    "official_documentation": "high",
    "textbook": "high",
    "built_in": "medium",
    "course_material": "medium",
    "user_document": "limited",
}


class Citation(BaseModel):
    """One source location safe to render beside an answer."""

    id: str
    title: str
    excerpt: str = ""
    source_name: str = ""
    source_path: str = ""
    source_type: str = "user_document"
    page: str = ""
    chapter: str = ""
    trust_level: TrustLevel = "limited"
    score: float = Field(default=0.0, ge=0.0)
    retrieval_modes: list[str] = Field(default_factory=list)
    kb_id: str = ""
    course_id: str = ""
    review_status: str = "approved"
    version: str = ""
    content_hash: str = ""
    review_record_id: str = ""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _score(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _infer_source_type(raw: dict[str, Any], title: str, source_path: str) -> str:
    explicit = _text(raw.get("source_type") or raw.get("kind"))
    if explicit:
        return explicit
    haystack = f"{title} {source_path}".upper()
    if "GB/T" in haystack or "GB " in haystack:
        return "national_standard"
    if "标准" in haystack or "STANDARD" in haystack:
        return "industry_standard"
    if "教材" in haystack or "TEXTBOOK" in haystack:
        return "textbook"
    return "user_document"


def normalize_citation(
    raw: dict[str, Any],
    *,
    kb_id: str = "",
    course_id: str = "",
    defaults: dict[str, Any] | None = None,
    retrieval_mode: str = "",
) -> Citation:
    """Normalize provider-specific source rows into the product citation contract."""
    base = defaults or {}
    title = _text(raw.get("title") or raw.get("name") or raw.get("file_name"))
    source_path = _text(raw.get("source_path") or raw.get("source") or raw.get("file_path"))
    if not title:
        title = source_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or "未命名来源"
    excerpt = _text(raw.get("excerpt") or raw.get("content") or raw.get("snippet"))
    source_type = _infer_source_type(raw, title, source_path)
    trust_level = _text(raw.get("trust_level") or base.get("trust_level"))
    if trust_level not in _TRUST_BY_SOURCE.values():
        trust_level = _TRUST_BY_SOURCE.get(source_type, "limited")
    content_hash = _text(raw.get("content_hash") or raw.get("file_hash"))
    if not content_hash:
        content_hash = "sha256:" + sha256(
            f"{source_path}\n{excerpt}".encode("utf-8")
        ).hexdigest()
    modes = raw.get("retrieval_modes")
    retrieval_modes = [
        _text(value) for value in modes if _text(value)
    ] if isinstance(modes, list) else []
    if retrieval_mode and retrieval_mode not in retrieval_modes:
        retrieval_modes.append(retrieval_mode)
    stable = _text(raw.get("chunk_id") or raw.get("id")) or content_hash.removeprefix(
        "sha256:"
    )[:20]
    citation_id = sha256(
        f"{kb_id}|{stable}|{_text(raw.get('page') or raw.get('page_label'))}".encode("utf-8")
    ).hexdigest()[:24]
    return Citation(
        id=f"citation:{citation_id}",
        title=title,
        excerpt=excerpt[:1200],
        source_name=_text(raw.get("source_name") or title),
        source_path=source_path,
        source_type=source_type,
        page=_text(raw.get("page") or raw.get("page_label") or raw.get("source_page")),
        chapter=_text(raw.get("chapter")),
        trust_level=trust_level,  # type: ignore[arg-type]
        score=_score(raw.get("score")),
        retrieval_modes=retrieval_modes,
        kb_id=_text(raw.get("kb_id") or kb_id),
        course_id=_text(raw.get("course_id") or course_id),
        review_status=_text(raw.get("review_status") or base.get("review_status") or "approved"),
        version=_text(raw.get("version") or base.get("version")),
        content_hash=content_hash,
        review_record_id=_text(raw.get("review_record_id") or base.get("review_record_id")),
    )


def citation_payload(citation: Citation, *, is_admin: bool = False) -> dict[str, Any]:
    """Return the role-appropriate card payload; sensitive provenance is admin-only."""
    payload = citation.model_dump(
        mode="json",
        exclude={
            "content_hash",
            "review_record_id",
            "review_status",
            "version",
            "source_path",
        },
    )
    if is_admin:
        payload["admin_details"] = {
            "content_hash": citation.content_hash,
            "source_path": citation.source_path,
            "version": citation.version,
            "review_status": citation.review_status,
            "review_record_id": citation.review_record_id,
        }
    return payload


__all__ = ["Citation", "TrustLevel", "citation_payload", "normalize_citation"]
