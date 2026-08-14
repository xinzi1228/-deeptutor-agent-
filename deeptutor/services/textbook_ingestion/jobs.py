from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any
import uuid

from deeptutor.services.file_io import atomic_write_json

from .converter import TextbookConverter
from .models import TextbookJob, utc_now


class TextbookJobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.jobs_dir = self.root / "jobs"
        self.outputs_dir = self.root / "outputs"
        self._lock = threading.RLock()

    def _path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def create(self, *, source_path: Path, original_name: str, source_hash: str, engine: str | None) -> TextbookJob:
        job = TextbookJob(
            id=f"tb_{uuid.uuid4().hex}",
            source_path=str(source_path),
            original_name=original_name,
            source_hash=source_hash,
            engine=engine,
        )
        self.save(job)
        return job

    def save(self, job: TextbookJob) -> TextbookJob:
        with self._lock:
            self.jobs_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self._path(job.id), job.model_dump(mode="json"))
        return job

    def get(self, job_id: str) -> TextbookJob | None:
        path = self._path(job_id)
        if not path.is_file():
            return None
        try:
            return TextbookJob.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def list(self, *, limit: int = 100) -> list[TextbookJob]:
        if not self.jobs_dir.is_dir():
            return []
        rows = [job for path in self.jobs_dir.glob("*.json") if (job := self.get(path.stem)) is not None]
        rows.sort(key=lambda row: row.created_at)
        return rows[-max(1, min(limit, 200)):]

    def update(self, job_id: str, **changes: Any) -> TextbookJob:
        with self._lock:
            current = self.get(job_id)
            if current is None:
                raise FileNotFoundError(job_id)
            payload = current.model_dump(mode="json")
            payload.update(changes)
            payload["updated_at"] = utc_now()
            return self.save(TextbookJob.model_validate(payload))


def run_textbook_job(root: Path, job_id: str) -> None:
    store = TextbookJobStore(root)
    job = store.get(job_id)
    if job is None or job.status == "cancelled":
        return
    existing_manifest = Path(job.manifest_path) if job.manifest_path else None
    if job.status in {"completed", "needs_review"} and existing_manifest and existing_manifest.is_file():
        return
    store.update(job_id, status="running", progress_message="正在通过统一文档解析服务转换教材")
    try:
        artifact = TextbookConverter(store.outputs_dir).convert(
            Path(job.source_path),
            job_id=job.id,
            engine=job.engine,
            on_output=lambda message: store.update(job_id, progress_message=message),
        )
        latest = store.get(job_id)
        if latest is None or latest.status == "cancelled":
            return
        store.update(
            job_id,
            status="needs_review" if artifact.review_issues else "completed",
            progress_message="转换完成，等待人工复核" if artifact.review_issues else "转换完成",
            total_pages=artifact.total_pages,
            successful_pages=artifact.successful_page_count,
            review_pages=artifact.review_page_count,
            failed_pages=artifact.failed_page_count,
            resume_cursor=artifact.total_pages,
            markdown_path=artifact.markdown_path,
            manifest_path=artifact.manifest_path,
            parser_signature=artifact.parser_signature,
            parser_engine=artifact.parser_engine,
            error="",
        )
    except Exception as exc:  # noqa: BLE001 - persisted for resumable admin retry
        store.update(job_id, status="failed", progress_message="转换失败，可从已保存原件重试", error=str(exc))

