from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import threading
import uuid

from deeptutor.services.file_io import atomic_write_json

from .models import LearningProfile
from .pin import LOCK_MINUTES, MAX_FAILED_ATTEMPTS, hash_pin, verify_pin

PROFILE_ID_RE = re.compile(r"^lp_[a-f0-9]{24}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat()


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class ProfileLockedError(RuntimeError):
    def __init__(self, locked_until: str):
        super().__init__("学习档案暂时锁定")
        self.locked_until = locked_until


class LearningProfileStore:
    def __init__(self, account_workspace: Path):
        self.root = Path(account_workspace) / "learning_profiles"
        self.file = self.root / "profiles.json"
        self.audit_file = self.root / "audit.jsonl"
        self._lock = threading.RLock()

    def _read(self) -> dict:
        if not self.file.exists():
            return {"schema_version": 1, "profiles": []}
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": 1, "profiles": []}
        return data if isinstance(data, dict) else {"schema_version": 1, "profiles": []}

    def _write_profiles(self, profiles: list[LearningProfile]) -> None:
        atomic_write_json(self.file, {"schema_version": 1, "profiles": [asdict(item) for item in profiles]})

    @staticmethod
    def _decode(item: dict) -> LearningProfile:
        fields = LearningProfile.__dataclass_fields__
        return LearningProfile(**{key: value for key, value in item.items() if key in fields})

    def list(self, owner_user_id: str, *, include_disabled: bool = False) -> list[LearningProfile]:
        with self._lock:
            profiles = [self._decode(item) for item in self._read().get("profiles", []) if isinstance(item, dict)]
        return [item for item in profiles if item.owner_user_id == owner_user_id and (include_disabled or not item.disabled)]

    def get(self, owner_user_id: str, profile_id: str) -> LearningProfile | None:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            return None
        return next((item for item in self.list(owner_user_id, include_disabled=True) if item.id == profile_id), None)

    def create(self, owner_user_id: str, name: str, pin: str, avatar: str = "") -> LearningProfile:
        clean_name = str(name).strip()
        if not clean_name or len(clean_name) > 40:
            raise ValueError("档案名称需要 1 到 40 个字符")
        now = iso(utc_now())
        profile = LearningProfile(
            id=f"lp_{uuid.uuid4().hex[:24]}", owner_user_id=owner_user_id, name=clean_name,
            avatar=str(avatar).strip()[:120], created_at=now, updated_at=now, pin_hash=hash_pin(pin),
        )
        with self._lock:
            profiles = [self._decode(item) for item in self._read().get("profiles", []) if isinstance(item, dict)]
            profiles.append(profile)
            self._write_profiles(profiles)
        self.ensure_profile_dirs(profile.id)
        return profile

    def update(self, owner_user_id: str, profile_id: str, *, name: str | None = None, avatar: str | None = None, disabled: bool | None = None) -> LearningProfile:
        with self._lock:
            profiles = [self._decode(item) for item in self._read().get("profiles", []) if isinstance(item, dict)]
            index = next((i for i, item in enumerate(profiles) if item.id == profile_id and item.owner_user_id == owner_user_id), None)
            if index is None:
                raise KeyError(profile_id)
            current = profiles[index]
            clean_name = current.name if name is None else str(name).strip()
            if not clean_name or len(clean_name) > 40:
                raise ValueError("档案名称需要 1 到 40 个字符")
            profiles[index] = replace(current, name=clean_name, avatar=current.avatar if avatar is None else str(avatar)[:120], disabled=current.disabled if disabled is None else disabled, updated_at=iso(utc_now()))
            self._write_profiles(profiles)
            return profiles[index]

    def verify_and_record(self, owner_user_id: str, profile_id: str, pin: str) -> LearningProfile:
        with self._lock:
            profiles = [self._decode(item) for item in self._read().get("profiles", []) if isinstance(item, dict)]
            index = next((i for i, item in enumerate(profiles) if item.id == profile_id and item.owner_user_id == owner_user_id and not item.disabled), None)
            if index is None:
                raise KeyError(profile_id)
            current = profiles[index]
            locked = parse_time(current.locked_until)
            now = utc_now()
            if locked and locked > now:
                raise ProfileLockedError(current.locked_until)
            if verify_pin(pin, current.pin_hash):
                profiles[index] = replace(current, failed_attempts=0, locked_until="", updated_at=iso(now))
                self._write_profiles(profiles)
                return profiles[index]
            failed = current.failed_attempts + 1
            locked_until = iso(now + timedelta(minutes=LOCK_MINUTES)) if failed >= MAX_FAILED_ATTEMPTS else ""
            profiles[index] = replace(current, failed_attempts=0 if locked_until else failed, locked_until=locked_until, updated_at=iso(now))
            self._write_profiles(profiles)
            if locked_until:
                raise ProfileLockedError(locked_until)
            raise PermissionError("PIN 不正确")

    def change_pin(self, owner_user_id: str, profile_id: str, new_pin: str) -> LearningProfile:
        with self._lock:
            profiles = [self._decode(item) for item in self._read().get("profiles", []) if isinstance(item, dict)]
            index = next((i for i, item in enumerate(profiles) if item.id == profile_id and item.owner_user_id == owner_user_id), None)
            if index is None:
                raise KeyError(profile_id)
            profiles[index] = replace(profiles[index], pin_hash=hash_pin(new_pin), failed_attempts=0, locked_until="", updated_at=iso(utc_now()))
            self._write_profiles(profiles)
            return profiles[index]

    def profile_root(self, profile_id: str) -> Path:
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise ValueError("无效学习档案 ID")
        return self.root / profile_id

    def ensure_profile_dirs(self, profile_id: str) -> Path:
        root = self.profile_root(profile_id)
        for child in ("sessions", "memory", "learning", "annotation", "artifacts", "inbox"):
            (root / child).mkdir(parents=True, exist_ok=True)
        return root
