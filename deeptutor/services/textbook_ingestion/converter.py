from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from deeptutor.services.file_io import atomic_write_json, atomic_write_text
from deeptutor.services.parsing import get_parse_service
from deeptutor.services.parsing.types import ParsedDocument

from .models import TextbookArtifact
from .quality import block_page, inspect_blocks, source_page_count


def _block_markdown(block: dict[str, Any], resources_dir: Path) -> tuple[str, str]:
    kind = str(block.get("type") or block.get("block_type") or "text").lower()
    if kind in {"image", "figure"}:
        raw = str(block.get("img_path") or block.get("image_path") or "")
        source = Path(raw) if raw else None
        if source and source.is_file():
            target = resources_dir / source.name
            if not target.exists():
                shutil.copy2(source, target)
            caption = str(block.get("caption") or block.get("text") or source.stem)
            return f"![{caption}](resources/{target.name})", str(target)
        return "", ""
    if kind in {"table", "table_body"}:
        return str(block.get("table_body") or block.get("text") or block.get("content") or ""), ""
    if kind in {"equation", "formula", "interline_equation"}:
        formula = str(block.get("latex") or block.get("text") or block.get("content") or "")
        return (f"$$\n{formula}\n$$" if formula else ""), ""
    return str(block.get("text") or block.get("content") or ""), ""


class TextbookConverter:
    """Wrap the shared parser IR in a traceable, rebuildable textbook artifact."""

    def __init__(self, output_root: Path, *, parse_service=None) -> None:
        self.output_root = Path(output_root)
        self.parse_service = parse_service or get_parse_service()

    def convert(
        self,
        source_path: Path,
        *,
        job_id: str,
        engine: str | None = None,
        on_output=None,
    ) -> TextbookArtifact:
        source_path = Path(source_path)
        parsed: ParsedDocument = self.parse_service.parse(source_path, engine=engine, on_output=on_output)
        output_dir = self.output_root / job_id
        resources_dir = output_dir / "resources"
        output_dir.mkdir(parents=True, exist_ok=True)
        resources_dir.mkdir(parents=True, exist_ok=True)

        blocks = parsed.blocks or []
        total_pages = source_page_count(source_path, blocks)
        issues = inspect_blocks(blocks, source_path=source_path, total_pages=total_pages)
        resources: list[str] = []
        body_parts: list[str] = []
        if blocks:
            grouped: dict[int, list[dict[str, Any]]] = {}
            for block in blocks:
                grouped.setdefault(block_page(block) or 0, []).append(block)
            for page_index in sorted(grouped):
                body_parts.append(f"<!-- source-page: {page_index + 1} -->")
                for block in grouped[page_index]:
                    text, resource = _block_markdown(block, resources_dir)
                    if text.strip():
                        body_parts.append(text.strip())
                    if resource:
                        resources.append(resource)
        else:
            pieces = [part.strip() for part in parsed.markdown.split("\f") if part.strip()]
            if len(pieces) == total_pages:
                for page_index, piece in enumerate(pieces):
                    body_parts.extend((f"<!-- source-page: {page_index + 1} -->", piece))
            else:
                body_parts.extend((f"<!-- source-pages: 1-{total_pages}; exact: false -->", parsed.markdown.strip()))

        failed_pages = {issue.page for issue in issues if issue.severity == "error" and issue.page}
        review_pages = {issue.page for issue in issues if issue.severity == "review" and issue.page}
        if any(issue.page is None and issue.severity == "review" for issue in issues):
            review_pages.update(range(1, total_pages + 1))
        review_pages.difference_update(failed_pages)
        header = "\n".join(
            (
                "---",
                "artifact_type: textbook_markdown",
                f"source_name: {json.dumps(source_path.name, ensure_ascii=False)}",
                f"source_hash: {parsed.source_hash}",
                f"parser_engine: {parsed.engine}",
                f"parser_signature: {parsed.parser_signature}",
                f"source_page_count: {total_pages}",
                "rebuildable: true",
                "---",
            )
        )
        markdown_path = output_dir / "document.md"
        atomic_write_text(markdown_path, header + "\n\n" + "\n\n".join(body_parts).strip() + "\n")
        artifact = TextbookArtifact(
            job_id=job_id,
            markdown_path=str(markdown_path),
            manifest_path=str(output_dir / "artifact.json"),
            source_hash=parsed.source_hash,
            parser_signature=parsed.parser_signature,
            parser_engine=parsed.engine,
            total_pages=total_pages,
            successful_page_count=max(0, total_pages - len(review_pages) - len(failed_pages)),
            review_page_count=len(review_pages),
            failed_page_count=len(failed_pages),
            review_issues=issues,
            resources=resources,
        )
        atomic_write_json(Path(artifact.manifest_path), artifact.model_dump(mode="json"))
        atomic_write_json(output_dir / "review.json", {"issues": [row.model_dump(mode="json") for row in issues]})
        return artifact

