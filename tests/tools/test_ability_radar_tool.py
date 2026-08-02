"""AbilityRadarTool — learner five-dimension radar from learning records."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ability_radar_emits_radar_chart(monkeypatch) -> None:
    from deeptutor.tools.ability_radar_tool import AbilityRadarTool

    fake_radar = {
        "dimensions": [
            {"name": "框精度", "english": "box_precision", "score": 80.0, "max": 100},
            {"name": "标签准确", "english": "label_accuracy", "score": 70.0, "max": 100},
            {"name": "完整性", "english": "recall", "score": 60.0, "max": 100},
            {"name": "一致性", "english": "consistency", "score": 75.0, "max": 100},
            {"name": "知识掌握", "english": "knowledge", "score": 50.0, "max": 100},
        ]
    }
    monkeypatch.setattr("deeptutor.services.learning_records.LearningStats", lambda: type("S", (), {"radar": lambda self: fake_radar})())

    tool = AbilityRadarTool()
    result = await tool.execute()
    assert result.success
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "radar"
    assert len(chart["data"]["labels"]) == 5
    assert chart["data"]["values"] == [80.0, 70.0, 60.0, 75.0, 50.0]
    assert "框精度" in result.content


@pytest.mark.asyncio
async def test_ability_radar_empty_records(monkeypatch) -> None:
    from deeptutor.tools.ability_radar_tool import AbilityRadarTool

    fake_radar = {
        "dimensions": [
            {"name": "框精度", "score": 0.0, "max": 100},
            {"name": "标签准确", "score": 0.0, "max": 100},
            {"name": "完整性", "score": 0.0, "max": 100},
            {"name": "一致性", "score": 0.0, "max": 100},
            {"name": "知识掌握", "score": 0.0, "max": 100},
        ]
    }
    monkeypatch.setattr("deeptutor.services.learning_records.LearningStats", lambda: type("S", (), {"radar": lambda self: fake_radar})())

    tool = AbilityRadarTool()
    result = await tool.execute()
    assert result.success
    assert "尚无练习记录" in result.content or "暂无" in result.content
