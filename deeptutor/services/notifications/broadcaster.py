"""Process-wide turn-completion notifications with seq/epoch replay.

Borrowed from stablyai/orca mobile-notification-replay: a monotonic
``notificationSeq`` + process-lifetime ``notificationEpoch`` let clients
catch up missed notifications after a disconnect via getMissedSince(seq, epoch).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NotificationRecord:
    seq: int
    epoch: str
    event_type: str
    title: str
    body: str
    turn_id: str = ""
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)


class NotificationBroadcaster:
    """Singleton fan-out: one buffer + monotonic seq + epoch (process UUID)."""

    _instance: Optional["NotificationBroadcaster"] = None

    MAX_BUFFER = 256

    def __init__(self) -> None:
        self._epoch = uuid.uuid4().hex
        self._next_seq = 1
        self._buffer: list[NotificationRecord] = []
        self._subscribers: list[asyncio.Queue[NotificationRecord]] = []
        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "NotificationBroadcaster":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def epoch(self) -> str:
        return self._epoch

    async def publish(self, event_type: str, title: str, body: str, **extra: Any) -> NotificationRecord:
        rec = NotificationRecord(
            seq=self._next_seq,
            epoch=self._epoch,
            event_type=event_type,
            title=title,
            body=body,
            **extra,
        )
        async with self._lock:
            self._next_seq += 1
            self._buffer.append(rec)
            if len(self._buffer) > self.MAX_BUFFER:
                self._buffer = self._buffer[-self.MAX_BUFFER:]
            for q in self._subscribers:
                q.put_nowait(rec)
        return rec

    def subscribe(self) -> asyncio.Queue[NotificationRecord]:
        q: asyncio.Queue[NotificationRecord] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[NotificationRecord]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def get_missed(self, after_seq: int) -> list[NotificationRecord]:
        return [r for r in self._buffer if r.seq > after_seq]

    def snapshot(self, after_seq: int) -> dict[str, Any]:
        return {
            "epoch": self._epoch,
            "next_seq": self._next_seq,
            "notifications": [self._to_dict(r) for r in self.get_missed(after_seq)],
        }

    @staticmethod
    def _to_dict(r: NotificationRecord) -> dict[str, Any]:
        return {
            "seq": r.seq,
            "epoch": r.epoch,
            "event_type": r.event_type,
            "title": r.title,
            "body": r.body,
            "turn_id": r.turn_id,
            "session_id": r.session_id,
            "timestamp": r.timestamp,
        }
