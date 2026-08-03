"""standards endpoint — annotation standards catalog from skill references."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_standards_returns_documents():
    from deeptutor.api.routers.standards import standards

    result = await standards()
    assert "standards" in result
    docs = result["standards"]
    assert len(docs) >= 4, "expected the annotation-guide reference docs"
    for d in docs:
        assert d["id"]
        assert d["title"]
        assert "sections" in d
        assert "content" in d


@pytest.mark.asyncio
async def test_standards_bbox_has_expected_section():
    from deeptutor.api.routers.standards import standards

    result = await standards()
    docs = {d["id"]: d for d in result["standards"]}
    assert "bbox-guide" in docs
    assert any("边界框" in s for s in docs["bbox-guide"]["sections"])
