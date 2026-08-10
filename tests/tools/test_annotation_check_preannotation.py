"""AI 预标注双评 (double-scoring): annotation_check evaluates pre_annotation against the same ground_truth."""

from __future__ import annotations

import json

import pytest

from deeptutor.tools.annotation_check import AnnotationCheckTool, _bbox_dict


@pytest.fixture
def _no_png(monkeypatch):
    async def _fake_png(**kwargs):
        return None

    monkeypatch.setattr("deeptutor.tools.annotation_check.render_scorecard_png", _fake_png)
    monkeypatch.setattr(
        "deeptutor.services.teaching_flow.TeachingFlowEngine",
        lambda: type("_Fake", (), {"on_evaluated": lambda self, **k: {}})(),
    )


def test_bbox_dict_reused_for_pre_annotation():
    """pre_annotation_metrics must come from the same _bbox_dict scorer as student metrics."""
    pre = [{"x": 195, "y": 128, "w": 370, "h": 290, "label": "car"}]
    gt = [{"x": 207, "y": 140, "w": 353, "h": 273, "label": "car"}]
    assert _bbox_dict(pre, gt) == {
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "matched_count": 1,
        "extra_count": 0,
        "missed_count": 0,
    }


@pytest.mark.asyncio
async def test_double_scoring_review_mode(_no_png):
    """review mode: AI pre-annotation near-correct; student F1 == AI F1 -> improvement ~0."""
    gt = [{"x": 207, "y": 140, "w": 353, "h": 273, "label": "car"}]
    pre = [{"x": 195, "y": 128, "w": 370, "h": 290, "label": "car"}]  # review: near-correct
    student = gt[:]  # student confirmed the box as-is

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions=json.dumps(student),
        ground_truth=json.dumps(gt),
        pre_annotation=json.dumps(pre),
    )
    assert result.success
    meta = result.metadata
    assert meta["pre_annotation_metrics"]["f1"] == 1.0
    assert meta["pre_annotation_metrics"]["matched_count"] == 1
    assert meta["improvement"] == 0.0
    assert "AI 预标注对比" in result.content
    assert "改进" in result.content


@pytest.mark.asyncio
async def test_double_scoring_find_error_missing_target(_no_png):
    """find_error mode: AI missed a small target -> AI F1 clearly below student's corrected F1."""
    gt = [
        {"x": 187, "y": 351, "w": 144, "h": 140, "label": "car"},
        {"x": 431, "y": 308, "w": 89, "h": 109, "label": "car"},
        {"x": 664, "y": 409, "w": 138, "h": 137, "label": "car"},
        {"x": 564, "y": 141, "w": 71, "h": 35, "label": "car"},  # small far car
    ]
    pre = gt[:3]  # AI missed the small far car
    student = gt[:]  # student corrected: found all 4

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions=json.dumps(student),
        ground_truth=json.dumps(gt),
        pre_annotation=json.dumps(pre),
    )
    assert result.success
    meta = result.metadata
    pre_metrics = meta["pre_annotation_metrics"]
    assert pre_metrics["matched_count"] == 3
    assert pre_metrics["missed_count"] == 1
    assert pre_metrics["f1"] == pytest.approx(0.8571, abs=1e-4)  # recall=3/4, precision=1
    assert meta["improvement"] == pytest.approx(0.1429, abs=1e-4)
    assert meta["improvement"] > 0


@pytest.mark.asyncio
async def test_double_scoring_find_error_offset_box(_no_png):
    """find_error mode: AI box heavily offset -> that object missed + one extra box."""
    gt = [
        {"x": 0, "y": 157, "w": 88, "h": 116, "label": "horse"},
        {"x": 433, "y": 74, "w": 181, "h": 358, "label": "horse"},
        {"x": 26, "y": 121, "w": 292, "h": 295, "label": "horse"},
        {"x": 313, "y": 130, "w": 116, "h": 291, "label": "horse"},
    ]
    pre = [
        {"x": 0, "y": 157, "w": 88, "h": 116, "label": "horse"},
        {"x": 520, "y": 220, "w": 160, "h": 300, "label": "horse"},  # offset, IoU<0.5
        {"x": 26, "y": 121, "w": 292, "h": 295, "label": "horse"},
        {"x": 313, "y": 130, "w": 116, "h": 291, "label": "horse"},
    ]
    student = gt[:]  # student corrected all boxes

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions=json.dumps(student),
        ground_truth=json.dumps(gt),
        pre_annotation=json.dumps(pre),
    )
    assert result.success
    meta = result.metadata
    pre_metrics = meta["pre_annotation_metrics"]
    assert pre_metrics["matched_count"] == 3
    assert pre_metrics["extra_count"] == 1  # offset box
    assert pre_metrics["missed_count"] == 1
    assert pre_metrics["f1"] == pytest.approx(0.75, abs=1e-4)
    assert meta["improvement"] == pytest.approx(0.25, abs=1e-4)


@pytest.mark.asyncio
async def test_no_pre_annotation_zero_regression(_no_png):
    """No pre_annotation -> metadata must NOT contain pre_annotation keys (old behavior unchanged)."""
    gt = [{"x": 207, "y": 140, "w": 353, "h": 273, "label": "car"}]

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions=json.dumps(gt),
        ground_truth=json.dumps(gt),
    )
    assert result.success
    assert "pre_annotation_metrics" not in result.metadata
    assert "improvement" not in result.metadata
    assert "AI 预标注对比" not in result.content
    assert result.metadata["readiness"] == "advance"


@pytest.mark.asyncio
async def test_pre_annotation_ignored_for_non_bbox():
    """Other task_types ignore pre_annotation (keep original behavior)."""
    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="classification",
        predictions='[{"id":1,"label":"positive"}]',
        ground_truth='[{"id":1,"label":"positive"},{"id":2,"label":"negative"}]',
        pre_annotation='[{"x":0,"y":0,"w":10,"h":10,"label":"cat"}]',
    )
    assert result.success
    meta = result.metadata
    assert meta is None or "pre_annotation_metrics" not in meta
    assert "AI 预标注对比" not in result.content


@pytest.mark.asyncio
async def test_malformed_pre_annotation_ignored(_no_png):
    """Malformed pre_annotation JSON must not break normal grading."""
    gt = [{"x": 207, "y": 140, "w": 353, "h": 273, "label": "car"}]

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions=json.dumps(gt),
        ground_truth=json.dumps(gt),
        pre_annotation="not-json",
    )
    assert result.success
    assert "pre_annotation_metrics" not in result.metadata
    assert result.metadata["readiness"] == "advance"
