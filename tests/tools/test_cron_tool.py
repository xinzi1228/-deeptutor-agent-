"""Cron tool — schedule/list/cancel timed tasks for a conversation."""

from __future__ import annotations

import time
import uuid

import pytest

from deeptutor.services.cron import CronJob, CronOwner, CronSchedule
from deeptutor.tools.cron_tool import run_cron_action


class _FakeCronService:
    """In-memory cron service stand-in."""

    def __init__(self) -> None:
        self.jobs: dict[str, CronJob] = {}

    def list_jobs(self, owner_key: str | None = None) -> list[CronJob]:
        jobs = list(self.jobs.values())
        if owner_key is not None:
            jobs = [j for j in jobs if j.owner.key == owner_key]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or 0)

    def add_job(self, **kwargs) -> CronJob:
        job = CronJob(
            id=uuid.uuid4().hex[:10],
            name=kwargs.get("name") or "",
            message=kwargs.get("message") or "",
            schedule=kwargs.get("schedule") or CronSchedule(kind="every", every_seconds=60),
            owner=kwargs.get("owner") or CronOwner(kind="chat"),
        )
        job.state.next_run_at_ms = int(time.time() * 1000) + 60_000
        self.jobs[job.id] = job
        return job

    def cancel_job(self, job_id: str, *, owner_key: str | None = None) -> bool:
        job = self.jobs.get(job_id)
        if job is None:
            return False
        if owner_key is not None and job.owner.key != owner_key:
            return False
        del self.jobs[job_id]
        return True


@pytest.fixture
def fake_service(monkeypatch):
    service = _FakeCronService()
    monkeypatch.setattr("deeptutor.tools.cron_tool.get_cron_service", lambda: service)
    return service


def _owner(**overrides) -> dict:
    base = {"kind": "chat", "session_id": "sess1", "user_id": "u1"}
    base.update(overrides)
    return base


def test_list_empty(fake_service):
    out = run_cron_action({"action": "list", "_cron_owner": _owner()})
    assert out.ok
    assert "No scheduled tasks" in out.text


def test_schedule_every_seconds(fake_service):
    out = run_cron_action({
        "action": "schedule",
        "_cron_owner": _owner(),
        "message": "该练标注了",
        "name": "学习提醒",
        "every_seconds": 30,
    })
    assert out.ok
    assert "Scheduled" in out.text
    assert len(fake_service.jobs) == 1
    job = list(fake_service.jobs.values())[0]
    assert job.message == "该练标注了"
    assert job.schedule.kind == "every"
    assert job.schedule.every_seconds == 30


def test_schedule_requires_message(fake_service):
    out = run_cron_action({"action": "schedule", "_cron_owner": _owner()})
    assert not out.ok
    assert "message" in out.text


def test_schedule_exactly_one_timing(fake_service):
    out = run_cron_action({
        "action": "schedule",
        "_cron_owner": _owner(),
        "message": "x",
        "at": "2026-06-12T09:00",
        "every_seconds": 30,
    })
    assert not out.ok
    assert "exactly one of" in out.text


def test_cancel_existing(fake_service):
    created = run_cron_action({
        "action": "schedule", "_cron_owner": _owner(),
        "message": "x", "every_seconds": 30,
    })
    assert created.ok
    job_id = created.meta["job_id"]
    out = run_cron_action({"action": "cancel", "_cron_owner": _owner(), "job_id": job_id})
    assert out.ok
    assert "cancelled" in out.text
    assert len(fake_service.jobs) == 0


def test_cancel_missing(fake_service):
    out = run_cron_action({"action": "cancel", "_cron_owner": _owner(), "job_id": "nope"})
    assert not out.ok


def test_no_owner_rejected():
    out = run_cron_action({"action": "list"})
    assert not out.ok
    assert "not available" in out.text


def test_schedule_blocked_inside_cron(fake_service):
    out = run_cron_action({
        "action": "schedule", "_cron_owner": _owner(),
        "message": "x", "every_seconds": 30, "_cron_in_context": True,
    })
    assert not out.ok
    assert "inside a running" in out.text
