from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

if TYPE_CHECKING:
    from deeptutor.services.content_governance.review import ContentGovernanceService
    from deeptutor.services.textbook_ingestion import TextbookJob

_KINDS = (
    "term",
    "knowledge_point",
    "procedure",
    "safety_rule",
    "summary",
    "candidate_question",
    "conflict",
)
_CONTROLLED_SOURCE_TYPES = {"national_standard", "industry_standard", "official_documentation", "textbook"}


class TextbookCandidate(BaseModel):
    kind: Literal[
        "term",
        "knowledge_point",
        "procedure",
        "safety_rule",
        "summary",
        "candidate_question",
        "conflict",
    ]
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=12_000)
    source_pages: list[int] = Field(min_length=1)
    claim_scope: Literal[
        "mandatory_requirement", "recommendation", "example_threshold", "background"
    ] = "background"
    options: list[str] = Field(default_factory=list, max_length=12)
    answer: Any = None
    explanation: str = Field(default="", max_length=4000)


def get_textbook_root() -> Path:
    from deeptutor.multi_user.paths import get_admin_path_service

    return get_admin_path_service().get_workspace_dir() / "textbooks"


def get_governance_service() -> ContentGovernanceService:
    from deeptutor.multi_user.paths import get_admin_path_service
    from deeptutor.services.content_governance.review import get_content_governance_service

    root = get_admin_path_service().workspace_root / "content-governance"
    return get_content_governance_service(root)


def _is_admin() -> bool:
    from deeptutor.multi_user.context import get_current_user

    return get_current_user().role == "admin"


def _load_job(job_id: str) -> tuple[TextbookJob, Path]:
    from deeptutor.services.textbook_ingestion import TextbookJobStore

    root = get_textbook_root()
    job = TextbookJobStore(root).get(job_id)
    if job is None:
        raise FileNotFoundError("找不到教材导入任务")
    if job.status not in {"completed", "needs_review"}:
        raise ValueError("教材尚未完成结构化转换")
    path = Path(job.markdown_path).resolve()
    try:
        path.relative_to((root / "outputs").resolve())
    except ValueError as exc:
        raise PermissionError("教材产物路径不在受控目录") from exc
    if not path.is_file():
        raise FileNotFoundError("教材 Markdown 不存在")
    header = path.read_text(encoding="utf-8")[:4096]
    if "artifact_type: textbook_markdown" not in header or "source_hash:" not in header:
        raise ValueError("该文件不是可追溯教材 Markdown")
    return job, path


def _ensure_textbook_source(service: ContentGovernanceService, job: TextbookJob):
    from deeptutor.services.content_governance.models import SourceRecordCreate

    expected = {job.source_hash, f"sha256:{job.source_hash}"}
    for source in service.store.list_sources():
        if source.source_type == "textbook" and source.file_hash in expected:
            return source
    return service.create_source(
        SourceRecordCreate(
            title=job.original_name,
            source_type="textbook",
            normative=False,
            claim_scope="background",
            file_hash=f"sha256:{job.source_hash}",
            pages=f"1-{max(1, job.total_pages)}",
            notes=f"教材导入任务 {job.id} 的只读原件",
        ),
        actor_id="textbook-analysis-agent",
    )


class TextbookCandidateTool(BaseTool):
    """Read controlled textbook artifacts and write candidates to human review only."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="textbook_candidate",
            description=(
                "Read one structured textbook import or submit page-cited extraction candidates "
                "to the content-governance review queue. Admin-only. This tool cannot publish, "
                "delete originals, or modify the formal question bank."
            ),
            parameters=[
                ToolParameter(name="action", type="string", description="read or submit", enum=["read", "submit"]),
                ToolParameter(name="job_id", type="string", description="Registered textbook ingestion job id"),
                ToolParameter(name="candidates_json", type="string", description="Candidate JSON array for submit", required=False),
                ToolParameter(
                    name="source_ids",
                    type="array",
                    description="Optional controlled standard source ids",
                    required=False,
                    items={"type": "string"},
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not _is_admin():
            return ToolResult(content="只有管理员可以运行教材分析候选工具。", success=False)
        action = str(kwargs.get("action") or "").strip().lower()
        job_id = str(kwargs.get("job_id") or "").strip()
        if action not in {"read", "submit"} or not job_id:
            return ToolResult(content="action 必须是 read/submit，且 job_id 必填。", success=False)
        try:
            job, markdown_path = _load_job(job_id)
            service = get_governance_service()
            textbook_source = _ensure_textbook_source(service, job)
            controlled = {
                row.id: row
                for row in service.store.list_sources()
                if row.source_type in _CONTROLLED_SOURCE_TYPES
            }
            if action == "read":
                markdown = markdown_path.read_text(encoding="utf-8")
                if len(markdown) > 120_000:
                    markdown = markdown[:120_000] + "\n\n[内容过长，已截断；请按章节分批处理]"
                return ToolResult(
                    content=markdown,
                    metadata={
                        "textbook": {
                            "job_id": job.id,
                            "source_id": textbook_source.id,
                            "source_hash": job.source_hash,
                            "total_pages": job.total_pages,
                            "review_pages": job.review_pages,
                        },
                        "controlled_sources": [
                            {
                                "id": row.id,
                                "title": row.title,
                                "source_type": row.source_type,
                                "standard_number": row.standard_number,
                                "chapter": row.chapter,
                                "pages": row.pages,
                            }
                            for row in controlled.values()
                        ],
                    },
                )
            return self._submit(
                job,
                textbook_source.id,
                controlled,
                str(kwargs.get("candidates_json") or ""),
                kwargs.get("source_ids") or [],
                service,
            )
        except (FileNotFoundError, PermissionError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            return ToolResult(content=f"教材候选处理失败：{exc}", success=False)

    def _submit(
        self,
        job: TextbookJob,
        textbook_source_id: str,
        controlled: dict[str, Any],
        candidates_json: str,
        raw_source_ids: Any,
        service: ContentGovernanceService,
    ) -> ToolResult:
        from deeptutor.services.content_governance.models import (
            ContentRevisionCreate,
            StandardConflictCreate,
        )

        payload = json.loads(candidates_json)
        if not isinstance(payload, list) or not payload:
            raise ValueError("candidates_json 必须是非空 JSON 数组")
        if len(payload) > 100:
            raise ValueError("单次最多提交 100 条候选")
        candidates = [TextbookCandidate.model_validate(row) for row in payload]
        if not isinstance(raw_source_ids, list):
            raise ValueError("source_ids 必须是来源 ID 数组")
        extra_source_ids = list(dict.fromkeys(str(value) for value in raw_source_ids if str(value)))
        unknown = [source_id for source_id in extra_source_ids if source_id not in controlled]
        if unknown:
            raise ValueError(f"包含未受控来源：{', '.join(unknown)}")
        revisions: list[str] = []
        conflicts: list[str] = []
        for candidate in candidates:
            pages = sorted(set(candidate.source_pages))
            if any(page < 1 or (job.total_pages and page > job.total_pages) for page in pages):
                raise ValueError(f"{candidate.title} 的源页超出教材范围")
            sources = [textbook_source_id, *extra_source_ids]
            if candidate.claim_scope == "mandatory_requirement":
                standards = [controlled[source_id] for source_id in extra_source_ids if controlled[source_id].source_type in {"national_standard", "industry_standard"}]
                if not standards:
                    raise ValueError(f"{candidate.title} 标记为强制要求，但没有引用国家或行业标准")
            if candidate.kind == "conflict":
                if len(sources) < 2:
                    raise ValueError("冲突报告必须同时引用教材和至少一个受控来源")
                conflict = service.report_conflict(
                    StandardConflictCreate(claim=candidate.content, source_ids=sources),
                    actor_id="textbook-analysis-agent",
                )
                conflicts.append(conflict.id)
                continue
            digest = sha256(
                f"{job.id}|{candidate.kind}|{candidate.title}|{pages}".encode("utf-8")
            ).hexdigest()[:16]
            revision = service.submit_revision(
                ContentRevisionCreate(
                    content_id=f"textbook:{job.id}:{candidate.kind}:{digest}",
                    content_type="question" if candidate.kind == "candidate_question" else "knowledge_article",
                    change_summary=f"教材分析候选：{candidate.kind} · {candidate.title}",
                    proposed_content={
                        **candidate.model_dump(mode="json"),
                        "source_pages": pages,
                        "textbook_job_id": job.id,
                        "source_hash": job.source_hash,
                    },
                    source_ids=sources,
                    proposer_kind="ai",
                ),
                actor_id="textbook-analysis-agent",
            )
            revisions.append(revision.id)
        return ToolResult(
            content=f"已提交 {len(revisions)} 条待审核候选、{len(conflicts)} 条来源冲突；尚未发布。",
            metadata={"candidate_revision_ids": revisions, "conflict_ids": conflicts, "status": "candidate"},
        )


__all__ = ["TextbookCandidate", "TextbookCandidateTool"]
