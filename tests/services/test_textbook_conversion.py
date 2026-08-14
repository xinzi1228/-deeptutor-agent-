from __future__ import annotations

from pathlib import Path

from deeptutor.services.parsing.types import ParsedDocument
from deeptutor.services.textbook_ingestion import TextbookConverter, TextbookJobStore


class _FakeParseService:
    def parse(self, source_path: Path, *, engine: str | None = None, on_output=None):
        if on_output:
            on_output("解析完成")
        return ParsedDocument(
            markdown="# 第一章\n\n正文",
            blocks=[
                {"type": "text", "text": "# 第一章\n\n正文", "page_idx": 0},
                {"type": "table", "table_body": "| 项目 | 要求 |\n|---|---|\n| 框 | 贴边 |", "page_idx": 1},
                {"type": "image", "img_path": "missing.png", "page_idx": 1},
            ],
            source_hash="source-hash",
            parser_signature="parser-v1",
            engine=engine or "mineru",
        )


def test_structured_conversion_keeps_source_and_page_provenance(tmp_path: Path) -> None:
    source = tmp_path / "教材.pdf"
    source.write_bytes(b"fake-pdf")
    converter = TextbookConverter(tmp_path / "outputs", parse_service=_FakeParseService())

    artifact = converter.convert(source, job_id="job-1", engine="mineru")

    markdown = Path(artifact.markdown_path).read_text(encoding="utf-8")
    assert "source_hash: source-hash" in markdown
    assert "parser_signature: parser-v1" in markdown
    assert "<!-- source-page: 1 -->" in markdown
    assert "<!-- source-page: 2 -->" in markdown
    assert artifact.review_page_count == 1
    assert any(issue.category == "missing_image" for issue in artifact.review_issues)


def test_job_store_persists_resume_state_and_reuses_completed_artifact(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    source.write_bytes(b"book")
    store = TextbookJobStore(tmp_path / "textbooks")
    job = store.create(source_path=source, original_name="book.pdf", source_hash="abc", engine="mineru")
    store.update(job.id, status="running", resume_cursor=2, successful_pages=2)

    restored = TextbookJobStore(tmp_path / "textbooks").get(job.id)

    assert restored is not None
    assert restored.status == "running"
    assert restored.resume_cursor == 2
    assert restored.successful_pages == 2
