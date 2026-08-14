from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Callable

from deeptutor.services.file_io import atomic_write_json

_SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")
_VALID_MODES = {"teaching", "professional"}
_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


class EditLeaseConflict(RuntimeError):
    """The task is actively edited by another mode or browser session."""


class EditLeaseVersionMismatch(RuntimeError):
    """The caller made a decision from a stale lease snapshot."""


class AnnotationEditLeaseStore:
    """Profile-private, expiring single-editor leases for annotation tasks."""

    def __init__(
        self,
        profile_root: Path,
        *,
        ttl_seconds: int = 90,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(profile_root) / "annotation" / "edit_leases"
        self.ttl_seconds = max(15, min(ttl_seconds, 600))
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = _lock_for(self.root)

    @staticmethod
    def _validate(mode: str, browser_session_id: str) -> tuple[str, str]:
        clean_mode = mode.strip()
        clean_session = browser_session_id.strip()[:160]
        if clean_mode not in _VALID_MODES:
            raise ValueError("标注模式只能是 teaching 或 professional")
        if len(clean_session) < 8:
            raise ValueError("浏览器会话编号无效")
        return clean_mode, clean_session

    def _path(self, task_id: str) -> Path:
        clean_id = _SAFE_ID.sub("_", task_id.strip())[:100]
        if not clean_id:
            raise ValueError("缺少任务编号")
        digest = hashlib.sha256(task_id.strip().encode("utf-8")).hexdigest()[:12]
        return self.root / f"{clean_id}-{digest}.json"

    def _read(self, task_id: str) -> dict | None:
        path = self._path(task_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _active(self, lease: dict | None) -> dict | None:
        if not lease:
            return None
        try:
            expires_at = datetime.fromisoformat(str(lease["expires_at"]))
        except (KeyError, TypeError, ValueError):
            return None
        return lease if expires_at > self._now() else None

    def get(self, task_id: str) -> dict | None:
        with self._lock:
            return self._active(self._read(task_id))

    def acquire(
        self,
        task_id: str,
        *,
        mode: str,
        browser_session_id: str,
        takeover: bool = False,
        expected_version: int | None = None,
        saved_draft_version: int = 0,
    ) -> dict:
        clean_mode, clean_session = self._validate(mode, browser_session_id)
        with self._lock:
            previous = self._read(task_id)
            active = self._active(previous)
            previous_version = int((previous or {}).get("version") or 0)
            if active:
                same_owner = (
                    active.get("mode") == clean_mode
                    and active.get("browser_session_id") == clean_session
                )
                if same_owner:
                    return self._write(
                        task_id,
                        mode=clean_mode,
                        browser_session_id=clean_session,
                        version=int(active["version"]),
                        checkpoint_version=int(active.get("checkpoint_version") or 0),
                    )
                if not takeover:
                    raise EditLeaseConflict("该任务正在另一标注模式中编辑，当前模式已转为只读")
                if expected_version != int(active["version"]):
                    raise EditLeaseVersionMismatch("编辑状态已变化，请刷新后再接管")
                checkpoint = int(active.get("checkpoint_version") or 0)
                if checkpoint <= 0 or saved_draft_version != checkpoint:
                    raise EditLeaseConflict("接管前必须保存并确认原模式草稿版本")
                previous_version = int(active["version"])
            return self._write(
                task_id,
                mode=clean_mode,
                browser_session_id=clean_session,
                version=previous_version + 1,
                checkpoint_version=0,
            )

    def mark_checkpoint(
        self,
        task_id: str,
        *,
        mode: str,
        browser_session_id: str,
        expected_version: int,
        draft_version: int,
    ) -> dict:
        clean_mode, clean_session = self._validate(mode, browser_session_id)
        if draft_version <= 0:
            raise ValueError("草稿版本无效")
        with self._lock:
            active = self._active(self._read(task_id))
            if not active:
                raise EditLeaseConflict("编辑权已过期，请重新进入任务")
            if int(active.get("version") or 0) != expected_version:
                raise EditLeaseVersionMismatch("编辑状态已变化，请刷新后再保存")
            if active.get("mode") != clean_mode or active.get("browser_session_id") != clean_session:
                raise EditLeaseConflict("当前浏览器没有该模式的编辑权")
            return self._write(
                task_id,
                mode=clean_mode,
                browser_session_id=clean_session,
                version=expected_version + 1,
                checkpoint_version=draft_version,
            )

    def release(
        self,
        task_id: str,
        *,
        browser_session_id: str,
        expected_version: int,
    ) -> bool:
        with self._lock:
            active = self._active(self._read(task_id))
            if not active:
                return False
            if (
                active.get("browser_session_id") != browser_session_id
                or int(active.get("version") or 0) != expected_version
            ):
                return False
            try:
                self._path(task_id).unlink(missing_ok=True)
            except OSError:
                return False
            return True

    def _write(
        self,
        task_id: str,
        *,
        mode: str,
        browser_session_id: str,
        version: int,
        checkpoint_version: int,
    ) -> dict:
        now = self._now()
        lease = {
            "schema_version": 1,
            "task_id": task_id,
            "mode": mode,
            "browser_session_id": browser_session_id,
            "version": version,
            "checkpoint_version": checkpoint_version,
            "updated_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.ttl_seconds)).isoformat(),
        }
        atomic_write_json(self._path(task_id), lease)
        return lease
