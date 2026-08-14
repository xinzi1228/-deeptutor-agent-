from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from deeptutor.knowledge.manager import KnowledgeBaseManager
from deeptutor.services.knowledge_retrieval.citations import (
    citation_payload,
    normalize_citation,
)
from deeptutor.services.knowledge_retrieval.hybrid import retrieve_knowledge
from deeptutor.services.knowledge_retrieval.reranker import rerank_citations


def _policy(*, accepted: bool, course_id: str = "course-a") -> dict:
    checks = {
        "connectivity": accepted,
        "sample_index": accepted,
        "retrieval_quality": accepted,
        "citation_location": accepted,
        "permission_isolation": accepted,
    }
    return {
        "status": "ready",
        "course_id": course_id,
        "review_status": "approved",
        "review_record_id": "review-1",
        "version": "version-2",
        "provider": "llamaindex",
        "source_type": "textbook",
        "embedding_acceptance": checks,
        "semantic_ready": accepted,
        "semantic_restricted_reason": "" if accepted else "Embedding 五项验收未完成",
    }


def test_keyword_search_returns_real_page_hash_and_review_version(tmp_path: Path) -> None:
    base = tmp_path / "knowledge"
    raw = base / "course-kb" / "raw"
    raw.mkdir(parents=True)
    (raw / "chapter.md").write_text(
        "# 目标检测\n<!-- source-page: 7 -->\n## 边界框\n边界框必须贴合目标边缘。",
        encoding="utf-8",
    )
    (base / "kb_config.json").write_text(
        json.dumps(
            {
                "knowledge_bases": {
                    "course-kb": {
                        "path": "course-kb",
                        "status": "ready",
                        "rag_provider": "llamaindex",
                        "course_id": "course-a",
                        "review_status": "approved",
                        "active_reviewed_version": "v3",
                        "source_type": "textbook",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    [hit] = KnowledgeBaseManager(base).keyword_search_documents(
        "course-kb", "边界框", top_k=3
    )

    assert hit["page"] == "7"
    assert hit["chapter"] == "边界框"
    assert hit["content_hash"].startswith("sha256:")
    assert hit["version"] == "v3"
    assert hit["review_status"] == "approved"


def test_reranker_prefers_standard_and_fuses_retrieval_modes() -> None:
    weak = normalize_citation(
        {"title": "个人笔记", "content": "边界框", "source_type": "user_document", "score": 1},
        retrieval_mode="keyword",
    )
    standard_keyword = normalize_citation(
        {
            "title": "GB/T 42755-2023",
            "content": "边界框标注规程",
            "source_type": "national_standard",
            "score": 0.6,
            "source": "standard.md",
            "page": "12",
        },
        retrieval_mode="keyword",
    )
    standard_semantic = standard_keyword.model_copy(deep=True)
    standard_semantic.retrieval_modes = ["semantic"]

    ranked = rerank_citations(
        [weak, standard_keyword, standard_semantic], query="GB/T 42755-2023 边界框"
    )

    assert ranked[0].source_type == "national_standard"
    assert set(ranked[0].retrieval_modes) == {"keyword", "semantic"}


@pytest.mark.asyncio
async def test_embedding_stays_restricted_until_all_five_checks_pass(monkeypatch) -> None:
    class _Manager:
        def keyword_search_documents(self, *_args, **_kwargs):
            return [
                {
                    "title": "课程教材",
                    "excerpt": "边界框用于圈定目标。",
                    "source": "chapter.md",
                    "page": "2",
                    "source_type": "textbook",
                    "review_status": "approved",
                }
            ]

    resource = SimpleNamespace(id="admin:kb:course-kb", name="course-kb", base_dir=Path("x"))
    monkeypatch.setattr(
        "deeptutor.multi_user.knowledge_access.resolve_for_retrieval",
        lambda *_args, **_kwargs: (resource, _Manager(), _policy(accepted=False)),
    )

    result = await retrieve_knowledge(
        query="什么是边界框", kb_ref="course-kb", course_id="course-a"
    )

    assert result.semantic.enabled is False
    assert result.semantic.restricted is True
    assert result.semantic_count == 0
    assert result.keyword_count == 1
    assert result.citations[0].page == "2"


@pytest.mark.asyncio
async def test_hybrid_filters_unreviewed_and_out_of_course_sources(monkeypatch) -> None:
    class _Manager:
        def keyword_search_documents(self, *_args, **_kwargs):
            return []

    resource = SimpleNamespace(id="admin:kb:course-kb", name="course-kb", base_dir=Path("x"))
    monkeypatch.setattr(
        "deeptutor.multi_user.knowledge_access.resolve_for_retrieval",
        lambda *_args, **_kwargs: (resource, _Manager(), _policy(accepted=True)),
    )

    async def _semantic(**_kwargs):
        return {
            "sources": [
                {
                    "title": "已审核教材",
                    "content": "正确内容",
                    "review_status": "approved",
                    "course_id": "course-a",
                },
                {"title": "待审核内容", "content": "草稿", "review_status": "candidate"},
                {
                    "title": "其他课程",
                    "content": "越权内容",
                    "review_status": "approved",
                    "course_id": "course-b",
                },
                {
                    "title": "旧版本",
                    "content": "已经被新版替换",
                    "review_status": "approved",
                    "course_id": "course-a",
                    "version": "version-1",
                },
            ]
        }

    monkeypatch.setattr("deeptutor.tools.rag_tool.rag_search", _semantic)
    result = await retrieve_knowledge(
        query="目标检测", kb_ref="course-kb", course_id="course-a"
    )

    assert [row.title for row in result.citations] == ["已审核教材"]
    assert result.semantic.enabled is True


def test_student_payload_hides_admin_provenance_details() -> None:
    citation = normalize_citation(
        {
            "title": "教材",
            "source": "private/path/chapter.md",
            "content": "摘要",
            "version": "v2",
            "review_status": "approved",
            "review_record_id": "review-9",
        }
    )

    student = citation_payload(citation, is_admin=False)
    admin = citation_payload(citation, is_admin=True)

    assert "content_hash" not in student
    assert "source_path" not in student
    assert admin["admin_details"]["version"] == "v2"
    assert admin["admin_details"]["source_path"] == "private/path/chapter.md"


def test_retrieval_scope_rejects_other_course(monkeypatch) -> None:
    from deeptutor.multi_user import knowledge_access

    resource = SimpleNamespace(
        id="admin:kb:course-kb",
        name="course-kb",
        base_dir=Path("x"),
        assigned=False,
    )

    class _Manager:
        def get_retrieval_policy(self, _name):
            return _policy(accepted=False, course_id="course-a")

    monkeypatch.setattr(knowledge_access, "resolve_kb", lambda *_args, **_kwargs: resource)
    monkeypatch.setattr(knowledge_access, "manager_for_resource", lambda _resource: _Manager())

    with pytest.raises(HTTPException) as excinfo:
        knowledge_access.resolve_for_retrieval("course-kb", course_id="course-b")

    assert excinfo.value.status_code == 403
