from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.multi_user.context import (
    reset_current_learning_profile,
    reset_current_user,
    set_current_learning_profile,
    set_current_user,
)
from deeptutor.multi_user.models import CurrentUser, UserScope
from deeptutor.services.authorization.policy import (
    AuthorizationDenied,
    authorize_profile_operation,
)
from deeptutor.services.learning_profiles.models import ProfileAccessContext

PROFILE_ID = "lp_1234567890abcdef12345678"


def _user(tmp_path: Path, *, role: str = "user") -> CurrentUser:
    return CurrentUser(
        id="teacher-1" if role == "admin" else "student-1",
        username="tester",
        role=role,
        scope=UserScope(kind="admin" if role == "admin" else "user", user_id="tester", root=tmp_path),
    )


def _access(mode: str, *, scopes: tuple[str, ...] = ()) -> ProfileAccessContext:
    return ProfileAccessContext(
        owner_user_id="student-1",
        profile_id=PROFILE_ID,
        mode=mode,
        actor_user_id="teacher-1" if mode != "student" else "student-1",
        read_only=mode == "teacher_view",
        scopes=scopes,
        reason="课堂辅导" if mode == "impersonate" else "",
        impersonation_id="imp_test" if mode == "impersonate" else "",
    )


def _authorize(tmp_path: Path, access: ProfileAccessContext, operation: str) -> None:
    user_token = set_current_user(_user(tmp_path, role="admin" if access.mode != "student" else "user"))
    profile_token = set_current_learning_profile(access)
    try:
        authorize_profile_operation(
            operation,
            target_profile_id=PROFILE_ID,
            resource_type="test-resource",
            resource_id="resource-1",
            request_id=f"request-{operation}",
        )
    finally:
        reset_current_learning_profile(profile_token)
        reset_current_user(user_token)


@pytest.mark.parametrize(
    "operation",
    [
        "chat.send",
        "memory.write",
        "annotation.draft",
        "annotation.submit",
        "learning_record.append",
        "inbox.capture",
        "inbox.organize",
        "visualization.mutate",
    ],
)
def test_student_can_only_mutate_own_learning_workflow(tmp_path: Path, operation: str) -> None:
    _authorize(tmp_path, _access("student"), operation)


@pytest.mark.parametrize(
    "operation",
    ["task.assign", "teacher_feedback.append", "reviewed_derived.correct", "initial_grade.overwrite"],
)
def test_student_cannot_perform_staff_operations(tmp_path: Path, operation: str) -> None:
    with pytest.raises(AuthorizationDenied):
        _authorize(tmp_path, _access("student"), operation)


@pytest.mark.parametrize(
    "operation",
    ["chat.send", "memory.write", "annotation.submit", "inbox.organize", "task.assign"],
)
def test_teacher_view_is_read_only_across_every_write(tmp_path: Path, operation: str) -> None:
    with pytest.raises(AuthorizationDenied, match="教师只读"):
        _authorize(tmp_path, _access("teacher_view"), operation)


@pytest.mark.parametrize(
    "operation",
    ["task.assign", "inbox.organize", "teacher_feedback.append", "reviewed_derived.correct"],
)
def test_impersonation_allows_only_explicit_assistance_scopes(
    tmp_path: Path, operation: str
) -> None:
    _authorize(tmp_path, _access("impersonate", scopes=(operation,)), operation)


@pytest.mark.parametrize(
    "operation",
    [
        "chat.send",
        "memory.write",
        "annotation.draft",
        "annotation.submit",
        "learning_record.append",
        "initial_grade.overwrite",
        "audit.delete",
    ],
)
def test_impersonation_never_mutates_original_evidence(tmp_path: Path, operation: str) -> None:
    with pytest.raises(AuthorizationDenied):
        _authorize(tmp_path, _access("impersonate", scopes=(operation,)), operation)


def test_scope_and_target_profile_are_both_enforced(tmp_path: Path) -> None:
    access = _access("impersonate", scopes=("task.assign",))
    user_token = set_current_user(_user(tmp_path, role="admin"))
    profile_token = set_current_learning_profile(access)
    try:
        with pytest.raises(AuthorizationDenied, match="scope"):
            authorize_profile_operation("inbox.organize", target_profile_id=PROFILE_ID)
        with pytest.raises(AuthorizationDenied, match="档案"):
            authorize_profile_operation("task.assign", target_profile_id="lp_other")
    finally:
        reset_current_learning_profile(profile_token)
        reset_current_user(user_token)


def test_regular_user_without_profile_cannot_write_memory(tmp_path: Path) -> None:
    token = set_current_user(_user(tmp_path))
    try:
        with pytest.raises(AuthorizationDenied, match="学习档案"):
            authorize_profile_operation("memory.write")
    finally:
        reset_current_user(token)


def test_synthetic_partner_without_profile_can_only_write_own_memory(tmp_path: Path) -> None:
    partner = CurrentUser(
        id="partner_coach",
        username="coach",
        role="user",
        scope=UserScope(kind="user", user_id="partner_coach", root=tmp_path),
    )
    token = set_current_user(partner)
    try:
        decision = authorize_profile_operation("memory.write")
        assert decision.mode == "partner"
        with pytest.raises(AuthorizationDenied):
            authorize_profile_operation("annotation.submit")
    finally:
        reset_current_user(token)
