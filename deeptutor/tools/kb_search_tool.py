"""KbSearchTool — precise keyword search over the annotation knowledge base.

Scans ``data/user/workspace/annotation_kb/`` (60 docs, 6 categories) for query
tokens and returns the top-k matches with title / snippet / source. No LLM
involved — deterministic and unit-testable. No hits => explicit "not in KB".
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

KB_ROOT = Path(__file__).resolve().parents[2] / "data" / "user" / "workspace" / "annotation_kb"

CATEGORY_DIRS: tuple[str, ...] = (
    "01-基础概念",
    "02-行业标准",
    "03-工具操作",
    "04-质量管控",
    "05-典型错误",
    "06-项目管理",
)


def _tokenize(text: str) -> list[str]:
    """Split into CJK bigrams + ascii words (lightweight keyword tokens)."""
    tokens: list[str] = []
    cjk = re.findall(r"[\u4e00-\u9fff]+", text.lower())
    for chunk in cjk:
        if len(chunk) == 1:
            tokens.append(chunk)
        else:
            tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
            tokens.append(chunk)  # whole chunk as a token too
    tokens.extend(re.findall(r"[a-z0-9_]+", text.lower()))
    return [t for t in tokens if len(t) >= 2]


def _snippet(text: str, tokens: list[str], width: int = 40) -> str:
    positions = [m.start() for t in tokens for m in re.finditer(re.escape(t), text)]
    if not positions:
        return text[: width * 2].replace("\n", " ")
    pos = positions[0]
    start = max(0, pos - width)
    end = min(len(text), pos + width * 2)
    snippet = text[start:end].replace("\n", " ")
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def search_kb(query: str, *, category: str | None = None, top_k: int = 3) -> list[dict[str, Any]]:
    """Return top-k matches as {title, category, snippet, source}."""
    if not KB_ROOT.exists():
        return []
    tokens = _tokenize(query or "")
    if not tokens:
        return []
    target_dirs = [category] if category and category in CATEGORY_DIRS else list(CATEGORY_DIRS)
    scored: list[tuple[int, dict[str, Any]]] = []
    for cat_dir in target_dirs:
        cat_path = KB_ROOT / cat_dir
        if not cat_path.is_dir():
            continue
        for md in cat_path.glob("*.md"):
            text = md.read_text(encoding="utf-8", errors="ignore")
            score = sum(text.count(t) for t in tokens)
            if score <= 0:
                continue
            title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else md.stem
            scored.append((score, {
                "title": title,
                "category": cat_dir,
                "snippet": _snippet(text, tokens),
                "source": str(md.relative_to(KB_ROOT)).replace("\\", "/"),
            }))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[: max(1, top_k)]]


class KbSearchTool(BaseTool):
    """Search the annotation knowledge base for teaching evidence."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="kb_search",
            description=(
                "Search the annotation knowledge base (60 docs across 6 categories: "
                "基础知识/行业标准/工具操作/质量管控/常见错误/项目管理). Use when teaching a "
                "knowledge point or citing a standard. Returns top matching docs with "
                "snippet and source. Category can be limited for precision."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search keywords (e.g. 遮挡, IOU, GB/T 41867).",
                    required=True,
                ),
                ToolParameter(
                    name="category",
                    type="string",
                    description="Optional category dir name to limit the search.",
                    required=False,
                    enum=list(CATEGORY_DIRS),
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResult(content="Error: query is required.", success=False)
        category = str(kwargs.get("category") or "").strip() or None
        hits = search_kb(query, category=category, top_k=3)
        if not hits:
            return ToolResult(
                content="知识库未收录此内容。可改为通用教学建议并注明非标准条款。",
                metadata={"kb_search": {"hits": [], "query": query}},
            )
        lines = [f"知识库命中（{len(hits)} 条）: "]
        for h in hits:
            lines.append(f"- 【{h['title']}】({h['category']})\n  {h['snippet']}\n  来源: {h['source']}")
        return ToolResult(
            content="\n".join(lines),
            metadata={"kb_search": {"hits": hits, "query": query}},
        )


__all__ = ["KbSearchTool", "search_kb", "CATEGORY_DIRS", "KB_ROOT"]
