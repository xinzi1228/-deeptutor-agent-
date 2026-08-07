"""Annotation grading endpoint — POST /api/v1/annotation/check.

Thin HTTP wrapper over the pure ``annotation_check._*_dict`` metrics so the
annotation tools / Coach / frontend can grade a submission without routing
through the chat loop. No Label Studio dependency.
"""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip("fastapi")

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient

annotation_router = importlib.import_module("deeptutor.api.routers.annotation").router

API = "/api/v1/annotation"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(annotation_router, prefix=API)
    return TestClient(app)


def test_check_bbox(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "bbox",
            "predictions": [
                {"x": 10, "y": 10, "w": 50, "h": 50, "label": "cat"},
                {"x": 90, "y": 90, "w": 50, "h": 50, "label": "cat"},
            ],
            "ground_truth": [{"x": 10, "y": 10, "w": 50, "h": 50, "label": "cat"}],
            "image_size": "500x500",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "precision" in data["metrics"]
    assert "recall" in data["metrics"]
    assert "f1" in data["metrics"]
    assert data["metrics"]["f1"] > 0


def test_check_classification(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "classification",
            "predictions": [{"id": 1, "label": "positive"}],
            "ground_truth": [{"id": 1, "label": "positive"}, {"id": 2, "label": "negative"}],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["accuracy"] == 0.5
    assert data["metrics"]["correct"] == 1
    assert data["metrics"]["total"] == 2


def test_check_ner(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "ner",
            "predictions": [{"start": 0, "end": 4, "label": "PER"}],
            "ground_truth": [{"start": 0, "end": 4, "label": "PER"}, {"start": 9, "end": 13, "label": "LOC"}],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["f1"] > 0


def test_check_invalid_task_type(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={"task_type": "bogus", "predictions": [], "ground_truth": []},
    )
    assert res.status_code == 400


def test_check_invalid_json(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={"task_type": "bbox", "predictions": "not-json", "ground_truth": "[]"},
    )
    assert res.status_code == 400


def test_check_judgment_report_present(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "judgment",
            "predictions": [{"id": 1, "label": "true"}],
            "ground_truth": [{"id": 1, "answer": True}],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "report" in data
    assert "判断" in data["report"] or "accuracy" in data["metrics"]


def test_check_non_dict_predictions_400(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={"task_type": "bbox", "predictions": [1, 2, 3], "ground_truth": []},
    )
    assert res.status_code == 400


def test_check_missing_predictions_400(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={"task_type": "bbox", "ground_truth": []},
    )
    assert res.status_code == 400


@pytest.mark.parametrize(
    "task_type, predictions, ground_truth, metric_key",
    [
        ("judgment", [{"id": 1, "label": "true"}], [{"id": 1, "answer": True}], "accuracy"),
        ("standard", [{"x": 1, "y": 2, "w": 3, "h": 4, "label": "cat"}], [{"required_fields": ["x", "y", "w", "h", "label"], "labels": ["cat"]}], "compliance_rate"),
        ("error_case", [{"id": 1, "flagged": True}], [{"id": 1, "is_error": True}], "accuracy"),
        ("audio_event", [{"label": "knock", "start_time": 0.0, "end_time": 1.0}], [{"label": "knock", "start_time": 0.0, "end_time": 1.0}], "f1"),
        ("audio_transcription", [{"id": 1, "text": "hello world"}], [{"id": 1, "text": "hello world"}], "accuracy"),
        ("video_tracking", [{"frame": 0, "boxes": [{"x": 0, "y": 0, "w": 5, "h": 5, "label": "a"}]}], [{"frame": 0, "boxes": [{"x": 0, "y": 0, "w": 5, "h": 5, "label": "a"}]}], "f1"),
        ("video_event", [{"label": "run", "start_time": 0.0, "end_time": 2.0}], [{"label": "run", "start_time": 0.0, "end_time": 2.0}], "f1"),
    ],
)
def test_check_other_task_types(client: TestClient, task_type: str, predictions: list[dict], ground_truth: list[dict], metric_key: str) -> None:
    res = client.post(f"{API}/check", json={"task_type": task_type, "predictions": predictions, "ground_truth": ground_truth})
    assert res.status_code == 200
    data = res.json()
    assert data["task_type"] == task_type
    assert metric_key in data["metrics"]
