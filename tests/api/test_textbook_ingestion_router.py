from __future__ import annotations

import io
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile
import pytest

from deeptutor.api.routers import textbook_ingestion as router


@pytest.mark.asyncio
async def test_textbook_upload_is_content_addressed_and_queued(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(router, "get_textbook_root", lambda: tmp_path / "textbooks")
    tasks = BackgroundTasks()
    upload = UploadFile(filename="数据标注教材.pdf", file=io.BytesIO(b"pdf-content"))

    response = await router.import_textbook(background_tasks=tasks, file=upload, engine="markitdown")

    job = response["job"]
    original = Path(job["source_path"])
    assert job["status"] == "queued"
    assert original.read_bytes() == b"pdf-content"
    assert job["source_hash"] in original.as_posix()
    assert len(tasks.tasks) == 1


@pytest.mark.asyncio
async def test_textbook_upload_rejects_unsupported_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(router, "get_textbook_root", lambda: tmp_path / "textbooks")
    upload = UploadFile(filename="程序.exe", file=io.BytesIO(b"bad"))

    with pytest.raises(HTTPException) as exc_info:
        await router.import_textbook(background_tasks=BackgroundTasks(), file=upload, engine=None)

    assert exc_info.value.status_code == 400
