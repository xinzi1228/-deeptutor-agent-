"""Share management — create (authed), read (public token), revoke."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from deeptutor.services.session import get_session_store
from deeptutor.services.share import get_share_store

router = APIRouter()          # authed: create/revoke
public_router = APIRouter()   # public: GET /share/{token}


class CreateShareRequest(BaseModel):
    session_id: str


@router.post("/shares")
async def create_share(payload: CreateShareRequest) -> dict[str, Any]:
    req = (
        payload
        if isinstance(payload, CreateShareRequest)
        else CreateShareRequest.model_validate(payload)
    )
    store = get_share_store()
    entry = store.create(req.session_id)
    return {
        "token": entry.token,
        "url": f"/share/{entry.token}",
        "session_id": entry.session_id,
    }


@router.delete("/shares/{token}")
async def revoke_share(token: str) -> dict[str, Any]:
    store = get_share_store()
    if store.revoke(token):
        return {"ok": True}
    return {"ok": False, "error": "分享不存在"}


@public_router.get("/share/{token}")
async def get_shared_session(token: str) -> dict[str, Any]:
    store = get_share_store()
    entry = store.get(token)
    if entry is None:
        return {"error": "分享链接无效或已过期"}
    session_store = get_session_store()
    session = await session_store.get_session_with_messages(entry.session_id)
    if session is None:
        return {"error": "会话不存在或已被删除"}
    return {"session": session, "shared": True}
