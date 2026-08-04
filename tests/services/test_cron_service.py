"""CronService — job store + scheduler."""

from __future__ import annotations

from deeptutor.services.cron import CronOwner, CronSchedule, CronService


def _service(tmp_path) -> CronService:
    return CronService(store_path=tmp_path / "jobs.json")


def test_set_job_enabled_toggles_persisted(tmp_path):
    s = _service(tmp_path)
    job = s.add_job(
        name="r",
        message="提醒练标注",
        schedule=CronSchedule(kind="every", every_seconds=30),
        owner=CronOwner(kind="chat", session_id="s1"),
    )
    assert job.enabled is True
    assert s.set_job_enabled(job.id, False) is True
    # persisted + re-read from a fresh service instance
    s2 = _service(tmp_path)
    assert s2.get_job(job.id).enabled is False
    assert s2.set_job_enabled(job.id, True) is True
    assert s2.get_job(job.id).enabled is True


def test_set_job_enabled_missing_or_wrong_owner(tmp_path):
    s = _service(tmp_path)
    assert s.set_job_enabled("nope", False) is False
    job = s.add_job(
        name="r",
        message="x",
        schedule=CronSchedule(kind="every", every_seconds=30),
        owner=CronOwner(kind="chat", session_id="s1", user_id="u1"),
    )
    # wrong owner key
    assert s.set_job_enabled(job.id, False, owner_key="chat:other") is False
    assert s.set_job_enabled(job.id, False, owner_key="chat:u1") is True
