"""shares router — create (authed) / read (public token) / revoke."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_share_returns_token():
    from deeptutor.api.routers.shares import create_share

    result = await create_share({"session_id": "sess1"})
    assert "token" in result
    assert result["token"]
    assert "url" in result


@pytest.mark.asyncio
async def test_get_share_unknown_token():
    from deeptutor.api.routers.shares import get_shared_session

    result = await get_shared_session("unknown-token")
    assert result is not None
    assert "error" in result


@pytest.mark.asyncio
async def test_get_share_valid_token_recognized():
    from deeptutor.api.routers.shares import create_share, get_shared_session

    created = await create_share({"session_id": "sess1"})
    token = created["token"]
    result = await get_shared_session(token)
    # Token is recognized — either the session loads (test DB may or may not have it)
    # or we get a session-not-found error, but NEVER "invalid token"
    if result and "error" in result:
        assert "无效" not in str(result["error"]), "token should be valid"
    else:
        assert "session" in result
