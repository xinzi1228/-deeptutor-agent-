from __future__ import annotations

import json
from pathlib import Path

import pytest

from deeptutor.services.content_governance.models import SourceRecordCreate
from deeptutor.services.content_governance.review import get_content_governance_service
from deeptutor.services.textbook_ingestion import TextbookJobStore
from deeptutor.tools import textbook_candidate_tool as module
from deeptutor.tools.textbook_candidate_tool import TextbookCandidateTool


@pytest.fixture
def controlled_textbook(tmp_path: Path, monkeypatch):
    root = tmp_path / "textbooks"
    output = root / "outputs" / "job-output"
    output.mkdir(parents=True)
    markdown = output / "document.md"
    markdown.write_text(
        "---\nartifact_type: textbook_markdown\nsource_hash: abc\n---\n\n<!-- source-page: 1 -->\n# 数据标注",
        encoding="utf-8",
    )
    source = tmp_path / "original.pdf"
    source.write_bytes(b"pdf")
    store = TextbookJobStore(root)
    job = store.create(source_path=source, original_name="教材.pdf", source_hash="abc", engine="markitdown")
    store.update(
        job.id,
        status="completed",
        total_pages=1,
        markdown_path=str(markdown),
        manifest_path=str(output / "artifact.json"),
    )
    governance = get_content_governance_service(tmp_path / "governance")
    monkeypatch.setattr(module, "get_textbook_root", lambda: root)
    monkeypatch.setattr(module, "get_governance_service", lambda: governance)
    monkeypatch.setattr(module, "_is_admin", lambda: True)
    return job, governance


@pytest.mark.asyncio
async def test_read_only_returns_registered_markdown_and_source(controlled_textbook) -> None:
    job, governance = controlled_textbook
    result = await TextbookCandidateTool().execute(action="read", job_id=job.id)

    assert result.success is True
    assert "source-page: 1" in result.content
    assert result.metadata["textbook"]["source_id"]
    assert governance.store.list_revisions() == []


@pytest.mark.asyncio
async def test_submit_only_creates_page_cited_candidate_revision(controlled_textbook) -> None:
    job, governance = controlled_textbook
    payload = [{"kind": "term", "title": "边界框", "content": "用于圈定目标。", "source_pages": [1]}]

    result = await TextbookCandidateTool().execute(
        action="submit",
        job_id=job.id,
        candidates_json=json.dumps(payload, ensure_ascii=False),
        source_ids=[],
    )

    assert result.success is True
    revision = governance.store.list_revisions()[0]
    assert revision.status == "candidate"
    assert revision.proposer_kind == "ai"
    assert revision.proposed_content["source_pages"] == [1]
    assert governance.store.list_published(revision.content_id) == []


@pytest.mark.asyncio
async def test_submit_rejects_candidate_without_valid_source_page(controlled_textbook) -> None:
    job, _governance = controlled_textbook
    payload = [{"kind": "summary", "title": "摘要", "content": "内容", "source_pages": [9]}]

    result = await TextbookCandidateTool().execute(
        action="submit", job_id=job.id, candidates_json=json.dumps(payload), source_ids=[]
    )

    assert result.success is False
    assert "超出教材范围" in result.content


@pytest.mark.asyncio
async def test_mandatory_requirement_requires_controlled_standard(controlled_textbook) -> None:
    job, _governance = controlled_textbook
    payload = [
        {
            "kind": "safety_rule",
            "title": "安全要求",
            "content": "必须执行检查。",
            "source_pages": [1],
            "claim_scope": "mandatory_requirement",
        }
    ]

    result = await TextbookCandidateTool().execute(
        action="submit", job_id=job.id, candidates_json=json.dumps(payload), source_ids=[]
    )

    assert result.success is False
    assert "国家或行业标准" in result.content


@pytest.mark.asyncio
async def test_conflict_is_recorded_without_publishing(controlled_textbook) -> None:
    job, governance = controlled_textbook
    standard = governance.create_source(
        SourceRecordCreate(
            title="数据标注规程",
            source_type="national_standard",
            standard_number="GB/T 42755-2023",
            claim_scope="mandatory_requirement",
        ),
        actor_id="admin",
    )
    payload = [
        {
            "kind": "conflict",
            "title": "阈值表述冲突",
            "content": "教材阈值与国家标准表述不一致。",
            "source_pages": [1],
        }
    ]

    result = await TextbookCandidateTool().execute(
        action="submit",
        job_id=job.id,
        candidates_json=json.dumps(payload, ensure_ascii=False),
        source_ids=[standard.id],
    )

    assert result.success is True
    assert result.metadata["candidate_revision_ids"] == []
    assert len(result.metadata["conflict_ids"]) == 1
    assert governance.store.list_revisions() == []
