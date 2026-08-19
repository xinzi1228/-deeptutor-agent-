from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from deeptutor.api.routers.auth import TokenPayload, require_admin, require_auth
from deeptutor.multi_user.context import get_current_learning_profile, get_current_user
from deeptutor.multi_user.paths import get_current_path_service
from deeptutor.services.learning_profiles.audit import append_audit_event
from deeptutor.services.learning_profiles.grants import ProfileGrantStore
from deeptutor.services.learning_profiles.models import ProfileAuditEvent
from deeptutor.services.learning_profiles.store import LearningProfileStore, ProfileLockedError

router = APIRouter()

COOKIE_NAME = "dt_learning_profile"
COOKIE_MAX_AGE = 12 * 3600
TEACHER_COOKIE_MAX_AGE = 30 * 60


def _cookie_attrs() -> dict:
    from deeptutor.api.routers.auth import _SAMESITE, _SECURE
    return {"key": COOKIE_NAME, "httponly": True, "samesite": _SAMESITE, "secure": _SECURE, "path": "/"}


def _stores() -> tuple[LearningProfileStore, ProfileGrantStore]:
    workspace = get_current_path_service().get_workspace_dir()
    return LearningProfileStore(workspace), ProfileGrantStore(workspace)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(store: LearningProfileStore, event: str, profile_id: str = "", *, outcome: str = "success", mode: str = "", metadata: dict | None = None) -> None:
    user = get_current_user()
    append_audit_event(store.audit_file, ProfileAuditEvent(timestamp=_timestamp(), event=event, owner_user_id=user.id, profile_id=profile_id, actor_user_id=user.id, mode=mode, outcome=outcome, metadata=metadata))


class CreateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    pin: str
    avatar: str = ""


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    avatar: str | None = None
    disabled: bool | None = None


class UnlockRequest(BaseModel):
    pin: str


class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str


class ResetPinRequest(BaseModel):
    new_pin: str


class ImpersonateRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=200)
    scopes: list[str] = Field(min_length=1, max_length=4)


@router.get("")
async def list_profiles(_: TokenPayload | None = Depends(require_auth)) -> dict:
    store, _ = _stores()
    user = get_current_user()
    active = get_current_learning_profile()
    return {"profiles": [item.public_dict() for item in store.list(user.id)], "active_profile_id": active.profile_id if active else None}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_profile(body: CreateProfileRequest, _: TokenPayload | None = Depends(require_auth)) -> dict:
    store, _ = _stores()
    user = get_current_user()
    try:
        profile = store.create(user.id, body.name, body.pin, body.avatar)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # 仅当该账号还没有任何档案（创建的是第一个档案）时，把档案功能引入前的账号级旧数据迁移进它；
    # 后续创建的新档案从空白开始，不复制账号级旧数据。
    existing = store.list(user.id)
    if len(existing) == 1:  # 刚创建的这个是第一个
        from deeptutor.services.learning_profiles.migration import LearningProfileMigrator

        migration = LearningProfileMigrator(store.root.parent).migrate(profile.id)
        migration_status = migration["status"]
    else:
        migration_status = "skipped_not_first_profile"
    _audit(store, "profile_created", profile.id, metadata={"migration_status": migration_status})
    return {**profile.public_dict(), "legacy_migration": {"status": migration_status, "source_preserved": True}}


@router.patch("/{profile_id}")
async def update_profile(profile_id: str, body: UpdateProfileRequest, _: TokenPayload | None = Depends(require_auth)) -> dict:
    store, _ = _stores()
    try:
        profile = store.update(get_current_user().id, profile_id, name=body.name, avatar=body.avatar, disabled=body.disabled)
    except KeyError as exc:
        raise HTTPException(404, "学习档案不存在") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    _audit(store, "profile_updated", profile_id)
    return profile.public_dict()


@router.post("/{profile_id}/unlock")
async def unlock_profile(profile_id: str, body: UnlockRequest, response: Response, _: TokenPayload | None = Depends(require_auth)) -> dict:
    store, grants = _stores()
    user = get_current_user()
    try:
        profile = store.verify_and_record(user.id, profile_id, body.pin)
    except KeyError as exc:
        raise HTTPException(404, "学习档案不存在") from exc
    except ProfileLockedError as exc:
        _audit(store, "profile_unlock", profile_id, outcome="locked", metadata={"locked_until": exc.locked_until})
        raise HTTPException(423, {"message": "PIN 尝试过多，档案暂时锁定", "locked_until": exc.locked_until}) from exc
    except PermissionError as exc:
        _audit(store, "profile_unlock", profile_id, outcome="denied")
        raise HTTPException(401, "PIN 不正确") from exc
    raw, _grant = grants.issue(user.id, profile.id)
    response.set_cookie(value=raw, max_age=COOKIE_MAX_AGE, **_cookie_attrs())
    _audit(store, "profile_unlock", profile.id)
    return {"ok": True, "profile": profile.public_dict(), "idle_timeout_minutes": 30}


@router.post("/lock")
async def lock_profile(response: Response, dt_learning_profile: str | None = Cookie(default=None), _: TokenPayload | None = Depends(require_auth)) -> dict:
    store, grants = _stores()
    grants.revoke(dt_learning_profile or "", get_current_user().id)
    response.delete_cookie(**_cookie_attrs())
    _audit(store, "profile_locked", get_current_learning_profile().profile_id if get_current_learning_profile() else "")
    return {"ok": True}


@router.get("/active")
async def active_profile(_: TokenPayload | None = Depends(require_auth)) -> dict:
    access = get_current_learning_profile()
    if access is None:
        return {"unlocked": False, "profile": None}
    store, _ = _stores()
    profile = store.get(access.owner_user_id, access.profile_id)
    return {"unlocked": profile is not None, "profile": profile.public_dict() if profile else None, "mode": access.mode, "read_only": access.read_only}


@router.post("/{profile_id}/pin/change")
async def change_pin(profile_id: str, body: ChangePinRequest, response: Response, _: TokenPayload | None = Depends(require_auth)) -> dict:
    store, grants = _stores()
    user = get_current_user()
    try:
        store.verify_and_record(user.id, profile_id, body.current_pin)
        store.change_pin(user.id, profile_id, body.new_pin)
    except (KeyError, PermissionError, ProfileLockedError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    response.delete_cookie(**_cookie_attrs())
    _audit(store, "profile_pin_changed", profile_id)
    return {"ok": True, "locked": True}


@router.post("/{profile_id}/pin/reset")
async def reset_pin(profile_id: str, body: ResetPinRequest, response: Response, _: TokenPayload = Depends(require_admin)) -> dict:
    store, _ = _stores()
    try:
        store.change_pin(get_current_user().id, profile_id, body.new_pin)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    response.delete_cookie(**_cookie_attrs())
    _audit(store, "profile_pin_reset", profile_id, mode="admin")
    return {"ok": True, "locked": True}


@router.post("/{profile_id}/teacher-view")
async def teacher_view(profile_id: str, response: Response, _: TokenPayload = Depends(require_admin)) -> dict:
    store, grants = _stores()
    user = get_current_user()
    if store.get(user.id, profile_id) is None:
        raise HTTPException(404, "学习档案不存在")
    raw, _ = grants.issue(user.id, profile_id, mode="teacher_view", actor_user_id=user.id)
    response.set_cookie(value=raw, max_age=TEACHER_COOKIE_MAX_AGE, **_cookie_attrs())
    _audit(store, "teacher_view_started", profile_id, mode="teacher_view")
    return {"ok": True, "read_only": True, "expires_in": TEACHER_COOKIE_MAX_AGE}


@router.post("/{profile_id}/impersonate")
async def impersonate(
    profile_id: str,
    body: ImpersonateRequest,
    response: Response,
    _: TokenPayload = Depends(require_admin),
) -> dict:
    store, grants = _stores()
    user = get_current_user()
    if store.get(user.id, profile_id) is None:
        raise HTTPException(404, "学习档案不存在")
    try:
        raw, grant = grants.issue(
            user.id,
            profile_id,
            mode="impersonate",
            actor_user_id=user.id,
            scopes=tuple(body.scopes),
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    response.set_cookie(value=raw, max_age=TEACHER_COOKIE_MAX_AGE, **_cookie_attrs())
    _audit(
        store,
        "impersonation_started",
        profile_id,
        mode="impersonate",
        metadata={
            "impersonation_id": grant.impersonation_id,
            "reason": grant.reason,
            "scopes": list(grant.scopes),
        },
    )
    return {
        "ok": True,
        "read_only": False,
        "expires_in": TEACHER_COOKIE_MAX_AGE,
        "impersonation_id": grant.impersonation_id,
        "scopes": list(grant.scopes),
    }
