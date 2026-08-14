from pathlib import Path

import pytest

from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.coach_context.service import build_annotation_coach_context
from deeptutor.services.current_learning_task.models import StartTaskCommand
from deeptutor.services.current_learning_task.service import CurrentLearningTaskService
from deeptutor.services.current_learning_task.store import CurrentLearningTaskStore


def _service(tmp_path: Path, *, writable: bool = True) -> CurrentLearningTaskService:
    def guard() -> None:
        if not writable:
            raise PermissionError("read only")

    return CurrentLearningTaskService(
        CurrentLearningTaskStore(tmp_path / "profile-a"),
        profile_id="profile-a",
        write_guard=guard,
    )


def test_switch_task_clears_incompatible_context_and_increments_version(tmp_path: Path):
    service = _service(tmp_path)
    first, created = service.start(
        StartTaskCommand(course_id="course-a", task_id="task-a", phase="practice"),
        expected_version=0,
        idempotency_key="start-a",
    )
    updated, _ = service.patch_context(
        draft_ref="draft-a",
        latest_submission_ref="attempt-a",
        coach_session_id="coach-a",
        expected_version=first.version,
        idempotency_key="context-a",
    )

    switched, switched_created = service.start(
        StartTaskCommand(course_id="course-a", task_id="task-b", phase="assigned"),
        expected_version=updated.version,
        idempotency_key="start-b",
    )

    assert created is True and switched_created is True
    assert switched.task_id == "task-b"
    assert switched.draft_ref == ""
    assert switched.latest_submission_ref == ""
    assert switched.coach_session_id == ""
    assert switched.version == updated.version + 1


def test_transition_rejects_model_invented_stage_and_version_conflict(tmp_path: Path):
    service = _service(tmp_path)
    task, _ = service.start(
        StartTaskCommand(course_id="course-a", task_id="task-a", phase="assigned"),
        expected_version=0,
        idempotency_key="start",
    )

    with pytest.raises(ValueError):
        service.transition(
            "published",
            expected_version=task.version,
            idempotency_key="bad-phase",
        )
    with pytest.raises(RuntimeError):
        service.transition("practice", expected_version=0, idempotency_key="stale")


def test_idempotency_returns_same_result_without_duplicate_event(tmp_path: Path):
    service = _service(tmp_path)
    command = StartTaskCommand(course_id="course-a", task_id="task-a", phase="assigned")

    first, first_created = service.start(command, expected_version=0, idempotency_key="same")
    replay, replay_created = service.start(command, expected_version=0, idempotency_key="same")

    assert first_created is True
    assert replay_created is False
    assert replay.version == first.version
    assert len(service.store.list_events()) == 1


def test_read_only_guard_blocks_every_mutation(tmp_path: Path):
    service = _service(tmp_path, writable=False)

    with pytest.raises(PermissionError):
        service.start(
            StartTaskCommand(course_id="course-a", task_id="task-a"),
            expected_version=0,
            idempotency_key="blocked",
        )


def test_annotation_store_emits_references_without_copying_payload(tmp_path: Path):
    observed = []
    store = AnnotationAttemptStore(
        tmp_path / "profile-a",
        task_observer=lambda event, task, reference: observed.append((event, task, reference)),
    )

    store.save_draft("task-a", "teaching", {"private_boxes": [1, 2, 3]})

    assert observed == [("draft_saved", "task-a", "annotation/drafts/task-a.json")]
    assert "private_boxes" not in observed[0][2]


def test_coach_context_prefers_unified_current_task(tmp_path: Path):
    profile_root = tmp_path / "profile-a"
    service = CurrentLearningTaskService(
        CurrentLearningTaskStore(profile_root),
        profile_id="profile-a",
        write_guard=lambda: None,
    )
    service.start(
        StartTaskCommand(course_id="course-a", task_id="task-a", phase="practice"),
        expected_version=0,
        idempotency_key="start",
    )

    context = build_annotation_coach_context(profile_root)

    assert context["current"]["task_id"] == "task-a"
    assert context["current"]["phase"] == "practice"
