# 第八轮优化实现计划 C：WS 即推送 + seq/epoch 重放（借鉴 stablyai/orca mobile-notification-replay）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 回合完成通知——后端进程级 `NotificationBroadcaster`（`notificationSeq` 单调 + `notificationEpoch` 进程 UUID + 重放缓冲），前端 WS 订阅通知 → Toast/Coach 气泡；断线重连 `getMissedSince(seq, epoch)` 幂等 catch-up。借鉴 Orca mobile-notification-replay。

**Architecture:**
- **后端**：新模块 `deeptutor/services/notifications/broadcaster.py`（进程级单例，镜像 `api/utils/progress_broadcaster.py` 模式），订阅全局 `EventBus.CAPABILITY_COMPLETE`，写 `notificationSeq`+`notificationEpoch`+环形缓冲；`unified_ws.py` 新增 `subscribe_notifications`（首次连接自动）+ `get_missed_notifications` 消息类型。
- **前端**：`web/lib/unified-ws.ts` 新增通知监听/`lastNotificationSeq`/`notificationEpoch` 持久化；`web/lib/notifications.ts` 复用 `notify()` 做成功 toast；重连后 `getMissedSince`。

**Tech Stack:** Python asyncio / TypeScript / StreamEvent 协议。参考：`%TEMP%\opencode\refs\orca\orca\mobile\src\lib\mobile-notification-replay.ts`。

---

## 背景（已核实，explore 子代理）

- **后端 WS**：`deeptutor/api/routers/unified_ws.py` L44 `/api/v1/ws`；每订阅一个 `_forward` task（subscribe_turn/subscribe_session），客户端主动订阅才收事件。`resume_from`+`after_seq` 是**每回合**重放。
- **回合完成**：`turn_runtime.py` `_publish_live_event`（L1830-1859）给每事件打**每回合** seq；DONE 事件 metadata 带 `status`（completed/cancelled/failed）。
- **全局事件**：`deeptutor/events/event_bus.py` `EventBus` 单例 + `EventType.CAPABILITY_COMPLETE`，`ChatOrchestrator._publish_completion`（orchestrator.py L96-114）发布。**这是 F2 挂点**（进程级广播，无需碰每回合 StreamBus）。
- **前端 WS 客户端**：`web/lib/unified-ws.ts` `UnifiedWSClient`（L158），`onmessage` L205-222 已跟踪 `lastSeq`（每回合）；重连 `resume_from`；`lastSeq`/`activeTurnId` 是实例字段不持久化。
- **Toast**：`web/lib/notifications.ts` `notify()` + ToastViewport 已存在，目前只用于 error/disconnect toast。
- **现状缺口**：无"回合完成"通知；AnnotationCoach 的 done→flashCoach 是本地不跨重连。

## 任务分解

### Task 1: 后端 NotificationBroadcaster 模块

**Files:**
- Create: `deeptutor/services/notifications/broadcaster.py`

- [ ] **Step 1: 创建模块**——进程级单例，镜像 ProgressBroadcaster 模式：

```python
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
```

> 注：`asyncio.Lock` 在模块级实例使用——单例在事件循环内创建。若项目已在别的模块定义过进程级单例（如 ProgressBroadcaster），风格一致即可。

- [ ] **Step 2: 挂接 CAPABILITY_COMPLETE**——启动时订阅全局 EventBus（在 app lifespan 或首次 import 时 lazy hook）。查 `deeptutor/api/main.py` lifespan，在 start 处加：

```python
from deeptutor.events.event_bus import EventBus, EventType
from deeptutor.services.notifications.broadcaster import NotificationBroadcaster

async def _hook_capability_complete(event: Any) -> None:
    # event: dict with capability/status/session_id/turn_id etc.
    try:
        title = "回合完成"
        body = "助手已回复，可以查看新消息了。"
        await NotificationBroadcaster.instance().publish(
            "capability_complete",
            title,
            body,
            turn_id=str(event.get("turn_id", "")),
            session_id=str(event.get("session_id", "")),
        )
    except Exception:
        pass  # notification failure must never break the loop

EventBus.instance().subscribe(EventType.CAPABILITY_COMPLETE, _hook_capability_complete)
```

> 需先读 EventBus.subscribe 签名 + CAPABILITY_COMPLETE 事件的 payload 结构（explore 说 `_publish_completion` L96-114——确认 event 是 dict 还是 dataclass）。

- [ ] **Step 3: 验证 pytest**——新增测试 `tests/api/test_notification_broadcaster.py`（发布/订阅/get_missed/epoch 固定/缓冲上限/快照）：

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_notification_broadcaster.py -q
```

Expected: 全过。

- [ ] **Step 4: Commit**

```bash
git add deeptutor/services/notifications/broadcaster.py tests/api/test_notification_broadcaster.py deeptutor/api/main.py
git commit -m "feat: 回合完成通知广播器 (seq/epoch 重放, ⑧轮F2)"
```

---

### Task 2: 后端 WS 消息类型（订阅 + get_missed）

**Files:**
- Modify: `deeptutor/api/routers/unified_ws.py`

- [ ] **Step 1: 新增两个消息类型**——在 receive loop（L102-312）加：

```python
elif msg_type == "subscribe_notifications":
    # 连接时自动订阅；客户端也可显式订阅
    notif_q = NotificationBroadcaster.instance().subscribe()
    notification_tasks[ws] = asyncio.create_task(_forward_notifications(ws, notif_q))

elif msg_type == "get_missed_notifications":
    after_seq = int(data.get("after_seq") or 0)
    snap = NotificationBroadcaster.instance().snapshot(after_seq)
    await safe_send(ws, {"type": "notifications_snapshot", **snap})
```

并新增 `_forward_notifications`（镜像 `_forward`，事件转 dict + safe_send），以及连接断开时 cleanup 通知订阅。

> 需读 unified_ws.py 现有 receive loop + `_forward` + safe_send 模式，保持风格一致；注意 ws 连接级状态（`notification_tasks` dict 与现有 `subscription_tasks` 并列或复用）。

- [ ] **Step 2: 验证 pytest**——现有 WS 测试保持过；新增/扩展测试覆盖 `get_missed_notifications`：

```
python -m pytest tests/api/ -k "ws or notification" -q
```

Expected: 无回归。

- [ ] **Step 3: Commit**

```bash
git add deeptutor/api/routers/unified_ws.py
git commit -m "feat: WS 通知订阅 + get_missed 重放 (⑧轮F2)"
```

---

### Task 3: 前端 WS 客户端通知消费 + 持久化

**Files:**
- Modify: `web/lib/unified-ws.ts`
- Modify: `web/lib/notifications.ts`（若需新增通知类型）

- [ ] **Step 1: 客户端加通知状态**——`UnifiedWSClient`：

```ts
// 通知重放状态（持久化跨重连，不跨刷新——刷新后 getMissed 从 0 拿 epoch 内缓冲）
lastNotificationSeq: number | null = null;
notificationEpoch: string | null = null;
private notificationListeners: ((n: NotificationEvent) => void)[] = [];

onNotificationEvent(cb: (n: NotificationEvent) => void): () => void {
  this.notificationListeners.push(cb);
  return () => {
    this.notificationListeners = this.notificationListeners.filter((f) => f !== cb);
  };
}

private emitNotification(n: NotificationEvent) {
  for (const cb of this.notificationListeners) cb(n);
}
```

`onmessage` 加：

```ts
if (event.type === "notifications_snapshot") {
  // 重放缓冲：snapshot.notifications = [{seq, epoch, title, body, ...}]
  if (event.epoch) this.notificationEpoch = event.epoch;
  for (const n of (event.notifications ?? [])) {
    this.lastNotificationSeq = Math.max(this.lastNotificationSeq ?? 0, n.seq);
    this.emitNotification(n);
  }
}
```

`connect()` 内 `onopen`（现有 resume_from 逻辑后）加：

```ts
// 通知订阅 + 断线 catch-up
this.send({ type: "subscribe_notifications" });
if (this.notificationEpoch && this.lastNotificationSeq != null) {
  this.send({ type: "get_missed_notifications", after_seq: this.lastNotificationSeq });
} else {
  this.send({ type: "get_missed_notifications", after_seq: 0 });
}
```

> 需读 unified-ws.ts 现有 send/resume_from 结构确认字段名。NotificationEvent 类型按 snapshot 的 notifications 项定义。

- [ ] **Step 2: 接入 Toast**——在 UnifiedChatContext（或独立 hook `useTurnNotifications`）订阅通知事件，收到 `capability_complete` 时 `notify(t.body, { tone: "success" })`（notifications.ts 若 tone 只支持 error/info 需加 "success"）。

> 复用现有 ToastViewport。注意不要对用户**正在看**的回合重复打扰——若页面已聚焦/正在该会话可跳过（MVP：直接 toast，P2 加聚焦判断）。

- [ ] **Step 3: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 4: Commit**

```bash
git add web/lib/unified-ws.ts web/lib/notifications.ts web/context/UnifiedChatContext.tsx
git commit -m "feat: 前端回合完成通知 + 断线 catch-up (⑧轮F2)"
```

---

## 验证
- 后端：`pytest tests/api/test_notification_broadcaster.py` + WS 相关测试无回归
- 前端：`npx tsc --noEmit`（清代理）
- 冒烟（可选，需服务）：annotation 页发起回合 → 完成后 toast；断线重连后 catch-up 遗漏通知

## 提交（仅 commit，不 push）
- 按 Task 拆 3 个 commit。**不触碰 annotation_tool*.html**。
