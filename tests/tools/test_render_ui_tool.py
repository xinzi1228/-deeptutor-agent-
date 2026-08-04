"""render_ui tool — validate structured component JSON → metadata.chart."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_quiz_card_valid():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    component = {
        "type": "quiz_card",
        "data": {
            "question": "两个框完全不重叠时 IOU 是多少？",
            "options": ["0", "0.5", "1"],
            "answer_index": 0,
            "explanation": "无交集 → IOU=0",
        },
    }
    result = await RenderUiTool().execute(component=json.dumps(component, ensure_ascii=False))
    assert result.success
    assert result.metadata["chart"]["type"] == "quiz_card"
    assert result.metadata["chart"]["data"]["answer_index"] == 0


@pytest.mark.asyncio
async def test_missing_fields_fails():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    result = await RenderUiTool().execute(component=json.dumps({"type": "quiz_card", "data": {"question": "x"}}))
    assert not result.success


@pytest.mark.asyncio
async def test_unknown_type_fails():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    result = await RenderUiTool().execute(component=json.dumps({"type": "unknown_card", "data": {}}))
    assert not result.success
