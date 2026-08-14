from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import threading
from typing import Any

from .models import PerformanceMetricInput


class PerformanceMetricStore:
    """Append-only, profile-local store containing only the metric whitelist."""

    _lock = threading.RLock()
    _MAX_BYTES = 5 * 1024 * 1024
    _KEEP_LINES = 2_000

    def __init__(self, profile_root: Path) -> None:
        self.path = Path(profile_root) / "telemetry" / "performance.jsonl"

    def append(self, metric: PerformanceMetricInput) -> dict[str, Any]:
        record = {
            "schema_version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metric.model_dump(mode="json"),
        }
        encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._trim_if_needed()
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded + "\n")
        return record

    def append_many(self, metrics: list[PerformanceMetricInput]) -> int:
        for metric in metrics:
            self.append(metric)
        return len(metrics)

    def summary(self) -> dict[str, Any]:
        records = self._read_records()
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            grouped[str(record["name"])].append(record)
        metrics: dict[str, dict[str, Any]] = {}
        for name, items in sorted(grouped.items()):
            durations = sorted(float(item["duration_ms"]) for item in items)
            metrics[name] = {
                "count": len(items),
                "p50_ms": self._percentile(durations, 0.50),
                "p95_ms": self._percentile(durations, 0.95),
                "error_count": sum(item.get("outcome") == "error" for item in items),
                "timeout_count": sum(item.get("outcome") == "timeout" for item in items),
            }
        return {"schema_version": 1, "total": len(records), "metrics": metrics}

    def _read_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and "name" in record and "duration_ms" in record:
                records.append(record)
        return records

    def _trim_if_needed(self) -> None:
        if not self.path.exists() or self.path.stat().st_size <= self._MAX_BYTES:
            return
        lines = self.path.read_text(encoding="utf-8").splitlines()[-self._KEEP_LINES :]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0
        index = max(0, math.ceil(percentile * len(values)) - 1)
        return round(values[index], 2)
