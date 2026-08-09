/**
 * Unified WebSocket Client
 *
 * Connects to the single `/api/v1/ws` endpoint and provides
 * a typed streaming interface for the new ChatOrchestrator protocol.
 *
 * Features:
 * - Client-side heartbeat (30s ping / 45s dead-connection detection)
 * - Auto-reconnect with exponential backoff (max 5 attempts)
 * - resume_from after reconnection to continue a streaming turn
 */

import { wsUrl } from "./api";

// ---- StreamEvent types (mirror Python StreamEventType) ----

export type StreamEventType =
  | "stage_start"
  | "stage_end"
  | "thinking"
  | "observation"
  | "content"
  | "tool_call"
  | "tool_result"
  | "progress"
  | "sources"
  | "result"
  | "error"
  | "session"
  | "session_meta"
  | "wait_for_input"
  | "done";

export interface StreamEvent {
  type: StreamEventType;
  source: string;
  stage: string;
  content: string;
  metadata: Record<string, unknown>;
  session_id?: string;
  turn_id?: string;
  seq?: number;
  timestamp: number;
}

export interface LLMSelection {
  profile_id: string;
  model_id: string;
}

// ---- Notification types (process-wide turn-completion notifications) ----

/** A turn-completion notification pushed by the backend (``notification``
 *  message) or replayed inside a ``notifications_snapshot`` buffer. */
export interface NotificationEvent {
  seq: number;
  epoch: string;
  event_type: string;
  title: string;
  body: string;
  turn_id: string;
  session_id: string;
  timestamp: number;
}

/** Live push: ``{"type": "notification", ...NotificationEvent}``. */
export interface NotificationMessage extends NotificationEvent {
  type: "notification";
}

/** Replay snapshot for ``get_missed_notifications``: the backend echoes its
 *  current epoch plus every buffered notification with ``seq > after_seq``. */
export interface NotificationsSnapshotMessage {
  type: "notifications_snapshot";
  epoch: string;
  next_seq: number;
  notifications: NotificationEvent[];
}

// ---- Client message ----

export interface StartTurnMessage {
  type: "message" | "start_turn";
  content: string;
  tools?: string[];
  capability?: string | null;
  knowledge_bases?: string[];
  session_id?: string | null;
  attachments?: {
    type: string;
    url?: string;
    base64?: string;
    filename?: string;
    mime_type?: string;
  }[];
  language?: string;
  config?: Record<string, unknown>;
  notebook_references?: {
    notebook_id: string;
    record_ids: string[];
  }[];
  history_references?: string[];
  question_notebook_references?: number[];
  book_references?: {
    book_id: string;
    page_ids: string[];
  }[];
  persona?: string;
  llm_selection?: LLMSelection | null;
  /** Edit-branching: when present (even as ``null``) the new user message
   *  attaches at this exact parent — creating a sibling rather than
   *  appending to the session tail. */
  parent_message_id?: number | null;
}

export interface SubscribeTurnMessage {
  type: "subscribe_turn";
  turn_id: string;
  after_seq?: number;
}

export interface SubscribeSessionMessage {
  type: "subscribe_session";
  session_id: string;
  after_seq?: number;
}

export interface ResumeTurnMessage {
  type: "resume_from";
  turn_id: string;
  seq?: number;
}

export interface UnsubscribeMessage {
  type: "unsubscribe";
  turn_id?: string;
  session_id?: string;
}

export interface CancelTurnMessage {
  type: "cancel_turn";
  turn_id: string;
}

export interface RegenerateMessage {
  type: "regenerate";
  session_id: string;
  overrides?: Record<string, unknown>;
}

/**
 * Deliver the user's answer for an ``ask_user`` paused turn so the
 * agentic loop can resume on the same turn. The user's reply is
 * substituted into the matching ``role=tool`` message body before the
 * next LLM iteration runs.
 *
 * Either ``text`` (legacy single-question shape) or ``answers``
 * (v2 multi-question shape) must be provided. When both are present
 * the backend prefers ``answers``.
 */
export interface SubmitUserReplyMessage {
  type: "submit_user_reply";
  turn_id: string;
  text?: string;
  answers?: Array<{ questionId: string; text: string }>;
}

export interface SubscribeNotificationsMessage {
  type: "subscribe_notifications";
}

export interface GetMissedNotificationsMessage {
  type: "get_missed_notifications";
  after_seq: number;
}

export type ChatMessage =
  | StartTurnMessage
  | SubscribeTurnMessage
  | SubscribeSessionMessage
  | ResumeTurnMessage
  | UnsubscribeMessage
  | CancelTurnMessage
  | RegenerateMessage
  | SubmitUserReplyMessage
  | SubscribeNotificationsMessage
  | GetMissedNotificationsMessage;

// ---- Connection manager ----

export type EventHandler = (event: StreamEvent) => void;

const HEARTBEAT_INTERVAL_MS = 30_000;
const HEARTBEAT_TIMEOUT_MS = 45_000;
const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 200;

export class UnifiedWSClient {
  private ws: WebSocket | null = null;
  private onEvent: EventHandler;
  private onClose?: () => void;

  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private lastReceivedAt = 0;

  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;

  private activeTurnId: string | null = null;
  private lastSeq = 0;

  // Process-wide turn-completion notifications. These persist across
  // reconnects within the client's lifetime (but not across a page refresh
  // — a fresh client requests the whole current process-epoch buffer by
  // sending ``after_seq=0``).
  private notificationListeners: ((n: NotificationEvent) => void)[] = [];
  lastNotificationSeq: number | null = null;
  notificationEpoch: string | null = null;

  constructor(onEvent: EventHandler, onClose?: () => void) {
    this.onEvent = onEvent;
    this.onClose = onClose;
  }

  /** Provide the current turn/seq so reconnection can resume the stream. */
  setResumeState(turnId: string | null, seq: number): void {
    this.activeTurnId = turnId;
    this.lastSeq = seq;
  }

  /** Subscribe to process-wide turn-completion notifications. Returns an
   *  unsubscribe function. */
  onNotificationEvent(cb: (n: NotificationEvent) => void): () => void {
    this.notificationListeners.push(cb);
    return () => {
      this.notificationListeners = this.notificationListeners.filter(
        (f) => f !== cb,
      );
    };
  }

  private emitNotification(n: NotificationEvent): void {
    for (const cb of this.notificationListeners) cb(n);
  }

  connect(): void {
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) return;
    this.intentionalClose = false;

    const url = wsUrl("/api/v1/ws");
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.lastReceivedAt = Date.now();
      this.startHeartbeat();

      if (this.activeTurnId) {
        this.send({
          type: "resume_from",
          turn_id: this.activeTurnId,
          seq: this.lastSeq,
        });
      }

      // Process-wide notifications: subscribe on every (re)connect, then
      // request missed notifications since the last seen seq so a client
      // that dropped mid-stream catches up on turn completions that landed
      // while it was offline. Idempotent — the backend replays only
      // ``seq > after_seq`` from its in-process buffer.
      this.send({ type: "subscribe_notifications" });
      this.send({
        type: "get_missed_notifications",
        after_seq: this.lastNotificationSeq ?? 0,
      });
    };

    this.ws.onmessage = (ev) => {
      this.lastReceivedAt = Date.now();
      try {
        const event: StreamEvent = JSON.parse(ev.data);
        // Heartbeat frames (client-sent ``ping`` echoed by some legacy
        // backends, or ``pong`` from the modern handler) keep the socket
        // alive but are not user-visible chat events. They MUST be dropped
        // here — otherwise the message list renders them as "Unknown type"
        // error rows, especially during long-running turns.
        const type = (event as { type?: string }).type;
        if (type === "ping" || type === "pong") return;
        if (type === "notifications_snapshot") {
          this.handleNotificationsSnapshot(
            event as unknown as NotificationsSnapshotMessage,
          );
          return;
        }
        if (type === "notification") {
          this.handleNotification(event as unknown as NotificationMessage);
          return;
        }
        if (event.turn_id) this.activeTurnId = event.turn_id;
        if (event.seq != null) this.lastSeq = Math.max(this.lastSeq, event.seq);
        this.onEvent(event);
      } catch {
        console.warn("Unparseable WS message:", ev.data);
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      this.stopHeartbeat();
      if (!this.intentionalClose) {
        this.attemptReconnect();
      }
    };

    this.ws.onerror = (err) => {
      console.error("WS error:", err);
    };
  }

  send(msg: ChatMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("WebSocket not connected");
      return;
    }
    this.ws.send(JSON.stringify(msg));
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.stopHeartbeat();
    this.clearReconnectTimer();
    // Drop listeners so a disposed client can't fire stale callbacks.
    this.notificationListeners = [];
    this.ws?.close();
    this.ws = null;
    this.resetResumeState();
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // ---- Notifications ----

  private handleNotificationsSnapshot(
    msg: NotificationsSnapshotMessage,
  ): void {
    if (
      msg.epoch &&
      this.notificationEpoch &&
      msg.epoch !== this.notificationEpoch
    ) {
      // Backend restarted (a new process epoch restarted its monotonic
      // seq): replay from the beginning so the fresh buffer isn't skipped.
      this.lastNotificationSeq = null;
    }
    if (msg.epoch) this.notificationEpoch = msg.epoch;
    for (const n of msg.notifications ?? []) {
      this.lastNotificationSeq = Math.max(
        this.lastNotificationSeq ?? 0,
        n.seq,
      );
      this.emitNotification(n);
    }
  }

  private handleNotification(msg: NotificationMessage): void {
    if (msg.epoch) this.notificationEpoch = msg.epoch;
    if (msg.seq != null) {
      this.lastNotificationSeq = Math.max(
        this.lastNotificationSeq ?? 0,
        msg.seq,
      );
    }
    this.emitNotification(msg);
  }

  // ---- Heartbeat ----

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      if (Date.now() - this.lastReceivedAt > HEARTBEAT_TIMEOUT_MS) {
        this.ws.close();
        return;
      }

      try {
        this.ws.send(JSON.stringify({ type: "ping" }));
      } catch {
        // send may fail if socket is closing
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  // ---- Reconnect ----

  private attemptReconnect(): void {
    if (this.reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      this.resetResumeState();
      this.onClose?.();
      return;
    }

    const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempt);
    this.reconnectAttempt += 1;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private resetResumeState(): void {
    this.activeTurnId = null;
    this.lastSeq = 0;
    this.reconnectAttempt = 0;
  }
}
