from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any, Callable
import uuid

from deeptutor.services.file_io import atomic_write_json, atomic_write_text

_SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")
_MAX_PAYLOAD_BYTES = 256_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("标注内容必须是对象")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise ValueError("单次标注内容不能超过 256KB")
    return payload


class AnnotationAttemptStore:
    """Durable, profile-private annotation state.

    Drafts and current activity are replaceable projections. Submitted attempts
    are append-only and de-duplicated by a client supplied idempotency key.
    """

    def __init__(
        self,
        profile_root: Path,
        *,
        task_observer: Callable[[str, str, str], None] | None = None,
    ):
        self.profile_root = Path(profile_root)
        self.root = self.profile_root / "annotation"
        self.drafts = self.root / "drafts"
        self.attempts_file = self.root / "attempts.jsonl"
        self.current_file = self.root / "current.json"
        self._lock = threading.RLock()
        self._task_observer = task_observer or self._notify_current_task

    def _read_rows(self) -> list[dict[str, Any]]:
        if not self.attempts_file.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.attempts_file.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def list_attempts(self, *, task_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        rows = self._read_rows()
        if task_id:
            rows = [row for row in rows if row.get("task_id") == task_id]
        return rows[-max(1, min(limit, 100)):]

    def save_draft(self, task_id: str, mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_id = _SAFE_ID.sub("_", task_id.strip())[:100]
        if not clean_id:
            raise ValueError("缺少任务编号")
        record = {
            "schema_version": 1,
            "task_id": task_id,
            "mode": mode,
            "payload": _safe_payload(payload),
            "updated_at": _now(),
        }
        with self._lock:
            atomic_write_json(self.drafts / f"{clean_id}.json", record)
            self.set_current(task_id=task_id, mode=mode, stage="editing", summary={"has_draft": True})
            self._task_observer("draft_saved", task_id, f"annotation/drafts/{clean_id}.json")
        return record

    def get_draft(self, task_id: str) -> dict[str, Any] | None:
        clean_id = _SAFE_ID.sub("_", task_id.strip())[:100]
        path = self.drafts / f"{clean_id}.json"
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def append_attempt(
        self,
        *,
        task_id: str,
        task_type: str,
        mode: str,
        payload: dict[str, Any],
        metrics: dict[str, Any] | None,
        report: str,
        idempotency_key: str,
        source: str = "teaching_workbench",
    ) -> tuple[dict[str, Any], bool]:
        key = idempotency_key.strip()[:160]
        if not key:
            raise ValueError("缺少幂等键")
        with self._lock:
            rows = self._read_rows()
            existing = next((row for row in rows if row.get("idempotency_key") == key), None)
            if existing is not None:
                return existing, False
            record = {
                "schema_version": 1,
                "id": f"attempt_{uuid.uuid4().hex}",
                "idempotency_key": key,
                "task_id": task_id,
                "task_type": task_type,
                "mode": mode,
                "payload": _safe_payload(payload),
                "metrics": metrics or {},
                "report": str(report)[:8000],
                "source": source,
                "sync_status": "local",
                "created_at": _now(),
            }
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            existing_text = self.attempts_file.read_text(encoding="utf-8") if self.attempts_file.exists() else ""
            prefix = existing_text if not existing_text or existing_text.endswith("\n") else existing_text + "\n"
            atomic_write_text(self.attempts_file, prefix + line + "\n")
            self.set_current(
                task_id=task_id,
                mode=mode,
                stage="submitted",
                summary={"attempt_id": record["id"], "metrics": record["metrics"]},
            )
            self._task_observer("attempt_submitted", task_id, record["id"])
            return record, True

    @staticmethod
    def _notify_current_task(event_type: str, task_id: str, reference: str) -> None:
        """Publish references only; annotation payload remains in its source store."""
        try:
            from deeptutor.services.current_learning_task.service import (
                get_current_learning_task_service,
            )

            service = get_current_learning_task_service()
            current = service.get()
            if current is None or current.task_id != task_id:
                return
            kwargs = (
                {"draft_ref": reference}
                if event_type == "draft_saved"
                else {"latest_submission_ref": reference}
            )
            service.patch_context(
                **kwargs,
                expected_version=current.version,
                idempotency_key=f"annotation:{event_type}:{reference}",
            )
        except (ImportError, PermissionError, RuntimeError, ValueError):
            return

    def set_current(
        self,
        *,
        task_id: str,
        mode: str,
        stage: str,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = {
            "schema_version": 1,
            "task_id": str(task_id)[:120],
            "mode": str(mode)[:40],
            "stage": str(stage)[:60],
            "summary": _safe_payload(summary or {}),
            "updated_at": _now(),
        }
        atomic_write_json(self.current_file, current)
        return current

    def current(self) -> dict[str, Any]:
        if not self.current_file.exists():
            return {}
        try:
            value = json.loads(self.current_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}
