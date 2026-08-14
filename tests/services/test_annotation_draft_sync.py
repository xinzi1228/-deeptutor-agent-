from __future__ import annotations

from deeptutor.services.annotation_attempts import AnnotationAttemptStore


def test_pending_submission_is_profile_local_and_idempotent(tmp_path) -> None:
    first = AnnotationAttemptStore(tmp_path / "first")
    second = AnnotationAttemptStore(tmp_path / "second")

    queued, created = first.queue_submission(
        task_id="task-1",
        task_type="bbox",
        mode="teaching",
        payload={"predictions": [{"x": 1, "y": 2, "w": 10, "h": 10, "label": "车"}]},
        metrics={"f1": 1.0},
        report="本地检查通过",
        idempotency_key="browser:task-1:revision-1",
    )
    duplicate, duplicate_created = first.queue_submission(
        task_id="task-1",
        task_type="bbox",
        mode="teaching",
        payload={"predictions": []},
        metrics={},
        report="不能覆盖",
        idempotency_key="browser:task-1:revision-1",
    )

    assert created is True
    assert duplicate_created is False
    assert duplicate["id"] == queued["id"]
    assert second.list_pending_submissions() == []


def test_synced_submission_becomes_a_formal_revision(tmp_path) -> None:
    store = AnnotationAttemptStore(tmp_path)
    queued, _ = store.queue_submission(
        task_id="task-1",
        task_type="bbox",
        mode="teaching",
        payload={"predictions": []},
        metrics={"f1": 0.8},
        report="通过",
        idempotency_key="browser:task-1:revision-2",
    )

    synced = store.mark_submission_synced(
        queued["idempotency_key"],
        revision={"provider": "label_studio", "task_id": 11, "annotation_id": 22},
    )
    attempt, created = store.finalize_submission(queued["idempotency_key"])

    assert synced["sync_status"] == "synced"
    assert created is True
    assert attempt["sync_status"] == "synced"
    assert attempt["revision"]["annotation_id"] == 22
    assert store.list_pending_submissions() == []


def test_failed_submission_remains_retryable_without_final_attempt(tmp_path) -> None:
    store = AnnotationAttemptStore(tmp_path)
    queued, _ = store.queue_submission(
        task_id="task-1",
        task_type="bbox",
        mode="teaching",
        payload={"predictions": []},
        metrics={"f1": 0.5},
        report="仅本地检查",
        idempotency_key="browser:task-1:revision-3",
    )

    failed = store.mark_submission_retry(queued["idempotency_key"], "服务未启动")

    assert failed["sync_status"] == "retry_pending"
    assert failed["retry_count"] == 1
    assert store.list_attempts() == []
    assert store.list_pending_submissions()[0]["last_error"] == "服务未启动"
