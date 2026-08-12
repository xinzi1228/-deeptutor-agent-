from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import secrets
import threading

from deeptutor.services.file_io import atomic_write_json

from .models import GrantMode, ProfileAccessContext, ProfileGrant
from .store import iso, parse_time, utc_now

IDLE_MINUTES = 30
ABSOLUTE_HOURS = 12
TEACHER_MINUTES = 10


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ProfileGrantStore:
    def __init__(self, account_workspace: Path):
        self.file = Path(account_workspace) / "learning_profiles" / "grants.json"
        self._lock = threading.RLock()

    def _read(self) -> list[ProfileGrant]:
        if not self.file.exists():
            return []
        try:
            rows = json.loads(self.file.read_text(encoding="utf-8")).get("grants", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            return []
        fields = ProfileGrant.__dataclass_fields__
        return [ProfileGrant(**{k: v for k, v in row.items() if k in fields}) for row in rows if isinstance(row, dict)]

    def _write(self, grants: list[ProfileGrant]) -> None:
        atomic_write_json(self.file, {"schema_version": 1, "grants": [asdict(item) for item in grants]})

    def issue(self, owner_user_id: str, profile_id: str, *, mode: GrantMode = "student", actor_user_id: str = "") -> tuple[str, ProfileGrant]:
        raw = secrets.token_urlsafe(32)
        now = utc_now()
        duration = timedelta(minutes=TEACHER_MINUTES) if mode != "student" else timedelta(hours=ABSOLUTE_HOURS)
        grant = ProfileGrant(id_hash=_digest(raw), owner_user_id=owner_user_id, profile_id=profile_id, mode=mode, created_at=iso(now), last_activity_at=iso(now), absolute_expires_at=iso(now + duration), actor_user_id=actor_user_id or owner_user_id)
        with self._lock:
            grants = self._read()
            grants.append(grant)
            self._write(grants[-200:])
        return raw, grant

    def validate(self, raw: str, owner_user_id: str, *, touch: bool = True) -> ProfileAccessContext | None:
        if not raw:
            return None
        target = _digest(raw)
        with self._lock:
            grants = self._read()
            index = next((i for i, item in enumerate(grants) if secrets.compare_digest(item.id_hash, target)), None)
            if index is None:
                return None
            grant = grants[index]
            now = utc_now()
            last = parse_time(grant.last_activity_at)
            absolute = parse_time(grant.absolute_expires_at)
            expired = bool(grant.revoked_at) or not absolute or absolute <= now or not last or last + timedelta(minutes=IDLE_MINUTES) <= now
            if expired or grant.owner_user_id != owner_user_id:
                return None
            if touch and last and (now - last).total_seconds() >= 60:
                grant = ProfileGrant(**{**asdict(grant), "last_activity_at": iso(now)})
                grants[index] = grant
                self._write(grants)
        return ProfileAccessContext(owner_user_id=grant.owner_user_id, profile_id=grant.profile_id, mode=grant.mode, actor_user_id=grant.actor_user_id, read_only=grant.mode == "teacher_view")

    def revoke(self, raw: str, owner_user_id: str) -> bool:
        target = _digest(raw) if raw else ""
        with self._lock:
            grants = self._read()
            changed = False
            for index, grant in enumerate(grants):
                if grant.owner_user_id == owner_user_id and secrets.compare_digest(grant.id_hash, target) and not grant.revoked_at:
                    grants[index] = ProfileGrant(**{**asdict(grant), "revoked_at": iso(utc_now())})
                    changed = True
            if changed:
                self._write(grants)
            return changed
