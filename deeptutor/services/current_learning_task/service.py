from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from .models import CurrentLearningTask, CurrentTaskEvent, StartTaskCommand, TaskPhase, utc_now
from .store import CurrentLearningTaskStore

_TRANSITIONS: dict[str, set[str]] = {
    "assigned": {"diagnosing", "theory", "practice", "paused"},
    "diagnosing": {"theory", "practice", "paused"},
    "theory": {"theory", "practice", "paused", "completed"},
    "practice": {"practice", "review", "paused"},
    "review": {"practice", "completed", "paused"},
    "paused": {"diagnosing", "theory", "practice"},
    "completed": set(),
}


class CurrentLearningTaskService:
    def __init__(
        self,
        store: CurrentLearningTaskStore,
        *,
        profile_id: str,
        write_guard: Callable[[], None],
    ):
        self.store = store
        self.profile_id = profile_id
        self.write_guard = write_guard

    def get(self) -> CurrentLearningTask | None:
        return self.store.get()

    def start(
        self,
        command: StartTaskCommand,
        *,
        expected_version: int,
        idempotency_key: str,
    ) -> tuple[CurrentLearningTask, bool]:
        self.write_guard()
        key = self._key(idempotency_key)
        replay = self.store.replay(key)
        if replay:
            return replay, False
        current = self.store.get()
        self._expect(current, expected_version)
        now = utc_now()
        version = (current.version + 1) if current else 1
        task = CurrentLearningTask(
            **command.model_dump(),
            profile_id=self.profile_id,
            started_at=now,
            phase_started_at=now,
            updated_at=now,
            version=version,
        )
        return self._commit(task, key, "task_started"), True

    def transition(
        self,
        phase: TaskPhase | str,
        *,
        expected_version: int,
        idempotency_key: str,
    ) -> tuple[CurrentLearningTask, bool]:
        self.write_guard()
        key = self._key(idempotency_key)
        replay = self.store.replay(key)
        if replay:
            return replay, False
        current = self._required()
        self._expect(current, expected_version)
        if phase not in _TRANSITIONS.get(current.phase, set()):
            raise ValueError(f"不允许从 {current.phase} 跳转到 {phase}")
        now = utc_now()
        updated = current.model_copy(
            update={"phase": phase, "phase_started_at": now, "updated_at": now, "version": current.version + 1}
        )
        return self._commit(updated, key, "phase_changed"), True

    def patch_context(
        self,
        *,
        draft_ref: str | None = None,
        latest_submission_ref: str | None = None,
        coach_session_id: str | None = None,
        expected_version: int,
        idempotency_key: str,
    ) -> tuple[CurrentLearningTask, bool]:
        self.write_guard()
        key = self._key(idempotency_key)
        replay = self.store.replay(key)
        if replay:
            return replay, False
        current = self._required()
        self._expect(current, expected_version)
        update = {"updated_at": utc_now(), "version": current.version + 1}
        for field, value in {
            "draft_ref": draft_ref,
            "latest_submission_ref": latest_submission_ref,
            "coach_session_id": coach_session_id,
        }.items():
            if value is not None:
                update[field] = str(value)[:200]
        return self._commit(current.model_copy(update=update), key, "context_updated"), True

    def _commit(self, task: CurrentLearningTask, key: str, event_type: str) -> CurrentLearningTask:
        with self.store._lock:
            self.store.save(task)
            self.store.append_event(
                CurrentTaskEvent(
                    id=f"task_event_{uuid4().hex}",
                    event_type=event_type,
                    profile_id=task.profile_id,
                    course_id=task.course_id,
                    task_id=task.task_id,
                    phase=task.phase,
                    version=task.version,
                    references={
                        "draft_ref": task.draft_ref,
                        "latest_submission_ref": task.latest_submission_ref,
                        "coach_session_id": task.coach_session_id,
                    },
                    created_at=utc_now(),
                )
            )
            self.store.remember(key, task)
        return task

    @staticmethod
    def _key(value: str) -> str:
        clean = str(value or "").strip()[:160]
        if not clean:
            raise ValueError("缺少幂等键")
        return clean

    @staticmethod
    def _expect(current: CurrentLearningTask | None, expected: int) -> None:
        actual = current.version if current else 0
        if expected != actual:
            raise RuntimeError(f"任务版本冲突：期望 {expected}，实际 {actual}")

    def _required(self) -> CurrentLearningTask:
        current = self.store.get()
        if current is None:
            raise FileNotFoundError("当前没有学习任务")
        return current


def get_current_learning_task_service() -> CurrentLearningTaskService:
    from deeptutor.multi_user.context import (
        authorize_learning_profile_mutation,
        get_current_learning_profile,
    )
    from deeptutor.multi_user.paths import get_current_learning_profile_root

    access = get_current_learning_profile()
    if access is None:
        raise PermissionError("请先解锁学习档案")
    root = get_current_learning_profile_root()
    assert root is not None
    return CurrentLearningTaskService(
        CurrentLearningTaskStore(root),
        profile_id=access.profile_id,
        write_guard=lambda: authorize_learning_profile_mutation(operation="current_learning_task"),
    )


__all__ = ["CurrentLearningTaskService", "get_current_learning_task_service"]
