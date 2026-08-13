from __future__ import annotations

from itertools import combinations

import pytest

from deeptutor.multi_user.context import (
    require_learning_profile_write_access,
    reset_current_learning_profile,
    set_current_learning_profile,
)
from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.label_studio_gateway import (
    LabelStudioAccessPolicy,
    LabelStudioProfileMap,
)
from deeptutor.services.learning_profiles.grants import ProfileGrantStore
from deeptutor.services.learning_profiles.store import LearningProfileStore


def test_two_accounts_four_profiles_never_share_private_state(tmp_path) -> None:
    fixtures = []
    for account_index, account_id in enumerate(("account-a", "account-b"), start=1):
        workspace = tmp_path / account_id / "workspace"
        profiles = LearningProfileStore(workspace)
        grants = ProfileGrantStore(workspace)
        for profile_index in (1, 2):
            profile = profiles.create(
                account_id,
                f"学生 {account_index}-{profile_index}",
                f"{account_index}{profile_index}34",
            )
            raw_grant, _ = grants.issue(account_id, profile.id)
            profile_root = profiles.profile_root(profile.id)
            marker = f"{account_id}/profile-{profile_index}"
            AnnotationAttemptStore(profile_root).append_attempt(
                task_id=f"task-{profile_index}",
                task_type="bbox",
                mode="teaching",
                payload={"marker": marker},
                metrics={"f1": profile_index / 10},
                report=marker,
                idempotency_key=f"matrix:{account_id}:{profile_index}",
            )
            mapping = LabelStudioProfileMap(
                profile_id=profile.id,
                email_alias=f"{profile.id}@example.invalid",
                project_id=account_index * 100 + profile_index,
                task_map={f"task-{profile_index}": account_index * 1000 + profile_index},
            )
            fixtures.append(
                {
                    "account": account_id,
                    "profile": profile,
                    "root": profile_root.resolve(),
                    "grant": raw_grant,
                    "grants": grants,
                    "marker": marker,
                    "mapping": mapping,
                }
            )

    assert len({item["root"] for item in fixtures}) == 4
    assert len({item["profile"].id for item in fixtures}) == 4

    for item in fixtures:
        attempts = AnnotationAttemptStore(item["root"]).list_attempts()
        assert [attempt["payload"]["marker"] for attempt in attempts] == [item["marker"]]
        assert item["grants"].validate(item["grant"], item["account"]) is not None
        other_account = "account-b" if item["account"] == "account-a" else "account-a"
        assert item["grants"].validate(item["grant"], other_account) is None
        assert "pin_hash" not in item["profile"].public_dict()

    for left, right in combinations(fixtures, 2):
        left_policy = LabelStudioAccessPolicy(left["mapping"])
        right_project = right["mapping"].project_id
        right_task = next(iter(right["mapping"].task_map.values()))
        assert not left_policy.allows("GET", f"/projects/{right_project}/data", f"task={right_task}")
        assert not left_policy.allows("GET", f"/api/tasks/{right_task}")
        assert left["marker"] not in str(AnnotationAttemptStore(right["root"]).list_attempts())


def test_teacher_grant_cannot_be_used_as_student_write_grant(tmp_path) -> None:
    workspace = tmp_path / "account" / "workspace"
    profile = LearningProfileStore(workspace).create("teacher-owner", "学生", "1234")
    grants = ProfileGrantStore(workspace)
    raw, _ = grants.issue("teacher-owner", profile.id, mode="teacher_view", actor_user_id="teacher")
    access = grants.validate(raw, "teacher-owner")
    assert access is not None
    assert access.read_only is True
    assert access.mode == "teacher_view"
    token = set_current_learning_profile(access)
    try:
        with pytest.raises(PermissionError, match="教师只读视角"):
            require_learning_profile_write_access()
    finally:
        reset_current_learning_profile(token)
