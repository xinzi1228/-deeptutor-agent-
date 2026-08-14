from __future__ import annotations

import re

from .citations import Citation

_SOURCE_WEIGHT = {
    "national_standard": 0.34,
    "industry_standard": 0.32,
    "official_documentation": 0.27,
    "textbook": 0.24,
    "built_in": 0.20,
    "course_material": 0.18,
    "user_document": 0.10,
}


def _normalized_provider_score(value: float) -> float:
    if value <= 0:
        return 0.0
    return min(value, 1.0) if value <= 1 else min(value / 10.0, 1.0)


def rank_score(citation: Citation, *, query: str, course_id: str = "") -> float:
    """Deterministically rank by authority, exactness, scope, version and fusion."""
    score = 0.25 * _normalized_provider_score(citation.score)
    score += _SOURCE_WEIGHT.get(citation.source_type, 0.08)
    needle = query.strip().casefold()
    haystack = f"{citation.title}\n{citation.excerpt}".casefold()
    if needle and needle in haystack:
        score += 0.18
    standard_numbers = re.findall(r"(?:GB|GB/T|ISO|IEC)[\s/-]*[A-Z0-9.-]+", query.upper())
    if standard_numbers and any(value.casefold() in haystack for value in standard_numbers):
        score += 0.14
    if course_id and citation.course_id == course_id:
        score += 0.10
    if citation.version:
        score += 0.04
    if {"keyword", "semantic"}.issubset(citation.retrieval_modes):
        score += 0.08
    return round(score, 6)


def rerank_citations(
    citations: list[Citation], *, query: str, course_id: str = "", top_k: int = 8
) -> list[Citation]:
    """Merge matching chunks and return an ordered, bounded citation list."""
    merged: dict[tuple[str, str, str], Citation] = {}
    for citation in citations:
        key = (citation.source_path or citation.source_name, citation.page, citation.excerpt[:160])
        previous = merged.get(key)
        if previous is None:
            merged[key] = citation.model_copy(deep=True)
            continue
        previous.score = max(previous.score, citation.score)
        previous.retrieval_modes = list(
            dict.fromkeys([*previous.retrieval_modes, *citation.retrieval_modes])
        )
        if previous.trust_level == "limited" and citation.trust_level != "limited":
            previous.trust_level = citation.trust_level
        if not previous.content_hash and citation.content_hash:
            previous.content_hash = citation.content_hash
    ranked = list(merged.values())
    for citation in ranked:
        citation.score = rank_score(citation, query=query, course_id=course_id)
    ranked.sort(key=lambda row: (-row.score, row.title.casefold(), row.page))
    return ranked[: max(1, min(int(top_k or 8), 20))]


__all__ = ["rank_score", "rerank_citations"]
