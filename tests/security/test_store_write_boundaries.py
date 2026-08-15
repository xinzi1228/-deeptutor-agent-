from __future__ import annotations

import asyncio
import json

import pytest

from deeptutor.multi_user.context import (
    reset_current_learning_profile,
    reset_current_user,
    set_current_learning_profile,
    set_current_user,
)
from deeptutor.multi_user.models import CurrentUser, UserScope
from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.learning_profiles.models import ProfileAccessContext
from deeptutor.services.learning_workspace import LearningWorkspaceService
from deeptutor.services.memory.store import MemoryStore
from deeptutor.services.visualization_artifacts import VisualizationArtifactStore

PROFILE_ID = "lp_1234567890abcdef12345678"


def _access(mode: str) -> ProfileAccessContext:
    return ProfileAccessContext(
        owner_user_id="owner",
        profile_id=PROFILE_ID,
        mode=mode,
        actor_user_id="teacher" if mode != "student" else "owner",
        read_only=mode == "teacher_view",
        scopes=("task.assign",) if mode == "impersonate" else (),
        reason="课堂辅导" if mode == "impersonate" else "",
        impersonation_id="imp_test" if mode == "impersonate" else "",
    )


@pytest.mark.parametrize("mode", ["teacher_view", "impersonate"])
def test_annotation_store_rejects_non_student_raw_evidence_writes(tmp_path, mode: str) -> None:
    token = set_current_learning_profile(_access(mode))
    try:
        with pytest.raises(PermissionError):
            AnnotationAttemptStore(tmp_path).save_draft("task-1", "teaching", {"boxes": []})
    finally:
        reset_current_learning_profile(token)


def test_visualization_store_rejects_teacher_view_even_without_router(tmp_path) -> None:
    token = set_current_learning_profile(_access("teacher_view"))
    try:
        with pytest.raises(PermissionError):
            VisualizationArtifactStore(tmp_path).delete("viz_" + "a" * 32)
    finally:
        reset_current_learning_profile(token)


def test_memory_store_rejects_teacher_view_even_without_router() -> None:
    token = set_current_learning_profile(_access("teacher_view"))
    try:
        with pytest.raises(PermissionError):
            asyncio.run(MemoryStore().overwrite_doc("L3", "preferences", "private"))
    finally:
        reset_current_learning_profile(token)


def test_student_can_write_annotation_through_store_boundary(tmp_path) -> None:
    token = set_current_learning_profile(_access("student"))
    try:
        result = AnnotationAttemptStore(tmp_path).save_draft("task-1", "teaching", {"boxes": []})
    finally:
        reset_current_learning_profile(token)
    assert result["task_id"] == "task-1"


def test_impersonated_inbox_organize_is_scoped_and_audited(tmp_path) -> None:
    service = LearningWorkspaceService(root=tmp_path / "learning")
    service.root.mkdir(parents=True)
    item = {"id": "inbox_1", "status": "open", "raw_text": "我不懂遮挡"}
    service.inbox_file.write_text(json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8")
    access = ProfileAccessContext(
        owner_user_id="owner",
        profile_id=PROFILE_ID,
        mode="impersonate",
        actor_user_id="teacher",
        read_only=False,
        scopes=("inbox.organize",),
        reason="课堂辅导",
        impersonation_id="imp_inbox",
    )
    user = CurrentUser(
        id="teacher",
        username="teacher",
        role="admin",
        scope=UserScope(kind="admin", user_id="teacher", root=tmp_path),
    )
    user_token = set_current_user(user)
    profile_token = set_current_learning_profile(access)
    try:
        organized = service.organize_inbox("inbox_1", resolved_to=["knowledge:occlusion"])
    finally:
        reset_current_learning_profile(profile_token)
        reset_current_user(user_token)

    assert organized["status"] == "organized"
    audit = tmp_path / "learning_profiles" / "audit.jsonl"
    raw = audit.read_text(encoding="utf-8")
    assert '"operation":"inbox.organize"' in raw
    assert "我不懂遮挡" not in raw
