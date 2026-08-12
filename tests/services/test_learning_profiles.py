from __future__ import annotations

from datetime import timedelta
import json

import pytest

from deeptutor.services.learning_profiles.grants import IDLE_MINUTES, ProfileGrantStore
from deeptutor.services.learning_profiles.pin import MAX_FAILED_ATTEMPTS, hash_pin, verify_pin
from deeptutor.services.learning_profiles.store import (
    LearningProfileStore,
    ProfileLockedError,
    iso,
    utc_now,
)


def test_pin_hash_is_not_plaintext_and_verifies():
    hashed = hash_pin("123456")
    assert hashed != "123456"
    assert verify_pin("123456", hashed)
    assert not verify_pin("654321", hashed)
    assert not verify_pin("abc", hashed)


def test_create_profile_writes_private_tree_without_pin_in_public_payload(tmp_path):
    store = LearningProfileStore(tmp_path / "workspace")
    profile = store.create("u_one", "小明", "1234", "icon:star:blue")

    assert profile.id.startswith("lp_")
    assert "pin_hash" not in profile.public_dict()
    assert store.get("u_one", profile.id) == profile
    assert store.get("u_two", profile.id) is None
    for child in ("sessions", "memory", "learning", "annotation", "artifacts", "inbox"):
        assert (store.profile_root(profile.id) / child).is_dir()


def test_wrong_pin_freezes_after_bounded_attempts(tmp_path):
    store = LearningProfileStore(tmp_path / "workspace")
    profile = store.create("u_one", "学生", "1234")
    for _ in range(MAX_FAILED_ATTEMPTS - 1):
        with pytest.raises(PermissionError):
            store.verify_and_record("u_one", profile.id, "9999")
    with pytest.raises(ProfileLockedError) as error:
        store.verify_and_record("u_one", profile.id, "9999")
    assert error.value.locked_until
    locked = store.get("u_one", profile.id)
    assert locked is not None and locked.locked_until
    with pytest.raises(ProfileLockedError):
        store.verify_and_record("u_one", profile.id, "1234")


def test_successful_unlock_clears_failure_state(tmp_path):
    store = LearningProfileStore(tmp_path / "workspace")
    profile = store.create("u_one", "学生", "1234")
    with pytest.raises(PermissionError):
        store.verify_and_record("u_one", profile.id, "9999")
    unlocked = store.verify_and_record("u_one", profile.id, "1234")
    assert unlocked.failed_attempts == 0
    assert unlocked.locked_until == ""


def test_grant_is_account_bound_revocable_and_not_stored_raw(tmp_path):
    grants = ProfileGrantStore(tmp_path / "workspace")
    raw, issued = grants.issue("u_one", "lp_" + "a" * 24)
    rendered = grants.file.read_text(encoding="utf-8")
    assert raw not in rendered
    assert grants.validate(raw, "u_two") is None
    context = grants.validate(raw, "u_one")
    assert context and context.profile_id == issued.profile_id
    assert grants.revoke(raw, "u_one")
    assert grants.validate(raw, "u_one") is None


def test_grant_expires_after_idle_timeout(tmp_path):
    grants = ProfileGrantStore(tmp_path / "workspace")
    raw, _ = grants.issue("u_one", "lp_" + "a" * 24)
    payload = json.loads(grants.file.read_text(encoding="utf-8"))
    payload["grants"][0]["last_activity_at"] = iso(utc_now() - timedelta(minutes=IDLE_MINUTES + 1))
    grants.file.write_text(json.dumps(payload), encoding="utf-8")
    assert grants.validate(raw, "u_one") is None


def test_teacher_view_is_read_only(tmp_path):
    grants = ProfileGrantStore(tmp_path / "workspace")
    raw, _ = grants.issue("u_teacher", "lp_" + "a" * 24, mode="teacher_view")
    context = grants.validate(raw, "u_teacher")
    assert context is not None
    assert context.read_only is True
    assert context.mode == "teacher_view"
