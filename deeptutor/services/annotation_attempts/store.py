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
        self.pending_file = self.root / "pending_submissions.jsonl"
        self.current_file = self.root / "current.json"
        self._lock = threading.RLock()
        self._task_observer = task_observer or self._notify_current_task

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def _read_rows(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.attempts_file)

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        content = "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in rows
        )
        atomic_write_text(path, content)

    def list_attempts(self, *, task_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        rows = self._read_rows()
        if task_id:
            rows = [row for row in rows if row.get("task_id") == task_id]
        return rows[-max(1, min(limit, 100)):]

    def save_draft(self, task_id: str, mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_id = _SAFE_ID.sub("_", task_id.strip())[:100]
        if not clean_id:
            raise ValueError("缺少任务编号")
        with self._lock:
            previous = self.get_draft(task_id) or {}
            record = {
                "schema_version": 2,
                "version": int(previous.get("version") or 0) + 1,
                "task_id": task_id,
                "mode": mode,
                "payload": _safe_payload(payload),
                "sync_status": "backend_saved",
                "formal_revision": {},
                "last_sync_error": "",
                "updated_at": _now(),
            }
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

    def mark_draft_sync_status(
        self,
        task_id: str,
        status: str,
        *,
        revision: dict[str, Any] | None = None,
        detail: str = "",
    ) -> dict[str, Any] | None:
        with self._lock:
            draft = self.get_draft(task_id)
            if draft is None:
                return None
            draft["sync_status"] = status
            draft["formal_revision"] = _safe_payload(revision or {})
            draft["last_sync_error"] = str(detail)[:500]
            draft["updated_at"] = _now()
            clean_id = _SAFE_ID.sub("_", task_id.strip())[:100]
            atomic_write_json(self.drafts / f"{clean_id}.json", draft)
            return draft

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
        sync_status: str = "local",
        revision: dict[str, Any] | None = None,
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
                "sync_status": sync_status,
                "revision": revision or {},
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

    def queue_submission(
        self,
        *,
        task_id: str,
        task_type: str,
        mode: str,
        payload: dict[str, Any],
        metrics: dict[str, Any],
        report: str,
        idempotency_key: str,
        source: str = "teaching_workbench",
    ) -> tuple[dict[str, Any], bool]:
        key = idempotency_key.strip()[:160]
        if not key:
            raise ValueError("缺少幂等键")
        with self._lock:
            rows = self._read_jsonl(self.pending_file)
            existing = next((row for row in rows if row.get("idempotency_key") == key), None)
            if existing is not None:
                return existing, False
            record = {
                "schema_version": 1,
                "id": f"pending_{uuid.uuid4().hex}",
                "idempotency_key": key,
                "task_id": task_id,
                "task_type": task_type,
                "mode": mode,
                "payload": _safe_payload(payload),
                "metrics": _safe_payload(metrics),
                "report": str(report)[:8000],
                "source": source,
                "sync_status": "queued",
                "retry_count": 0,
                "last_error": "",
                "revision": {},
                "finalized": False,
                "created_at": _now(),
                "updated_at": _now(),
            }
            rows.append(record)
            self._write_jsonl(self.pending_file, rows)
            return record, True

    def list_pending_submissions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.pending_file)
        pending = [
            row
            for row in rows
            if row.get("sync_status") != "synced" or not bool(row.get("finalized"))
        ]
        return pending[-max(1, min(limit, 100)):]

    def _update_pending(self, idempotency_key: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            rows = self._read_jsonl(self.pending_file)
            target: dict[str, Any] | None = None
            for row in rows:
                if row.get("idempotency_key") == idempotency_key:
                    row.update(changes)
                    row["updated_at"] = _now()
                    target = row
                    break
            if target is None:
                raise ValueError("找不到待同步提交")
            self._write_jsonl(self.pending_file, rows)
            return target

    def mark_submission_retry(self, idempotency_key: str, detail: str) -> dict[str, Any]:
        current = next(
            (row for row in self._read_jsonl(self.pending_file) if row.get("idempotency_key") == idempotency_key),
            None,
        )
        if current is None:
            raise ValueError("找不到待同步提交")
        return self._update_pending(
            idempotency_key,
            sync_status="retry_pending",
            retry_count=int(current.get("retry_count") or 0) + 1,
            last_error=str(detail)[:500],
        )

    def mark_submission_synced(
        self, idempotency_key: str, *, revision: dict[str, Any]
    ) -> dict[str, Any]:
        return self._update_pending(
            idempotency_key,
            sync_status="synced",
            last_error="",
            revision=_safe_payload(revision),
        )

    def finalize_submission(self, idempotency_key: str) -> tuple[dict[str, Any], bool]:
        with self._lock:
            row = next(
                (item for item in self._read_jsonl(self.pending_file) if item.get("idempotency_key") == idempotency_key),
                None,
            )
            if row is None or row.get("sync_status") != "synced":
                raise ValueError("提交尚未同步为正式修订版本")
            attempt, created = self.append_attempt(
                task_id=str(row.get("task_id") or ""),
                task_type=str(row.get("task_type") or "bbox"),
                mode=str(row.get("mode") or "teaching"),
                payload=row.get("payload") if isinstance(row.get("payload"), dict) else {},
                metrics=row.get("metrics") if isinstance(row.get("metrics"), dict) else {},
                report=str(row.get("report") or ""),
                idempotency_key=idempotency_key,
                source=str(row.get("source") or "teaching_workbench"),
                sync_status="synced",
                revision=row.get("revision") if isinstance(row.get("revision"), dict) else {},
            )
            self._update_pending(
                idempotency_key,
                finalized=True,
                finalized_at=_now(),
            )
            return attempt, created

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
