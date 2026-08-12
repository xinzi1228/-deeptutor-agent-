from __future__ import annotations

import json
from pathlib import Path
import threading

from .models import ProfileAuditEvent

_lock = threading.Lock()


def append_audit_event(path: Path, event: ProfileAuditEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": event.timestamp,
        "event": event.event,
        "owner_user_id": event.owner_user_id,
        "profile_id": event.profile_id,
        "actor_user_id": event.actor_user_id,
        "mode": event.mode,
        "outcome": event.outcome,
        "metadata": event.metadata or {},
    }
    with _lock, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
