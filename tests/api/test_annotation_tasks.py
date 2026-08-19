"""Annotation workbench task list — GET /api/v1/annotation/tasks practice filtering.

The workbench must only expose hands-on practice tasks (bbox/audio/video/ner);
theory tasks (classification/judgment/standard/error_case) stay with the chat.
"""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip("fastapi")

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient

annotation_router = importlib.import_module("deeptutor.api.routers.annotation").router

API = "/api/v1/annotation"

PRACTICE_TYPES = {"bbox", "audio_event", "audio_transcription", "video_event", "video_tracking", "ner"}


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(annotation_router, prefix=API)
    return TestClient(app)


def test_tasks_practice_only_filters_theory(client: TestClient) -> None:
    """practice_only=true 只返回实践操作题。"""
    resp = client.get(f"{API}/tasks?practice_only=true")
    assert resp.status_code == 200
    tasks = resp.json()["tasks"]
    assert tasks
    types = {t["type"] for t in tasks}
    assert types <= PRACTICE_TYPES
    assert "classification" not in types


def test_tasks_default_returns_all(client: TestClient) -> None:
    """不带 practice_only 返回全部题目。"""
    resp = client.get(f"{API}/tasks")
    assert resp.status_code == 200
    assert len(resp.json()["tasks"]) >= 100  # 102 题
