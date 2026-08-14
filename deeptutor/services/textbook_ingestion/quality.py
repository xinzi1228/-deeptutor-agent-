from __future__ import annotations

from pathlib import Path
import re
from typing import Any
import zipfile

from .models import ReviewIssue


def source_page_count(source_path: Path, blocks: list[dict[str, Any]] | None) -> int:
    indexed = [block_page(block) for block in blocks or []]
    indexed = [page for page in indexed if page is not None]
    if indexed:
        return max(indexed) + 1
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz

            with fitz.open(source_path) as document:
                return max(1, int(document.page_count))
        except Exception:
            return 1
    if suffix == ".pptx":
        try:
            with zipfile.ZipFile(source_path) as archive:
                slides = [name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
            return max(1, len(slides))
        except (OSError, zipfile.BadZipFile):
            return 1
    return 1


def block_page(block: dict[str, Any]) -> int | None:
    for key in ("page_idx", "page_index", "page_no", "page_number"):
        raw = block.get(key)
        if isinstance(raw, int):
            return max(0, raw - 1 if key in {"page_no", "page_number"} and raw > 0 else raw)
    return None


def inspect_blocks(
    blocks: list[dict[str, Any]] | None,
    *,
    source_path: Path,
    total_pages: int,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    if not blocks:
        if total_pages > 1:
            issues.append(
                ReviewIssue(
                    category="page_mapping",
                    message="当前解析结果没有逐页结构，需人工核对页码边界。",
                )
            )
        return issues
    for block in blocks:
        kind = str(block.get("type") or block.get("block_type") or "text").lower()
        page_index = block_page(block)
        page = page_index + 1 if page_index is not None else None
        if kind in {"image", "figure"}:
            resource = str(block.get("img_path") or block.get("image_path") or "")
            if not resource or not Path(resource).is_file():
                issues.append(
                    ReviewIssue(
                        category="missing_image",
                        message="图片资源没有成功落盘，不能静默进入知识库。",
                        page=page,
                        resource=resource,
                    )
                )
        elif kind in {"table", "table_body"}:
            content = str(block.get("table_body") or block.get("text") or block.get("content") or "").strip()
            if not content:
                issues.append(ReviewIssue(category="empty_table", message="表格结构为空，需人工复核。", page=page))
        elif kind in {"equation", "formula", "interline_equation"}:
            content = str(block.get("latex") or block.get("text") or block.get("content") or "").strip()
            if not content:
                issues.append(ReviewIssue(category="empty_formula", message="公式未被正确识别，需人工复核。", page=page))
        if block.get("error") or str(block.get("status") or "").lower() in {"error", "failed"}:
            issues.append(
                ReviewIssue(
                    category="parser_block_error",
                    message=str(block.get("error") or "解析器报告该内容块失败。"),
                    page=page,
                    severity="error",
                )
            )
    return issues

