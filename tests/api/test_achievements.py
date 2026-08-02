"""achievements API tests."""

from __future__ import annotations

import pytest

from deeptutor.api.routers.achievements import router


def test_router_has_get_achievements():
    methods = set()
    paths = set()
    for route in router.routes:
        paths.add(getattr(route, "path", ""))
        methods |= getattr(route, "methods", set())
    assert "/achievements" in paths
    assert "GET" in methods


@pytest.mark.asyncio
async def test_get_achievements_returns_derived_payload(monkeypatch) -> None:
    from deeptutor.api.routers.achievements import get_achievements

    fake = {
        "checkin": {"dates": ["2026-08-01"], "total_days": 1, "streak": 1, "today_checked": True},
        "badges": [{"id": "first_step", "name": "新手上路", "description": "完成首次学习", "unlocked": True, "unlocked_at": "2026-08-01T10:00:00+00:00"}],
    }
    monkeypatch.setattr("deeptutor.api.routers.achievements._derive_payload", lambda: fake)
    result = await get_achievements()
    assert result == fake
    assert result["checkin"]["streak"] == 1
