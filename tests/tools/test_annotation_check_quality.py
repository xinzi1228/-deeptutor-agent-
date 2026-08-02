"""Pixel-quality heuristic checks for annotation_check (edge/overlap/tightness)."""

from __future__ import annotations

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
