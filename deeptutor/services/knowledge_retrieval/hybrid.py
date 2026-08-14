from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from deeptutor.services.rag.factory import provider_uses_embedding_versions

from .citations import Citation, citation_payload, normalize_citation
from .reranker import rerank_citations


class SemanticRetrievalStatus(BaseModel):
    enabled: bool = False
    restricted: bool = True
    reason: str = ""
    checks: dict[str, bool] = Field(default_factory=dict)
    provider: str = ""


class HybridRetrievalResult(BaseModel):
    query: str
    kb_id: str
    course_id: str = ""
    citations: list[Citation] = Field(default_factory=list)
    semantic: SemanticRetrievalStatus
    keyword_count: int = 0
    semantic_count: int = 0

    @property
    def context(self) -> str:
        return "\n\n".join(
            f"【{row.title}】{f'（第{row.page}页）' if row.page else ''}\n{row.excerpt}"
            for row in self.citations
            if row.excerpt
        )

    def to_payload(self, *, is_admin: bool = False) -> dict[str, Any]:
        return {
            "query": self.query,
            "kb_id": self.kb_id,
            "course_id": self.course_id,
            "citations": [citation_payload(row, is_admin=is_admin) for row in self.citations],
            "semantic": self.semantic.model_dump(mode="json"),
            "keyword_count": self.keyword_count,
            "semantic_count": self.semantic_count,
            "context": self.context,
        }


def _semantic_status(policy: dict[str, Any]) -> SemanticRetrievalStatus:
    provider = str(policy.get("provider") or "")
    checks = {
        str(key): bool(value)
        for key, value in (policy.get("embedding_acceptance") or {}).items()
    }
    if provider_uses_embedding_versions(provider):
        enabled = bool(policy.get("semantic_ready"))
        return SemanticRetrievalStatus(
            enabled=enabled,
            restricted=not enabled,
            reason="" if enabled else str(policy.get("semantic_restricted_reason") or ""),
            checks=checks,
            provider=provider,
        )
    # Remote/provider-owned indexes do not use the active local embedding
    # version. Their readiness is governed by the provider connection and the
    # KB's ready status, already checked by resolve_for_retrieval().
    return SemanticRetrievalStatus(
        enabled=True,
        restricted=False,
        checks=checks,
        provider=provider,
    )


def _allowed_citation(citation: Citation, *, course_id: str, version: str) -> bool:
    if citation.review_status not in {"approved", "published"}:
        return False
    if course_id and citation.course_id and citation.course_id != course_id:
        return False
    return not (version and citation.version and citation.version != version)


async def retrieve_knowledge(
    *,
    query: str,
    kb_ref: str,
    course_id: str = "",
    top_k: int = 8,
    event_sink=None,
) -> HybridRetrievalResult:
    """Run access-scoped keyword + semantic retrieval and return real citations."""
    query = str(query or "").strip()
    if not query:
        raise ValueError("检索问题不能为空")
    from deeptutor.multi_user.knowledge_access import resolve_for_retrieval

    resource, manager, policy = resolve_for_retrieval(kb_ref, course_id=course_id)
    scoped_course = str(course_id or policy.get("course_id") or "").strip()
    raw_keyword = await asyncio.to_thread(
        manager.keyword_search_documents,
        resource.name,
        query,
        top_k=max(12, top_k * 2),
    )
    defaults = {
        "review_status": policy["review_status"],
        "review_record_id": policy["review_record_id"],
        "version": policy["version"],
    }
    citations = [
        normalize_citation(
            row,
            kb_id=resource.id,
            course_id=scoped_course,
            defaults=defaults,
            retrieval_mode="keyword",
        )
        for row in raw_keyword
    ]
    semantic_status = _semantic_status(policy)
    raw_semantic: list[dict[str, Any]] = []
    if semantic_status.enabled:
        try:
            from deeptutor.tools.rag_tool import rag_search

            semantic_result = await rag_search(
                query=query,
                kb_name=resource.name,
                provider=policy["provider"],
                kb_base_dir=str(resource.base_dir),
                event_sink=event_sink,
            )
            raw_semantic = [
                row
                for row in (semantic_result.get("sources") or [])
                if isinstance(row, dict)
            ]
        except Exception as exc:
            semantic_status.enabled = False
            semantic_status.restricted = True
            semantic_status.reason = f"语义检索本次不可用：{exc}"
    citations.extend(
        normalize_citation(
            row,
            kb_id=resource.id,
            course_id=scoped_course,
            defaults=defaults,
            retrieval_mode="semantic",
        )
        for row in raw_semantic
    )
    approved = [
        row
        for row in citations
        if _allowed_citation(
            row,
            course_id=scoped_course,
            version=str(policy.get("version") or ""),
        )
    ]
    ranked = rerank_citations(
        approved,
        query=query,
        course_id=scoped_course,
        top_k=top_k,
    )
    return HybridRetrievalResult(
        query=query,
        kb_id=resource.id,
        course_id=scoped_course,
        citations=ranked,
        semantic=semantic_status,
        keyword_count=len(raw_keyword),
        semantic_count=len(raw_semantic),
    )


__all__ = [
    "HybridRetrievalResult",
    "SemanticRetrievalStatus",
    "retrieve_knowledge",
]
