"""annotation_check emits scorecard chart metadata + PNG."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_bbox_check_emits_chart_metadata(monkeypatch, tmp_path) -> None:
    from deeptutor.tools.annotation_check import AnnotationCheckTool

    async def _fake_png(**kwargs):
        p = tmp_path / "scorecard.png"
        p.write_bytes(b"\x89PNG fake")
        return p

    monkeypatch.setattr("deeptutor.tools.annotation_check.render_scorecard_png", _fake_png)

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions='[{"x":207,"y":140,"w":353,"h":273,"label":"car"}]',
        ground_truth='[{"x":207,"y":140,"w":353,"h":273,"label":"car"}]',
    )
    assert result.success
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "scorecard"
    assert chart["data"]["f1"] > 0.9


@pytest.mark.asyncio
async def test_bbox_check_content_has_scorecard_image(monkeypatch, tmp_path) -> None:
    from deeptutor.tools.annotation_check import AnnotationCheckTool

    async def _fake_png(**kwargs):
        p = tmp_path / "scorecard.png"
        p.write_bytes(b"\x89PNG fake")
        return p

    monkeypatch.setattr("deeptutor.tools.annotation_check.render_scorecard_png", _fake_png)
    # make collect_public_artifacts return a fake artifact
    class FakeArtifact:
        url = "/api/outputs/fake/scorecard.png"

    monkeypatch.setattr(
        "deeptutor.tools.annotation_check.collect_public_artifacts",
        lambda *a, **k: [FakeArtifact()],
    )

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions='[{"x":207,"y":140,"w":353,"h":273,"label":"car"}]',
        ground_truth='[{"x":207,"y":140,"w":353,"h":273,"label":"car"}]',
    )
    assert "![成绩单]" in result.content
