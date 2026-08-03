"""Standards catalog — annotation standards from the annotation-guide skill."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter

router = APIRouter()

# annotation-guide skill references (source of truth for annotation standards)
_STANDARDS_DIR = (
    Path(__file__).resolve().parents[2] / "skills" / "builtin" / "annotation-guide" / "references"
)


def _extract_sections(text: str) -> list[str]:
    """Extract ## / ### heading texts (section titles)."""
    return [
        m.group(1).strip()
        for m in re.finditer(r"^#{2,3}\s+(.+)$", text, re.MULTILINE)
        if m.group(1).strip()
    ]


def _derive_title(md: Path, text: str) -> str:
    """First # heading, else readable filename."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return md.stem.replace("-", " ").title()


@router.get("/standards")
async def standards() -> dict[str, Any]:
    """标注规范文档目录（来自 annotation-guide skill references）。"""
    docs = []
    if _STANDARDS_DIR.exists():
        for md in sorted(_STANDARDS_DIR.glob("*.md")):
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            docs.append({
                "id": md.stem,
                "title": _derive_title(md, text),
                "sections": _extract_sections(text),
                "content": text,
            })
    return {"standards": docs}
