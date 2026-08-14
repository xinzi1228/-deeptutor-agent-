from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from deeptutor.services.annotation_attempts.edit_lease import (
    AnnotationEditLeaseStore,
    EditLeaseConflict,
    EditLeaseVersionMismatch,
)


def _clock(start: datetime):
    current = [start]

    def now() -> datetime:
        return current[0]

    def advance(seconds: int) -> None:
        current[0] += timedelta(seconds=seconds)

    return now, advance


def test_edit_lease_is_profile_and_task_local(tmp_path) -> None:
    now, _advance = _clock(datetime(2026, 8, 14, tzinfo=timezone.utc))
    first = AnnotationEditLeaseStore(tmp_path / "first", now=now)
    second = AnnotationEditLeaseStore(tmp_path / "second", now=now)

    lease = first.acquire("task-1", mode="teaching", browser_session_id="browser-a")

    assert lease["mode"] == "teaching"
    assert first.get("task-2") is None
    assert second.get("task-1") is None


def test_other_mode_is_read_only_until_explicit_versioned_takeover(tmp_path) -> None:
    now, _advance = _clock(datetime(2026, 8, 14, tzinfo=timezone.utc))
    store = AnnotationEditLeaseStore(tmp_path, now=now)
    lease = store.acquire("task-1", mode="teaching", browser_session_id="browser-a")

    with pytest.raises(EditLeaseConflict):
        store.acquire("task-1", mode="professional", browser_session_id="browser-a")

    checkpointed = store.mark_checkpoint(
        "task-1",
        mode="teaching",
        browser_session_id="browser-a",
        expected_version=lease["version"],
        draft_version=3,
    )
    taken = store.acquire(
        "task-1",
        mode="professional",
        browser_session_id="browser-a",
        takeover=True,
        expected_version=checkpointed["version"],
        saved_draft_version=3,
    )

    assert taken["mode"] == "professional"
    assert taken["version"] == checkpointed["version"] + 1


def test_takeover_rejects_stale_lease_or_unsaved_draft(tmp_path) -> None:
    now, _advance = _clock(datetime(2026, 8, 14, tzinfo=timezone.utc))
    store = AnnotationEditLeaseStore(tmp_path, now=now)
    lease = store.acquire("task-1", mode="teaching", browser_session_id="browser-a")

    with pytest.raises(EditLeaseVersionMismatch):
        store.acquire(
            "task-1",
            mode="professional",
            browser_session_id="browser-b",
            takeover=True,
            expected_version=lease["version"] + 1,
            saved_draft_version=1,
        )
    with pytest.raises(EditLeaseConflict, match="草稿"):
        store.acquire(
            "task-1",
            mode="professional",
            browser_session_id="browser-b",
            takeover=True,
            expected_version=lease["version"],
            saved_draft_version=0,
        )


def test_expired_lease_can_be_replaced_without_takeover(tmp_path) -> None:
    now, advance = _clock(datetime(2026, 8, 14, tzinfo=timezone.utc))
    store = AnnotationEditLeaseStore(tmp_path, ttl_seconds=30, now=now)
    first = store.acquire("task-1", mode="teaching", browser_session_id="browser-a")

    advance(31)
    second = store.acquire("task-1", mode="professional", browser_session_id="browser-b")

    assert second["version"] == first["version"] + 1
    assert second["browser_session_id"] == "browser-b"
