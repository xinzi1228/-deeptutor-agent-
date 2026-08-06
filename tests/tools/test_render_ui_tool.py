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


@pytest.mark.asyncio
async def test_ls_task_card_valid():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    component = {
        "type": "ls_task_card",
        "data": {
            "project_id": 3,
            "task_index": 0,
            "title": "遮挡检测练习",
            "task_type": "bbox",
            "instructions": "在图片中标出被遮挡的目标",
        },
    }
    result = await RenderUiTool().execute(component=json.dumps(component, ensure_ascii=False))
    assert result.success
    assert result.metadata["chart"]["type"] == "ls_task_card"
    assert result.metadata["chart"]["data"]["url"].endswith("/projects/3/labeling?task=0")


@pytest.mark.asyncio
async def test_ls_task_card_missing_project_id():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    component = {
        "type": "ls_task_card",
        "data": {"task_index": 0, "title": "遮挡检测练习"},
    }
    result = await RenderUiTool().execute(component=json.dumps(component, ensure_ascii=False))
    assert not result.success


@pytest.mark.asyncio
async def test_ls_task_card_negative_task_index():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    component = {
        "type": "ls_task_card",
        "data": {"project_id": 3, "task_index": -1, "title": "遮挡检测练习"},
    }
    result = await RenderUiTool().execute(component=json.dumps(component, ensure_ascii=False))
    assert not result.success


@pytest.mark.asyncio
async def test_ls_task_card_empty_title():
    from deeptutor.tools.render_ui_tool import RenderUiTool

    component = {
        "type": "ls_task_card",
        "data": {"project_id": 3, "task_index": 0, "title": "   "},
    }
    result = await RenderUiTool().execute(component=json.dumps(component, ensure_ascii=False))
    assert not result.success
