"""ShareStore — token→session share entries (免登录分享)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import secrets
import time


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class ShareEntry:
    token: str
    session_id: str
    created_at_ms: int
    expires_at_ms: int | None = None


class ShareStore:
    """JSON-persisted share entries. Token is the only auth — keep it secret."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[str, ShareEntry] = {}

    def _load(self) -> None:
        if self._entries:
            return
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for raw in data.values():
                e = ShareEntry(**raw)
                self._entries[e.token] = e
        except Exception:
            self._entries = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {token: asdict(e) for token, e in self._entries.items()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def create(self, session_id: str, *, ttl_seconds: int | None = None) -> ShareEntry:
        self._load()
        token = secrets.token_urlsafe(16)
        now = _now_ms()
        entry = ShareEntry(
            token=token,
            session_id=session_id,
            created_at_ms=now,
            expires_at_ms=(now + ttl_seconds * 1000) if ttl_seconds else None,
        )
        self._entries[token] = entry
        self._save()
        return entry

    def get(self, token: str) -> ShareEntry | None:
        self._load()
        entry = self._entries.get(token)
        if entry is None:
            return None
        if entry.expires_at_ms and entry.expires_at_ms <= _now_ms():
            self._entries.pop(token, None)
            self._save()
            return None
        return entry

    def revoke(self, token: str) -> bool:
        self._load()
        if token not in self._entries:
            return False
        del self._entries[token]
        self._save()
        return True


_store: ShareStore | None = None


def get_share_store() -> ShareStore:
    """Process-wide share store, anchored at the admin workspace."""
    global _store
    if _store is None:
        from deeptutor.multi_user.paths import get_admin_path_service

        root = get_admin_path_service().workspace_root
        _store = ShareStore(root / "shares.json")
    return _store


__all__ = ["ShareEntry", "ShareStore", "get_share_store"]
