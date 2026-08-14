from pathlib import Path

import pytest

from deeptutor.api.routers import content_governance as router
from deeptutor.services.content_governance.review import ContentGovernanceService
from deeptutor.services.content_governance.store import ContentGovernanceStore


@pytest.fixture
def governance_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = ContentGovernanceService(ContentGovernanceStore(tmp_path / "governance"))
    monkeypatch.setattr(router, "get_content_governance_service", lambda: service)
    return service


@pytest.mark.asyncio
async def test_source_revision_review_api_requires_human_publish_path(governance_service):
    source = await router.create_source(
        router.SourceRequest(
            title="国家标准",
            source_type="national_standard",
            standard_number="GB/T 42755-2023",
            chapter="6",
            url="https://example.test/standard",
        )
    )
    revision = await router.create_revision(
        router.RevisionRequest(
            content_id="kb-bbox",
            content_type="knowledge_article",
            change_summary="修正引用",
            proposed_content={"body": "新内容"},
            source_ids=[source["id"]],
            proposer_kind="ai",
        )
    )

    response = await router.review_revision(
        revision["id"],
        router.ReviewRequest(decision="approve", comment="人工复核通过"),
    )

    assert response["revision"]["status"] == "published"
    assert response["published"]["version"] == 1
    assert response["decision"]["reviewer_kind"] == "human"


@pytest.mark.asyncio
async def test_list_endpoints_return_traceable_objects(governance_service):
    await router.create_source(
        router.SourceRequest(
            title="教材",
            source_type="textbook",
            isbn="978-7-0000-0000-0",
            publisher="示例出版社",
            file_hash="sha256:book",
        )
    )

    sources = await router.list_sources()
    revisions = await router.list_revisions(status=None)

    assert sources["sources"][0]["isbn"] == "978-7-0000-0000-0"
    assert revisions == {"revisions": []}
