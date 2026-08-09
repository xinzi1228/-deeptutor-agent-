from __future__ import annotations

import asyncio

import pytest

from deeptutor.events.event_bus import Event, EventType
from deeptutor.services.notifications.broadcaster import (
    NotificationBroadcaster,
    NotificationRecord,
)


@pytest.fixture(autouse=True)
def _reset_broadcaster():
    """Give each test a fresh singleton instance."""
    NotificationBroadcaster._instance = None
    yield
    NotificationBroadcaster._instance = None


@pytest.mark.asyncio
async def test_publish_forwards_to_subscriber_queue():
    b = NotificationBroadcaster.instance()
    q = b.subscribe()

    rec = await b.publish("capability_complete", "回合完成", "助手已回复，可以查看新消息了。")

    got = q.get_nowait()
    assert got is rec
    assert got.seq == 1
    assert got.event_type == "capability_complete"
    assert got.title == "回合完成"
    assert got.body == "助手已回复，可以查看新消息了。"


@pytest.mark.asyncio
async def test_get_missed_only_returns_seqs_after_marker():
    b = NotificationBroadcaster.instance()
    await b.publish("capability_complete", "t1", "b1")
    await b.publish("capability_complete", "t2", "b2")
    await b.publish("capability_complete", "t3", "b3")

    missed = b.get_missed(after_seq=1)
    assert [r.seq for r in missed] == [2, 3]
    assert b.get_missed(after_seq=3) == []
    assert [r.seq for r in b.get_missed(after_seq=0)] == [1, 2, 3]


@pytest.mark.asyncio
async def test_epoch_stable_across_publishes_on_same_instance():
    b = NotificationBroadcaster.instance()
    r1 = await b.publish("capability_complete", "t1", "b1")
    r2 = await b.publish("capability_complete", "t2", "b2")

    assert r1.epoch == b.epoch
    assert r2.epoch == b.epoch
    assert b.epoch  # non-empty process UUID


@pytest.mark.asyncio
async def test_buffer_evicts_oldest_beyond_max():
    b = NotificationBroadcaster.instance()
    for i in range(b.MAX_BUFFER + 10):
        await b.publish("capability_complete", f"t{i}", f"b{i}")

    assert len(b._buffer) == b.MAX_BUFFER
    assert b._buffer[0].seq == 11
    assert b.get_missed(0)[0].seq == 11


@pytest.mark.asyncio
async def test_snapshot_structure():
    b = NotificationBroadcaster.instance()
    await b.publish("capability_complete", "回合完成", "助手已回复，可以查看新消息了。", turn_id="t1", session_id="s1")

    snap = b.snapshot(after_seq=0)
    assert snap["epoch"] == b.epoch
    assert snap["next_seq"] == 2
    assert len(snap["notifications"]) == 1

    n = snap["notifications"][0]
    assert set(n) == {"seq", "epoch", "event_type", "title", "body", "turn_id", "session_id", "timestamp"}
    assert n["seq"] == 1
    assert n["turn_id"] == "t1"
    assert n["session_id"] == "s1"


@pytest.mark.asyncio
async def test_capability_complete_hook_publishes_notification():
    from deeptutor.api.main import hook_capability_complete

    b = NotificationBroadcaster.instance()
    q = b.subscribe()

    event = Event(
        type=EventType.CAPABILITY_COMPLETE,
        task_id="turn-123",
        user_input="标注第 3 张图",
        agent_output="",
        metadata={
            "capability": "chat",
            "session_id": "sess-9",
            "turn_id": "turn-123",
        },
    )
    await hook_capability_complete(event)

    got = q.get_nowait()
    assert isinstance(got, NotificationRecord)
    assert got.event_type == "capability_complete"
    assert got.title == "回合完成"
    assert got.turn_id == "turn-123"
    assert got.session_id == "sess-9"


@pytest.mark.asyncio
async def test_capability_complete_hook_skips_events_without_turn_id():
    from deeptutor.api.main import hook_capability_complete

    b = NotificationBroadcaster.instance()

    # metadata-less payloads are ignored rather than publishing empty toasts
    await hook_capability_complete(object())
    await hook_capability_complete(None)

    # partner completions carry partner metadata but no turn_id -> ignored
    await hook_capability_complete(
        Event(
            type=EventType.CAPABILITY_COMPLETE,
            task_id="partner:wx:group:chat1",
            user_input="",
            agent_output="partner reply",
            metadata={
                "source": "partner",
                "partner_id": "wx",
                "channel": "wechat",
                "chat_id": "chat1",
            },
        )
    )

    assert b.get_missed(0) == []


def test_capability_complete_hook_registered_on_real_event_bus():
    from deeptutor.api.main import (
        hook_capability_complete,
        register_capability_complete_hook,
    )
    from deeptutor.events.event_bus import EventType, get_event_bus

    event_bus = get_event_bus()
    subscribers = event_bus._subscribers[EventType.CAPABILITY_COMPLETE]
    before = list(subscribers)

    assert register_capability_complete_hook() is True
    assert subscribers.count(hook_capability_complete) == 1
    # idempotent — a second lifespan boot must not double-subscribe
    assert register_capability_complete_hook() is True
    assert subscribers.count(hook_capability_complete) == 1

    subscribers[:] = before


@pytest.mark.asyncio
async def test_capability_complete_hook_fires_via_real_event_bus():
    from deeptutor.api.main import (
        hook_capability_complete,
        register_capability_complete_hook,
    )
    from deeptutor.events.event_bus import Event, EventType, get_event_bus

    b = NotificationBroadcaster.instance()
    q = b.subscribe()

    assert register_capability_complete_hook() is True
    event_bus = get_event_bus()
    try:
        await event_bus.publish(
            Event(
                type=EventType.CAPABILITY_COMPLETE,
                task_id="turn-9",
                user_input="标注第 4 张图",
                agent_output="",
                metadata={"turn_id": "turn-9", "session_id": "sess-9"},
            )
        )
        await asyncio.wait_for(event_bus.flush(), timeout=5)

        got = q.get_nowait()
        assert got.event_type == "capability_complete"
        assert got.turn_id == "turn-9"
        assert got.session_id == "sess-9"
    finally:
        await event_bus.stop()
        event_bus.unsubscribe(EventType.CAPABILITY_COMPLETE, hook_capability_complete)
