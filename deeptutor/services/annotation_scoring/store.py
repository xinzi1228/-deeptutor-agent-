from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any
import uuid

from deeptutor.services.file_io import atomic_write_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnnotationScoreStore:
    def __init__(self, profile_root: Path) -> None:
        self.path = Path(profile_root) / "annotation" / "scores.jsonl"
        self._lock = threading.RLock()

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows

    def list_scores(self, *, task_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        rows = self._rows()
        if task_id:
            rows = [row for row in rows if row.get("task_id") == task_id]
        return rows[-max(1, min(limit, 100)):]

    def record(
        self,
        *,
        task_id: str,
        attempt_id: str,
        metrics: dict[str, Any],
        rule_version: str,
        reference_version: str,
        score_hash: str,
    ) -> dict[str, Any]:
        with self._lock:
            rows = self._rows()
            existing = next((row for row in rows if row.get("attempt_id") == attempt_id), None)
            if existing:
                return existing
            task_rows = [row for row in rows if row.get("task_id") == task_id]
            previous = task_rows[-1] if task_rows else None
            previous_metrics = previous.get("metrics", {}) if isinstance(previous, dict) else {}
            metric_delta = {
                key: round(float(value) - float(previous_metrics[key]), 6)
                for key, value in metrics.items()
                if isinstance(value, (int, float))
                and isinstance(previous_metrics, dict)
                and isinstance(previous_metrics.get(key), (int, float))
            }
            record = {
                "schema_version": 1,
                "id": f"score_{uuid.uuid4().hex}",
                "task_id": task_id,
                "attempt_id": attempt_id,
                "revision_number": len(task_rows) + 1,
                "correction_of": previous.get("attempt_id", "") if previous else "",
                "metrics": metrics,
                "metric_delta": metric_delta,
                "rule_version": rule_version,
                "reference_version": reference_version,
                "score_hash": score_hash,
                "created_at": _now(),
            }
            rows.append(record)
            content = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
            atomic_write_text(self.path, content)
            return record

