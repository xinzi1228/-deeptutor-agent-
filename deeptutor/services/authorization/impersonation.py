from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import threading
from typing import Any


def _sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ImpersonationAuditWriter:
    """Append-only, idempotent audit writer that never stores private payloads."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def append(
        self,
        *,
        access: Any,
        operation: str,
        outcome: str,
        resource_type: str = "",
        resource_id: str = "",
        request_id: str = "",
        before: Any = None,
        after: Any = None,
        error_code: str = "",
    ) -> None:
        dedupe_key = _sha256(
            {
                "impersonation_id": access.impersonation_id,
                "request_id": request_id,
                "operation": operation,
                "resource_type": resource_type,
                "resource_id": resource_id,
            }
        )
        metadata: dict[str, Any] = {
            "dedupe_key": dedupe_key,
            "request_id": request_id,
            "operation": operation,
            "reason": access.reason,
            "impersonation_id": access.impersonation_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
        }
        if before is not None:
            metadata["before_sha256"] = _sha256(before)
        if after is not None:
            metadata["after_sha256"] = _sha256(after)
        if error_code:
            metadata["error_code"] = error_code
        row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "impersonated_mutation",
            "owner_user_id": access.owner_user_id,
            "profile_id": access.profile_id,
            "actor_user_id": access.actor_user_id,
            "mode": access.mode,
            "outcome": outcome,
            "metadata": metadata,
        }

        with self._lock:
            if self._already_written(dedupe_key):
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    def _already_written(self, dedupe_key: str) -> bool:
        if not self.path.exists():
            return False
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("metadata", {}).get("dedupe_key") == dedupe_key:
                    return True
        return False
