"""Chart card contract + scorecard image generation tests."""

from __future__ import annotations

import pytest

from deeptutor.tools.chart_cards import (
    build_scorecard_chart,
    progress_chart,
    radar_chart,
    render_scorecard_png,
)


def test_radar_chart_contract():
    c = radar_chart(
        labels=["框精度", "标签准确", "完整性", "一致性", "知识掌握"], values=[80, 70, 60, 75, 50]
    )
    assert c["type"] == "radar"
    assert c["data"]["labels"] == ["框精度", "标签准确", "完整性", "一致性", "知识掌握"]
    assert c["data"]["values"] == [80, 70, 60, 75, 50]


def test_progress_chart_contract():
    c = progress_chart(completed=2, total=4, modules=[{"name": "标注基础", "done": 2, "total": 2}])
    assert c["type"] == "progress"
    assert c["data"]["completed"] == 2
    assert c["data"]["total"] == 4


def test_scorecard_chart_contract():
    c = build_scorecard_chart(f1=0.85, precision=0.9, recall=0.8, passed=True)
    assert c["type"] == "scorecard"
    assert c["data"]["f1"] == 0.85
    assert c["data"]["passed"] is True


@pytest.mark.asyncio
async def test_render_scorecard_png(tmp_path):
    path = await render_scorecard_png(
        f1=0.85,
        precision=0.9,
        recall=0.8,
        passed=True,
        feedback=["框A 匹配 (IOU=0.82)", "漏标 1 个"],
        out_dir=tmp_path,
    )
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 500
