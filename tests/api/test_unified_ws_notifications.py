from __future__ import annotations

import asyncio

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from deeptutor.services.notifications.broadcaster import NotificationBroadcaster


def _build_app() -> FastAPI:
    from deeptutor.api.routers.unified_ws import router as ws_router

    app = FastAPI()
    app.include_router(ws_router, prefix="/api/v1")
    return app


def _seed_notifications() -> None:
    """Populate the broadcaster buffer before the client connects."""

    async def _seed() -> None:
        b = NotificationBroadcaster.instance()
        await b.publish(
            "capability_complete", "t1", "b1", turn_id="turn-1", session_id="s-1"
        )
        await b.publish(
            "capability_complete", "t2", "b2", turn_id="turn-2", session_id="s-2"
        )

    asyncio.run(_seed())


@pytest.fixture(autouse=True)
def _fresh_broadcaster():
    NotificationBroadcaster._instance = None
    yield
    NotificationBroadcaster._instance = None


def test_get_missed_notifications_returns_snapshot() -> None:
    _seed_notifications()

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.send_json({"type": "get_missed_notifications", "after_seq": 1})
            snap = ws.receive_json()

    assert snap["type"] == "notifications_snapshot"
    assert snap["next_seq"] == 3
    assert [n["seq"] for n in snap["notifications"]] == [2]
    assert snap["notifications"][0]["turn_id"] == "turn-2"
    assert snap["notifications"][0]["epoch"] == snap["epoch"]


def test_get_missed_notifications_empty_after_latest_seq() -> None:
    _seed_notifications()

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.send_json({"type": "get_missed_notifications", "after_seq": 99})
            snap = ws.receive_json()

    assert snap["type"] == "notifications_snapshot"
    assert snap["notifications"] == []


def test_subscribe_notifications_accepted_without_error() -> None:
    _seed_notifications()

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.send_json({"type": "subscribe_notifications"})
            ws.send_json({"type": "ping"})
            got = ws.receive_json()

    # subscribe must not poison the loop; the pong still arrives.
    assert got == {"type": "pong"}
