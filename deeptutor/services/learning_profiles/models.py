from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

GrantMode = Literal["student", "teacher_view", "impersonate"]


@dataclass(frozen=True, slots=True)
class LearningProfile:
    id: str
    owner_user_id: str
    name: str
    avatar: str
    created_at: str
    updated_at: str
    pin_hash: str
    failed_attempts: int = 0
    locked_until: str = ""
    disabled: bool = False
    data_version: int = 1

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("pin_hash", None)
        return data


@dataclass(frozen=True, slots=True)
class ProfileGrant:
    id_hash: str
    owner_user_id: str
    profile_id: str
    mode: GrantMode
    created_at: str
    last_activity_at: str
    absolute_expires_at: str
    revoked_at: str = ""
    actor_user_id: str = ""
    scopes: tuple[str, ...] = ()
    reason: str = ""
    impersonation_id: str = ""


@dataclass(frozen=True, slots=True)
class ProfileAccessContext:
    owner_user_id: str
    profile_id: str
    mode: GrantMode
    actor_user_id: str
    read_only: bool
    scopes: tuple[str, ...] = ()
    reason: str = ""
    impersonation_id: str = ""


@dataclass(frozen=True, slots=True)
class ProfileAuditEvent:
    timestamp: str
    event: str
    owner_user_id: str
    profile_id: str = ""
    actor_user_id: str = ""
    mode: str = ""
    outcome: str = "success"
    metadata: dict[str, Any] | None = None
