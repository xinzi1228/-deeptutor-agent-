"""ShareStore — token→session share entries."""

from __future__ import annotations

import json
import time

from deeptutor.services.share import ShareStore


def _store(tmp_path) -> ShareStore:
    return ShareStore(tmp_path / "shares.json")


def test_create_and_get(tmp_path):
    s = _store(tmp_path)
    entry = s.create("sess1")
    assert entry.token
    assert entry.session_id == "sess1"
    got = s.get(entry.token)
    assert got is not None
    assert got.session_id == "sess1"


def test_get_unknown_returns_none(tmp_path):
    s = _store(tmp_path)
    assert s.get("nope") is None


def test_get_expired_returns_none(tmp_path):
    s = _store(tmp_path)
    entry = s.create("sess1", ttl_seconds=1)
    data = json.loads((tmp_path / "shares.json").read_text(encoding="utf-8"))
    data[entry.token]["expires_at_ms"] = int(time.time() * 1000) - 1000
    (tmp_path / "shares.json").write_text(json.dumps(data), encoding="utf-8")
    s._entries = {}  # force reload
    assert s.get(entry.token) is None


def test_revoke(tmp_path):
    s = _store(tmp_path)
    entry = s.create("sess1")
    assert s.revoke(entry.token) is True
    assert s.get(entry.token) is None
    assert s.revoke(entry.token) is False
