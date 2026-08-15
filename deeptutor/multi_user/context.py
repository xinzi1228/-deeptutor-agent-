"""Request-local current user context."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

from deeptutor.services.learning_profiles.models import ProfileAccessContext

from .models import CurrentUser
from .paths import local_admin_user, scope_for_user

_current_user: ContextVar[CurrentUser | None] = ContextVar("deeptutor_current_user", default=None)
_current_learning_profile: ContextVar[ProfileAccessContext | None] = ContextVar(
    "deeptutor_current_learning_profile", default=None
)


def set_current_user(user: CurrentUser) -> Token[CurrentUser | None]:
    return _current_user.set(user)


def reset_current_user(token: Token[CurrentUser | None]) -> None:
    _current_user.reset(token)


def get_current_user() -> CurrentUser:
    return _current_user.get() or local_admin_user()


def get_current_user_or_none() -> CurrentUser | None:
    return _current_user.get()


def set_current_learning_profile(
    profile: ProfileAccessContext | None,
) -> Token[ProfileAccessContext | None]:
    return _current_learning_profile.set(profile)


def reset_current_learning_profile(token: Token[ProfileAccessContext | None]) -> None:
    _current_learning_profile.reset(token)


def get_current_learning_profile() -> ProfileAccessContext | None:
    return _current_learning_profile.get()


def require_learning_profile_access() -> ProfileAccessContext:
    profile = get_current_learning_profile()
    if profile is None:
        raise PermissionError("请先解锁学习档案")
    return profile


def require_learning_profile_write_access() -> ProfileAccessContext:
    """Return the active profile context only when it permits private-data writes."""
    profile = require_learning_profile_access()
    if profile.read_only:
        raise PermissionError("当前为教师只读视角，不能修改学生学习数据")
    return profile


def authorize_learning_profile_mutation(
    *, operation: str, path: str = ""
) -> ProfileAccessContext | None:
    """Protect profile-private mutations and audit managed writes.

    Account-level routes may be used before a learning profile is unlocked, so
    the absence of a profile is not an error here.  When a profile context is
    active, teacher-view grants are strictly read-only.  Impersonated writes
    are recorded without request bodies or other potentially sensitive data.
    """
    profile = get_current_learning_profile()
    if profile is None:
        return None
    lowered = path.lower()
    if "/workspace/inbox/" in lowered and lowered.endswith("/organize"):
        policy_operation = "inbox.organize"
    elif "/workspace/inbox" in lowered:
        policy_operation = "inbox.capture"
    elif "/extensions/" in lowered:
        policy_operation = "extension.preference"
    elif "/chat" in lowered or "/ws" in lowered:
        policy_operation = "chat.send"
    elif "/memory" in lowered:
        policy_operation = "memory.write"
    elif "/sessions" in lowered:
        policy_operation = "session.mutate"
    elif "/annotation" in lowered or "/label-studio" in lowered:
        policy_operation = "annotation.submit"
    elif "." in operation:
        policy_operation = operation
    else:
        policy_operation = "current_task.mutate"

    from deeptutor.services.authorization.policy import authorize_profile_operation

    authorize_profile_operation(
        policy_operation,
        target_profile_id=profile.profile_id,
        resource_type="request",
        resource_id=str(path)[:240],
    )
    return profile


def user_from_token_payload(payload: Any | None) -> CurrentUser:
    if payload is None:
        return local_admin_user()
    user_id = str(getattr(payload, "user_id", "") or "")
    username = str(getattr(payload, "username", "") or "local")
    role = str(getattr(payload, "role", "user") or "user")
    if role not in {"admin", "user"}:
        role = "user"
    if not user_id:
        user_id = "local-admin" if role == "admin" and username == "local" else username
    return CurrentUser(
        id=user_id,
        username=username,
        role=role,  # type: ignore[arg-type]
        scope=scope_for_user(user_id, is_admin=role == "admin"),
    )
