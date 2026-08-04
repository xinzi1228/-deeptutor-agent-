"""cron REST router — list/delete/toggle timed tasks."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_jobs_empty():
    from deeptutor.api.routers.cron import list_jobs

    result = await list_jobs()
    assert "jobs" in result
    assert isinstance(result["jobs"], list)


@pytest.mark.asyncio
async def test_toggle_and_delete_job():
    from deeptutor.api.routers.cron import JobToggleRequest, delete_job, list_jobs, toggle_job
    from deeptutor.services.cron import CronOwner, CronSchedule, get_cron_service

    service = get_cron_service()
    job = service.add_job(
        name="r",
        message="x",
        schedule=CronSchedule(kind="every", every_seconds=30),
        owner=CronOwner(kind="chat", session_id="s1"),
    )
    try:
        jobs = await list_jobs()
        assert any(j["id"] == job.id for j in jobs["jobs"])
        toggled = await toggle_job(job.id, JobToggleRequest(enabled=False))
        assert toggled["ok"] is True
        assert toggled["enabled"] is False
        deleted = await delete_job(job.id)
        assert deleted["ok"] is True
    finally:
        service.cancel_job(job.id)
