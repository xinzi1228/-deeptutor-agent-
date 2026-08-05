import pytest

from deeptutor.tools.kb_search_tool import CATEGORY_DIRS, KB_ROOT, KbSearchTool, search_kb


def test_kb_root_exists_and_has_docs():
    assert KB_ROOT.exists()
    md_files = list(KB_ROOT.rglob("*.md"))
    assert len(md_files) >= 40  # 60 篇（含未来扩展，至少 40）


def test_categories_cover_six_domains():
    assert any("基础" in c for c in CATEGORY_DIRS)
    assert any("标准" in c for c in CATEGORY_DIRS)
    assert len(CATEGORY_DIRS) >= 5


def test_search_keyword_hits():
    hits = search_kb("遮挡", top_k=5)
    assert isinstance(hits, list) and hits
    first = hits[0]
    assert "title" in first and "snippet" in first and "source" in first and "category" in first
    assert "遮挡" in first["snippet"] or "遮挡" in first["title"]


def test_search_category_limited():
    std = next(c for c in CATEGORY_DIRS if "标准" in c)
    hits = search_kb("标注", category=std, top_k=5)
    assert hits, "query 标注 should hit docs in the 标准 category"
    assert all(h["category"] == std for h in hits)


def test_search_no_hit_returns_empty():
    hits = search_kb("zzzqqqxxxyyy_not_exist", top_k=5)
    assert hits == []


def test_top_k_respected():
    hits = search_kb("标注", top_k=3)
    assert len(hits) <= 3


@pytest.mark.asyncio
async def test_execute_returns_hits():
    tool = KbSearchTool()
    result = await tool.execute(query="遮挡")
    assert result.success is True
    assert "遮挡" in result.content


@pytest.mark.asyncio
async def test_execute_no_hit_message():
    tool = KbSearchTool()
    result = await tool.execute(query="zzzqqqxxxyyy_not_exist")
    assert result.success is True
    assert "知识库未收录此内容" in result.content


@pytest.mark.asyncio
async def test_execute_empty_query_fails():
    tool = KbSearchTool()
    result = await tool.execute(query="   ")
    assert result.success is False
