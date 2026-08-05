import json

import pytest

import deeptutor.tools.label_studio_tool as ls_mod
from deeptutor.tools.label_studio_tool import LabelStudioImportTool


@pytest.fixture(autouse=True)
def _force_token(monkeypatch):
    monkeypatch.setattr(ls_mod, "LS_API_TOKEN", "test-token")


@pytest.mark.asyncio
async def test_import_success(monkeypatch):
    async def fake_request(method, path, **kwargs):
        assert method == "POST"
        assert path == "/api/projects/7/import"
        body = kwargs["json"]
        assert isinstance(body, list) and len(body) == 2
        return {"task_count": 2, "annotation_count": 0}

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    tasks = json.dumps([{"data": {"image": "a.jpg"}}, {"data": {"image": "b.jpg"}}], ensure_ascii=False)
    result = await tool.execute(project_id=7, tasks=tasks)
    assert result.success is True
    assert "2" in result.content
    assert result.metadata["imported"]["task_count"] == 2


@pytest.mark.asyncio
async def test_import_invalid_json_fails(monkeypatch):
    async def fake_request(method, path, **kwargs):
        raise AssertionError("should not call api")

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    result = await tool.execute(project_id=7, tasks="not-json")
    assert result.success is False


@pytest.mark.asyncio
async def test_import_missing_token_fails(monkeypatch):
    monkeypatch.setattr(ls_mod, "LS_API_TOKEN", "")

    async def fake_request(method, path, **kwargs):
        raise AssertionError("should not call api")

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    result = await tool.execute(project_id=7, tasks="[]")
    assert result.success is False


@pytest.mark.asyncio
async def test_import_missing_project_id_fails(monkeypatch):
    async def fake_request(method, path, **kwargs):
        raise AssertionError("should not call api")

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    result = await tool.execute(tasks="[]")
    assert result.success is False
