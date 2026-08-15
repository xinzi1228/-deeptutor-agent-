from __future__ import annotations

import json
from pathlib import Path

import pytest

from deeptutor.services.authorization.impersonation import ImpersonationAuditWriter
from deeptutor.services.authorization.policy import AuthorizationDenied, ProfileAuthorizationPolicy
from deeptutor.services.learning_profiles.models import ProfileAccessContext


def _access() -> ProfileAccessContext:
    return ProfileAccessContext(
        owner_user_id="student-1",
        profile_id="lp_1234567890abcdef12345678",
        mode="impersonate",
        actor_user_id="teacher-1",
        read_only=False,
        scopes=("task.assign", "teacher_feedback.append"),
        reason="课堂辅导",
        impersonation_id="imp_123",
    )


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_each_impersonated_write_is_audited_without_sensitive_body(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    policy = ProfileAuthorizationPolicy(audit_writer=ImpersonationAuditWriter(path))

    policy.authorize(
        _access(),
        operation="task.assign",
        target_profile_id=_access().profile_id,
        resource_type="learning_task",
        resource_id="task-1",
        request_id="req-1",
        before={"title": "旧任务", "private_text": "不应写入"},
        after={"title": "新任务", "private_text": "也不应写入"},
    )

    row = _rows(path)[0]
    assert row["event"] == "impersonated_mutation"
    assert row["metadata"]["request_id"] == "req-1"
    assert row["metadata"]["operation"] == "task.assign"
    assert row["metadata"]["reason"] == "课堂辅导"
    assert len(row["metadata"]["before_sha256"]) == 64
    assert len(row["metadata"]["after_sha256"]) == 64
    assert "private_text" not in path.read_text(encoding="utf-8")
    assert "不应写入" not in path.read_text(encoding="utf-8")


def test_retry_with_same_request_id_does_not_duplicate_audit(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    policy = ProfileAuthorizationPolicy(audit_writer=ImpersonationAuditWriter(path))
    kwargs = {
        "operation": "teacher_feedback.append",
        "target_profile_id": _access().profile_id,
        "resource_type": "feedback",
        "resource_id": "feedback-1",
        "request_id": "req-retry",
        "after": {"summary": "建议复习遮挡"},
    }

    policy.authorize(_access(), **kwargs)
    policy.authorize(_access(), **kwargs)

    assert len(_rows(path)) == 1


def test_denied_impersonation_is_also_audited(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    policy = ProfileAuthorizationPolicy(audit_writer=ImpersonationAuditWriter(path))

    with pytest.raises(AuthorizationDenied):
        policy.authorize(
            _access(),
            operation="annotation.submit",
            target_profile_id=_access().profile_id,
            resource_type="annotation",
            resource_id="attempt-1",
            request_id="req-denied",
        )

    row = _rows(path)[0]
    assert row["outcome"] == "denied"
    assert row["metadata"]["operation"] == "annotation.submit"
