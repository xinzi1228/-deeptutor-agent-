from __future__ import annotations

from deeptutor.services.annotation_scoring import (
    AnnotationScoreStore,
    BboxScorer,
    parse_label_studio_bbox_result,
)
from deeptutor.services.label_studio_gateway.client import build_label_studio_result


def test_bbox_scoring_is_deterministic_and_versioned() -> None:
    scorer = BboxScorer(rule_version="bbox-iou-0.5-v1")
    predictions = [{"x": 10, "y": 10, "w": 50, "h": 50, "label": "car"}]
    ground_truth = [{"x": 10, "y": 10, "w": 50, "h": 50, "label": "car"}]

    first = scorer.score(predictions, ground_truth, reference_version="task-bank:sha256:abc")
    second = scorer.score(predictions, ground_truth, reference_version="task-bank:sha256:abc")

    assert first.metrics == second.metrics
    assert first.metrics["f1"] == 1.0
    assert first.rule_version == "bbox-iou-0.5-v1"
    assert first.reference_version == "task-bank:sha256:abc"
    assert first.score_hash == second.score_hash


def test_score_store_keeps_initial_and_correction_delta(tmp_path) -> None:
    store = AnnotationScoreStore(tmp_path)
    initial = store.record(
        task_id="task-1",
        attempt_id="attempt-1",
        metrics={"f1": 0.5},
        rule_version="bbox-iou-0.5-v1",
        reference_version="task-bank:sha256:abc",
        score_hash="hash-1",
    )
    corrected = store.record(
        task_id="task-1",
        attempt_id="attempt-2",
        metrics={"f1": 0.9},
        rule_version="bbox-iou-0.5-v1",
        reference_version="task-bank:sha256:abc",
        score_hash="hash-2",
    )

    assert initial["revision_number"] == 1
    assert corrected["revision_number"] == 2
    assert corrected["correction_of"] == "attempt-1"
    assert corrected["metric_delta"]["f1"] == 0.4
    assert len(store.list_scores(task_id="task-1")) == 2


def test_label_studio_bbox_result_round_trips_to_server_coordinates() -> None:
    source = [{"id": "box-1", "x": 12, "y": 24, "w": 80, "h": 40, "label": "车辆"}]
    result = build_label_studio_result("bbox", source, image_size=(200, 100))

    restored, image_size = parse_label_studio_bbox_result(result)

    assert image_size == (200, 100)
    assert restored[0] == {"id": result[0]["id"], "x": 12.0, "y": 24.0, "w": 80.0, "h": 40.0, "label": "车辆"}
