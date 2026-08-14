from __future__ import annotations

import json
from pathlib import Path
import threading

from deeptutor.services.file_io import atomic_write_json, atomic_write_text

from .models import CurrentLearningTask, CurrentTaskEvent


class CurrentLearningTaskStore:
    def __init__(self, profile_root: Path):
        self.root = Path(profile_root) / "current_task"
        self.state_file = self.root / "state.json"
        self.events_file = self.root / "events.jsonl"
        self.idempotency_file = self.root / "idempotency.json"
        self._lock = threading.RLock()

    def get(self) -> CurrentLearningTask | None:
        value = self._read_json(self.state_file)
        return CurrentLearningTask.model_validate(value) if value else None

    def save(self, task: CurrentLearningTask) -> CurrentLearningTask:
        atomic_write_json(self.state_file, task.model_dump(mode="json"))
        return task

    def replay(self, key: str) -> CurrentLearningTask | None:
        rows = self._read_json(self.idempotency_file) or {}
        value = rows.get(key)
        return CurrentLearningTask.model_validate(value) if isinstance(value, dict) else None

    def remember(self, key: str, task: CurrentLearningTask) -> None:
        rows = self._read_json(self.idempotency_file) or {}
        rows[key] = task.model_dump(mode="json")
        if len(rows) > 200:
            rows = dict(list(rows.items())[-200:])
        atomic_write_json(self.idempotency_file, rows)

    def append_event(self, event: CurrentTaskEvent) -> None:
        existing = self.events_file.read_text(encoding="utf-8") if self.events_file.exists() else ""
        prefix = existing if not existing or existing.endswith("\n") else existing + "\n"
        line = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
        atomic_write_text(self.events_file, prefix + line + "\n")

    def list_events(self) -> list[CurrentTaskEvent]:
        if not self.events_file.exists():
            return []
        rows = []
        for line in self.events_file.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
                rows.append(CurrentTaskEvent.model_validate(value))
            except (json.JSONDecodeError, ValueError):
                continue
        return rows

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None


__all__ = ["CurrentLearningTaskStore"]
