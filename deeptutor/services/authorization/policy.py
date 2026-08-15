from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deeptutor.multi_user.context import get_current_learning_profile, get_current_user_or_none
from deeptutor.services.learning_profiles.models import ProfileAccessContext

from .impersonation import ImpersonationAuditWriter

STUDENT_ALLOWED = frozenset(
    {
        "chat.send",
        "memory.write",
        "annotation.draft",
        "annotation.submit",
        "learning_record.append",
        "inbox.capture",
        "inbox.organize",
        "visualization.mutate",
        "session.mutate",
        "current_task.mutate",
        "notebook.mutate",
        "question_notebook.mutate",
        "mastery_path.mutate",
        "extension.preference",
    }
)
IMPERSONATION_ALLOWED = frozenset(
    {"task.assign", "inbox.organize", "teacher_feedback.append", "reviewed_derived.correct"}
)
ORIGINAL_EVIDENCE = frozenset(
    {
        "chat.send",
        "memory.write",
        "annotation.draft",
        "annotation.submit",
        "learning_record.append",
        "initial_grade.overwrite",
        "audit.delete",
    }
)


class AuthorizationDenied(PermissionError):
    def __init__(self, message: str, *, code: str = "profile_write_forbidden") -> None:
        super().__init__(message)
        self.code = code
        self.status_code = 403


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    operation: str
    mode: str


class ProfileAuthorizationPolicy:
    def __init__(self, *, audit_writer: ImpersonationAuditWriter | None = None) -> None:
        self.audit_writer = audit_writer

    def authorize(
        self,
        access: ProfileAccessContext,
        *,
        operation: str,
        target_profile_id: str,
        resource_type: str = "",
        resource_id: str = "",
        request_id: str = "",
        before: Any = None,
        after: Any = None,
    ) -> AuthorizationDecision:
        error: AuthorizationDenied | None = None
        if target_profile_id != access.profile_id:
            error = AuthorizationDenied("不能操作当前授权范围之外的学习档案", code="profile_mismatch")
        elif access.mode == "teacher_view" or access.read_only:
            error = AuthorizationDenied(
                "当前为教师只读视角，不能修改学生学习数据", code="teacher_read_only"
            )
        elif access.mode == "student":
            if access.actor_user_id != access.owner_user_id:
                error = AuthorizationDenied("学生只能修改自己的学习档案", code="profile_owner_mismatch")
            elif operation not in STUDENT_ALLOWED:
                error = AuthorizationDenied("当前学生角色无权执行此操作", code="operation_forbidden")
        elif access.mode == "impersonate":
            if not access.reason.strip() or not access.impersonation_id:
                error = AuthorizationDenied("代管缺少原因或有效授权标识", code="invalid_impersonation")
            elif operation in ORIGINAL_EVIDENCE or operation not in IMPERSONATION_ALLOWED:
                error = AuthorizationDenied("教师代管不能修改学生原始学习证据", code="evidence_immutable")
            elif operation not in access.scopes:
                error = AuthorizationDenied("本次代管 scope 未授权该操作", code="scope_forbidden")
        else:
            error = AuthorizationDenied("未知的学习档案访问模式", code="invalid_access_mode")

        if access.mode == "impersonate" and self.audit_writer is not None:
            self.audit_writer.append(
                access=access,
                operation=operation,
                outcome="denied" if error else "success",
                resource_type=resource_type,
                resource_id=resource_id,
                request_id=request_id,
                before=before,
                after=after,
                error_code=error.code if error else "",
            )
        if error is not None:
            raise error
        return AuthorizationDecision(allowed=True, operation=operation, mode=access.mode)


def _audit_writer() -> ImpersonationAuditWriter | None:
    user = get_current_user_or_none()
    if user is None:
        return None
    return ImpersonationAuditWriter(Path(user.scope.root) / "learning_profiles" / "audit.jsonl")


def authorize_profile_operation(
    operation: str,
    *,
    target_profile_id: str = "",
    resource_type: str = "",
    resource_id: str = "",
    request_id: str = "",
    before: Any = None,
    after: Any = None,
) -> AuthorizationDecision:
    access = get_current_learning_profile()
    user = get_current_user_or_none()
    if access is None and user is None:
        return AuthorizationDecision(allowed=True, operation=operation, mode="system")
    if access is None:
        # Partner runtimes are synthetic, path-isolated users. They have no
        # learning profile and may only write their own dedicated memory tree.
        from deeptutor.services.partners.scope import is_partner_user_id

        if operation == "memory.write" and is_partner_user_id(user.id):
            return AuthorizationDecision(allowed=True, operation=operation, mode="partner")
        raise AuthorizationDenied("尚未选择学习档案", code="profile_required")
    return ProfileAuthorizationPolicy(audit_writer=_audit_writer()).authorize(
        access,
        operation=operation,
        target_profile_id=target_profile_id or access.profile_id,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        before=before,
        after=after,
    )
