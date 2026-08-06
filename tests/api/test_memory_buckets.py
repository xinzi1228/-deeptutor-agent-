"""Memory bucket management — /api/v1/memory/buckets CRUD.

Backend for the Memory page's 记忆区 (bucket) admin UI: list, create,
read content, delete. Validation lives in ``services.memory.store``;
the router maps ValueError → 400 and missing bucket → 404.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient

memory_router = importlib.import_module("deeptutor.api.routers.memory").router
paths_mod = importlib.import_module("deeptutor.services.memory.paths")

API = "/api/v1/memory"


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(paths_mod, "memory_root", lambda: tmp_path)
    (tmp_path / "L2").mkdir()
    (tmp_path / "L3").mkdir()
    app = FastAPI()
    app.include_router(memory_router, prefix=API)
    return TestClient(app)


def test_list_empty(client: TestClient) -> None:
    res = client.get(f"{API}/buckets")
    assert res.status_code == 200
    assert res.json() == {"buckets": []}


def test_create_and_list(client: TestClient) -> None:
    res = client.post(f"{API}/buckets", json={"name": "标注学习"})
    assert res.status_code == 200
    assert res.json()["created"] is True

    res = client.get(f"{API}/buckets")
    assert res.status_code == 200
    assert res.json()["buckets"] == [{"name": "标注学习"}]


def test_create_duplicate_409(client: TestClient) -> None:
    client.post(f"{API}/buckets", json={"name": "标注学习"})
    res = client.post(f"{API}/buckets", json={"name": "标注学习"})
    assert res.status_code == 409


def test_get_bucket_content(client: TestClient, tmp_path: Path) -> None:
    body = "# 标注学习笔记\n\n- 目标检测框的类别\n- IoU 计算的边界情况"
    chat = tmp_path / "L2" / "标注学习" / "chat.md"
    chat.parent.mkdir(parents=True)
    chat.write_text(body, encoding="utf-8")

    res = client.get(f"{API}/buckets/标注学习")
    assert res.status_code == 200
    payload = res.json()
    assert payload["name"] == "标注学习"
    assert "目标检测框的类别" in payload["content"]
    assert "IoU 计算的边界情况" in payload["content"]


def test_get_bucket_404_when_missing(client: TestClient) -> None:
    res = client.get(f"{API}/buckets/no_such_bucket")
    assert res.status_code == 404


def test_delete_bucket(client: TestClient) -> None:
    client.post(f"{API}/buckets", json={"name": "python学习"})
    res = client.delete(f"{API}/buckets/python学习")
    assert res.status_code == 200

    res = client.get(f"{API}/buckets")
    assert res.json()["buckets"] == []

    res = client.delete(f"{API}/buckets/python学习")
    assert res.status_code == 404


@pytest.mark.parametrize(
    "name",
    ["", "a/b", "a\\b", "..", "a b", "x" * 33],
)
def test_invalid_bucket_name_400(client: TestClient, name: str) -> None:
    res = client.post(f"{API}/buckets", json={"name": name})
    assert res.status_code == 400


def test_invalid_bucket_name_get_400(client: TestClient) -> None:
    res = client.get(f"{API}/buckets/{'x' * 33}")
    assert res.status_code == 400
