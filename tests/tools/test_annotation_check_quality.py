"""Pixel-quality heuristic checks for annotation_check (edge/overlap/tightness)."""

from __future__ import annotations

import json

import pytest

from deeptutor.tools.annotation_check import (
    check_edge_proximity,
    check_overlap,
    check_tightness,
    quality_checks,
)


def test_edge_proximity_triggers():
    boxes = [{"x": 0, "y": 0, "w": 100, "h": 100, "label": "car"}]
    checks = check_edge_proximity(boxes, image_size=(1000, 1000), threshold=5)
    assert len(checks) == 1
    assert checks[0]["rule"] == "edge"


def test_edge_proximity_not_triggered():
    boxes = [{"x": 50, "y": 50, "w": 100, "h": 100, "label": "car"}]
    assert check_edge_proximity(boxes, image_size=(1000, 1000), threshold=5) == []


def test_overlap_triggers():
    boxes = [
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "car"},
        {"x": 20, "y": 20, "w": 100, "h": 100, "label": "car"},
    ]
    checks = check_overlap(boxes, iou_threshold=0.5)
    assert len(checks) == 1
    assert checks[0]["rule"] == "overlap"


def test_overlap_nested_not_flagged():
    boxes = [
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "car"},
        {"x": 15, "y": 15, "w": 90, "h": 90, "label": "car"},
    ]
    assert check_overlap(boxes, iou_threshold=0.5) == []


def test_overlap_identical_boxes_flagged():
    boxes = [
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "car"},
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "car"},
    ]
    checks = check_overlap(boxes, iou_threshold=0.5)
    assert len(checks) == 1
    assert checks[0]["rule"] == "overlap"


def test_overlap_partial_high_iou_flagged():
    boxes = [
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "car"},
        {"x": 40, "y": 10, "w": 100, "h": 100, "label": "car"},
    ]
    checks = check_overlap(boxes, iou_threshold=0.5)
    assert len(checks) == 1
    assert checks[0]["rule"] == "overlap"


def test_tightness_triggers_on_wide_box():
    boxes = [{"x": 10, "y": 10, "w": 800, "h": 50, "label": "car"}]
    checks = check_tightness(boxes, ratio_threshold=5.0)
    assert len(checks) == 1
    assert checks[0]["rule"] == "tightness"


def test_tightness_not_triggered_normal():
    boxes = [{"x": 10, "y": 10, "w": 100, "h": 80, "label": "car"}]
    assert check_tightness(boxes, ratio_threshold=5.0) == []


def test_quality_checks_aggregates():
    boxes = [
        {"x": 0, "y": 0, "w": 800, "h": 40, "label": "car"},
    ]
    checks = quality_checks(boxes, image_size=(1000, 1000))
    rules = {c["rule"] for c in checks}
    assert "edge" in rules
    assert "tightness" in rules


def test_judgment_report():
    from deeptutor.tools.annotation_check import _judgment_report

    predictions = [{"id": 1, "label": "correct"}, {"id": 2, "label": "wrong"}]
    ground_truth = [{"id": 1, "answer": True}, {"id": 2, "answer": False}]
    content = _judgment_report(predictions, ground_truth)
    assert "Accuracy" in content or "准确率" in content
    assert "100%" in content


def test_standard_report_requires_valid_box():
    from deeptutor.tools.annotation_check import _standard_report

    # missing label field -> invalid
    predictions = [{"x": 0, "y": 0, "w": 100, "h": 100}]
    ground_truth = [{"required_fields": ["x", "y", "w", "h", "label"]}]
    content = _standard_report(predictions, ground_truth)
    assert "合规率" in content or "invalid" in content.lower() or "合规" in content
    assert "0%" in content or "0.0" in content


def test_error_case_report():
    from deeptutor.tools.annotation_check import _error_case_report

    # ground truth marks box 1 as erroneous (edge rule); student should flag it
    predictions = [{"id": 1, "flagged": True}, {"id": 2, "flagged": False}]
    ground_truth = [{"id": 1, "is_error": True}, {"id": 2, "is_error": False}]
    content = _error_case_report(predictions, ground_truth)
    assert "检出" in content or "accuracy" in content.lower() or "准确" in content
    assert "100%" in content


def test_judgment_dict_idless_matches_report():
    from deeptutor.tools.annotation_check import _judgment_dict, _judgment_report

    predictions = [{"label": "correct"}, {"label": "wrong"}]
    ground_truth = [{"answer": True}, {"answer": False}]
    assert _judgment_dict(predictions, ground_truth) == {"accuracy": 1.0, "correct": 2, "total": 2}
    assert "100%" in _judgment_report(predictions, ground_truth)


def test_standard_dict_missing_label_zero():
    from deeptutor.tools.annotation_check import _standard_dict

    predictions = [{"x": 0, "y": 0, "w": 100, "h": 100}]
    ground_truth = [{"required_fields": ["x", "y", "w", "h", "label"]}]
    assert _standard_dict(predictions, ground_truth) == {"compliance_rate": 0.0, "valid": 0, "total": 1}


def test_error_case_dict_idless_matches_report():
    from deeptutor.tools.annotation_check import _error_case_dict, _error_case_report

    predictions = [{"flagged": True}, {"flagged": False}]
    ground_truth = [{"is_error": True}, {"is_error": False}]
    assert _error_case_dict(predictions, ground_truth) == {"accuracy": 1.0, "correct": 2, "total": 2}
    assert "100%" in _error_case_report(predictions, ground_truth)


def test_error_case_unlisted_implicit_not_flagged_full_credit():
    from deeptutor.tools.annotation_check import _error_case_dict, _error_case_report

    # student lists ONLY the error ids; unlisted GT case (id=2, non-error) is implicitly not flagged
    predictions = [{"id": 1, "flagged": True}, {"id": 3, "flagged": True}]
    ground_truth = [{"id": 1, "is_error": True}, {"id": 2, "is_error": False}, {"id": 3, "is_error": True}]
    assert _error_case_dict(predictions, ground_truth) == {"accuracy": 1.0, "correct": 3, "total": 3}
    assert "100%" in _error_case_report(predictions, ground_truth)


def test_error_case_unlisted_missing_error_penalized():
    from deeptutor.tools.annotation_check import _error_case_dict

    # student lists only id=1 (correct), omits id=3 which IS an error -> 2/3
    predictions = [{"id": 1, "flagged": True}]
    ground_truth = [{"id": 1, "is_error": True}, {"id": 2, "is_error": False}, {"id": 3, "is_error": True}]
    assert _error_case_dict(predictions, ground_truth) == {"accuracy": round(2 / 3, 4), "correct": 2, "total": 3}


@pytest.mark.asyncio
async def test_execute_judgment_routes_to_metadata():
    from deeptutor.tools.annotation_check import AnnotationCheckTool

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="judgment",
        predictions='[{"label":"correct"},{"label":"wrong"}]',
        ground_truth='[{"answer":true},{"answer":false}]',
    )
    assert result.success
    assert result.metadata["accuracy"] == 1.0
    assert result.metadata["correct"] == 2


@pytest.mark.asyncio
async def test_execute_standard_routes_to_metadata():
    from deeptutor.tools.annotation_check import AnnotationCheckTool

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="standard",
        predictions='[{"x":0,"y":0,"w":100,"h":100}]',
        ground_truth='[{"required_fields":["x","y","w","h","label"]}]',
    )
    assert result.success
    assert result.metadata["compliance_rate"] == 0.0
    assert result.metadata["total"] == 1


@pytest.mark.asyncio
async def test_execute_error_case_routes_to_metadata():
    from deeptutor.tools.annotation_check import AnnotationCheckTool

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="error_case",
        predictions='[{"flagged":true},{"flagged":false}]',
        ground_truth='[{"is_error":true},{"is_error":false}]',
    )
    assert result.success
    assert result.metadata["accuracy"] == 1.0
    assert result.metadata["correct"] == 2


def test_auto_readiness_thresholds():
    from deeptutor.tools.annotation_check import auto_readiness

    assert auto_readiness(0.9) == "advance"
    assert auto_readiness(0.85) == "advance"
    assert auto_readiness(0.8) == "advance_with_caution"
    assert auto_readiness(0.7) == "advance_with_caution"
    assert auto_readiness(0.68) == "more_practice"
    assert auto_readiness(0.65) == "more_practice"
    assert auto_readiness(0.5) == "review_first"


def test_auto_readiness_floor():
    from deeptutor.tools.annotation_check import auto_readiness

    assert auto_readiness(0.0) == "review_first"
    assert auto_readiness(None) == "review_first"  # missing f1 -> conservative


@pytest.mark.asyncio
async def test_bbox_execute_wires_readiness(monkeypatch):
    from deeptutor.tools.annotation_check import AnnotationCheckTool

    captured = {}
    class _FakeEngine:
        def on_evaluated(self, task_id, f1, *, readiness=None, state_path=None):
            captured["task_id"] = task_id
            captured["f1"] = f1
            captured["readiness"] = readiness
            return {}
    # the bbox branch does `from deeptutor.services.teaching_flow import TeachingFlowEngine`
    # inside execute(), so the module attribute on the target module is what gets called
    monkeypatch.setattr("deeptutor.services.teaching_flow.TeachingFlowEngine", lambda: _FakeEngine())

    predictions = [
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "cat"},
        {"x": 150, "y": 150, "w": 100, "h": 100, "label": "cat"},
        {"x": 300, "y": 300, "w": 100, "h": 100, "label": "cat"},
    ]
    ground_truth = [
        {"x": 10, "y": 10, "w": 100, "h": 100, "label": "cat"},
        {"x": 150, "y": 150, "w": 100, "h": 100, "label": "cat"},
        {"x": 300, "y": 300, "w": 100, "h": 100, "label": "cat"},
    ]
    result = await AnnotationCheckTool().execute(
        predictions=json.dumps(predictions),
        ground_truth=json.dumps(ground_truth),
        task_type="bbox",
        task_id="task1",
    )
    assert result.success
    assert result.metadata["readiness"] == "advance"  # F1=1.0 -> advance
    assert "readiness" in result.content  # content mentions the judgment
    assert captured["readiness"] == "advance"
    assert captured["task_id"] == "task1"
    assert captured["f1"] == 1.0
