from pathlib import Path

from pydantic import ValidationError
import pytest

from deeptutor.services.content_governance.models import (
    ContentRevisionCreate,
    ReviewDecisionCreate,
    SourceRecordCreate,
    StandardConflictCreate,
)
from deeptutor.services.content_governance.review import ContentGovernanceService
from deeptutor.services.content_governance.store import ContentGovernanceStore


def _service(tmp_path: Path) -> ContentGovernanceService:
    return ContentGovernanceService(ContentGovernanceStore(tmp_path / "governance"))


def test_project_experience_cannot_claim_mandatory_standard():
    with pytest.raises(ValidationError):
        SourceRecordCreate(
            title="项目抽检经验",
            source_type="project_experience",
            normative=True,
            claim_scope="mandatory_requirement",
            file_hash="sha256:abc",
        )


def test_textbook_source_keeps_bibliographic_trace(tmp_path: Path):
    service = _service(tmp_path)

    source = service.create_source(
        SourceRecordCreate(
            title="数据标注工程",
            source_type="textbook",
            isbn="978-7-0000-0000-0",
            edition="第2版",
            publisher="示例出版社",
            chapter="第6章",
            pages="P120-P126",
            file_hash="sha256:bookhash",
        ),
        actor_id="admin-a",
    )

    assert source.isbn == "978-7-0000-0000-0"
    assert source.chapter == "第6章"
    assert service.store.get_source(source.id) is not None


def test_ai_revision_stays_candidate_until_human_approval(tmp_path: Path):
    service = _service(tmp_path)
    source = service.create_source(
        SourceRecordCreate(
            title="GB/T 42755-2023",
            source_type="national_standard",
            standard_number="GB/T 42755-2023",
            chapter="6.2",
            url="https://example.test/standard",
        ),
        actor_id="admin-a",
    )
    revision = service.submit_revision(
        ContentRevisionCreate(
            content_id="question-task-1",
            content_type="question",
            base_version=1,
            change_summary="修正标准来源",
            proposed_content={"source": source.standard_number},
            source_ids=[source.id],
            proposer_kind="ai",
        ),
        actor_id="content-agent",
    )

    assert revision.status == "candidate"
    assert service.versioning.list_versions("question-task-1") == []

    decision, published = service.review_revision(
        revision.id,
        ReviewDecisionCreate(decision="approve", comment="人工核对来源无误"),
        reviewer_id="teacher-a",
        reviewer_kind="human",
    )

    assert decision.decision == "approve"
    assert published is not None
    assert published.version == 2
    assert published.review_decision_id == decision.id


def test_ai_cannot_approve_revision(tmp_path: Path):
    service = _service(tmp_path)
    source = service.create_source(
        SourceRecordCreate(
            title="官方文档",
            source_type="official_documentation",
            url="https://example.test/docs",
        ),
        actor_id="admin-a",
    )
    revision = service.submit_revision(
        ContentRevisionCreate(
            content_id="article-1",
            content_type="knowledge_article",
            change_summary="候选修订",
            proposed_content={"body": "候选内容"},
            source_ids=[source.id],
            proposer_kind="ai",
        ),
        actor_id="content-agent",
    )

    with pytest.raises(PermissionError):
        service.review_revision(
            revision.id,
            ReviewDecisionCreate(decision="approve"),
            reviewer_id="review-agent",
            reviewer_kind="ai",
        )


def test_question_publication_preserves_original_score_and_records_impact(tmp_path: Path):
    service = _service(tmp_path)
    source = service.create_source(
        SourceRecordCreate(
            title="题库项目经验",
            source_type="project_experience",
            normative=False,
            claim_scope="example_threshold",
            file_hash="sha256:taskbank",
        ),
        actor_id="admin-a",
    )
    revision = service.submit_revision(
        ContentRevisionCreate(
            content_id="task-7",
            content_type="scoring_rule",
            base_version=3,
            change_summary="调整示例阈值",
            proposed_content={"threshold": 0.8, "label": "项目示例阈值"},
            source_ids=[source.id],
            proposer_kind="human",
        ),
        actor_id="teacher-a",
    )

    _decision, published = service.review_revision(
        revision.id,
        ReviewDecisionCreate(decision="approve"),
        reviewer_id="teacher-b",
        reviewer_kind="human",
    )

    impacts = service.store.list_impacts()
    assert published is not None
    assert impacts[0].revision_id == revision.id
    assert impacts[0].original_score_preserved is True
    assert impacts[0].recalculation_policy == "secondary_result_only"


def test_conflicting_sources_require_explicit_human_resolution(tmp_path: Path):
    service = _service(tmp_path)
    first = service.create_source(
        SourceRecordCreate(
            title="标准 A",
            source_type="national_standard",
            standard_number="GB/T 00001-2026",
        ),
        actor_id="admin-a",
    )
    second = service.create_source(
        SourceRecordCreate(
            title="教材 B",
            source_type="textbook",
            isbn="978-7-0000-0000-1",
        ),
        actor_id="admin-a",
    )
    conflict = service.report_conflict(
        StandardConflictCreate(
            claim="同一质量阈值存在冲突",
            source_ids=[first.id, second.id],
        ),
        actor_id="content-agent",
    )

    resolved = service.resolve_conflict(
        conflict.id,
        resolution="以现行国家标准为准，教材内容标记为历史说明",
        reviewer_id="teacher-a",
    )

    assert resolved.status == "resolved"
    assert resolved.resolved_by == "teacher-a"
