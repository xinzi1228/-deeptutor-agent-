from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

TaskPhase = Literal["assigned", "diagnosing", "theory", "practice", "review", "paused", "completed"]
TaskMode = Literal["learning", "teaching_annotation", "professional_annotation"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StartTaskCommand(BaseModel):
    course_id: str = Field(min_length=1, max_length=160)
    task_id: str = Field(min_length=1, max_length=160)
    phase: TaskPhase = "assigned"
    mode: TaskMode = "learning"
    course_version: str = ""
    task_version: str = ""
    scoring_version: str = ""


class CurrentLearningTask(StartTaskCommand):
    profile_id: str
    draft_ref: str = ""
    latest_submission_ref: str = ""
    coach_session_id: str = ""
    started_at: str
    phase_started_at: str
    elapsed_seconds: int = 0
    version: int = 1
    updated_at: str
    schema_version: int = 1


class CurrentTaskEvent(BaseModel):
    id: str
    event_type: str
    profile_id: str
    course_id: str
    task_id: str
    phase: TaskPhase
    version: int
    references: dict[str, str] = Field(default_factory=dict)
    created_at: str
    schema_version: int = 1


__all__ = ["CurrentLearningTask", "CurrentTaskEvent", "StartTaskCommand", "TaskPhase", "utc_now"]
