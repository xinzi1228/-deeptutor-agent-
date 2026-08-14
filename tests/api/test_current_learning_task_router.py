from pathlib import Path

import pytest

from deeptutor.api.routers import current_learning_task as router
from deeptutor.services.current_learning_task.service import CurrentLearningTaskService
from deeptutor.services.current_learning_task.store import CurrentLearningTaskStore


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    instance = CurrentLearningTaskService(
        CurrentLearningTaskStore(tmp_path / "profile-a"),
        profile_id="profile-a",
        write_guard=lambda: None,
    )
    monkeypatch.setattr(router, "get_current_learning_task_service", lambda: instance)
    return instance


@pytest.mark.asyncio
async def test_current_task_router_round_trip(service):
    started = await router.start_task(
        router.StartTaskRequest(
            course_id="course-a",
            task_id="task-a",
            phase="assigned",
            expected_version=0,
            idempotency_key="start-a",
        )
    )
    transitioned = await router.transition_task(
        router.TransitionRequest(
            phase="practice",
            expected_version=started["task"]["version"],
            idempotency_key="transition-a",
        )
    )
    current = await router.get_current_task()

    assert transitioned["task"]["phase"] == "practice"
    assert current["task"]["profile_id"] == "profile-a"


@pytest.mark.asyncio
async def test_router_maps_stale_version_to_conflict(service):
    await router.start_task(
        router.StartTaskRequest(
            course_id="course-a",
            task_id="task-a",
            expected_version=0,
            idempotency_key="start-a",
        )
    )

    with pytest.raises(router.HTTPException) as exc:
        await router.transition_task(
            router.TransitionRequest(
                phase="practice",
                expected_version=0,
                idempotency_key="stale",
            )
        )
    assert exc.value.status_code == 409
