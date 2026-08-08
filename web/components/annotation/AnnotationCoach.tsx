"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { MessageCircle, Send, X } from "lucide-react";
import { apiFetch, apiUrl } from "@/lib/api";
import {
  UnifiedWSClient,
  type StartTurnMessage,
  type StreamEvent,
} from "@/lib/unified-ws";
import { shouldAppendEventContent } from "@/lib/stream";
import {
  readStoredActiveSessionId,
  readStoredLanguage,
} from "@/context/app-shell-storage";

const STRUGGLE_POLL_MS = 30_000;
const STRUGGLE_WINDOW_MS = 60_000;
const SHORTCUT_DISMISS_KEY = "annotation.coach.shortcuts.dismissed";

interface CoachMessage {
  role: "user" | "coach";
  content: string;
}

type CoachMood = "celebrating" | "empathetic" | "curious" | "neutral";

type CoachStatus = "idle" | "working" | "waiting-input" | "flash";

interface CoachFlash {
  status: CoachStatus;
  until: number;
}

// Hermes 宠物状态机借鉴（agent/pet/state.py derive_pet_state 优先级）：
// waiting-input(学生回合) > working(发送中) > idle；flash 瞬态覆盖稳态。
function deriveCoachStatus(sending: boolean, awaitingInput: boolean): CoachStatus {
  if (awaitingInput) return "waiting-input";
  if (sending) return "working";
  return "idle";
}

const STATUS_RING: Record<string, string> = {
  idle: "",
  working: "border-[var(--primary)]/40 border-t-[var(--primary)]",
  "waiting-input": "border-[var(--muted-foreground)]/40 border-t-[var(--muted-foreground)]",
  flash: "border-[var(--primary)]/60 border-t-[var(--primary)]",
};

const MOOD_KEYWORDS: { mood: CoachMood; words: string[] }[] = [
  {
    mood: "celebrating",
    words: [
      "太棒了",
      "恭喜",
      "很不错",
      "不错！",
      "完美",
      "满分",
      "过关了",
      "已过关",
      "厉害了",
      "提升很大",
      "明显提升",
      "进步很大",
      "进步明显",
      "画得真准",
    ],
  },
  {
    mood: "empathetic",
    words: ["别急", "没关系", "再试一次", "不难", "别灰心", "正常", "都会遇到", "加油"],
  },
  {
    mood: "curious",
    words: ["试试", "换个思路", "想一想", "你觉得呢", "为什么", "要不要"],
  },
];

const MOOD_EMOJI: Record<CoachMood, string> = {
  celebrating: "🎉",
  empathetic: "💪",
  curious: "💡",
  neutral: "",
};

function detectCoachMood(text: string): CoachMood {
  for (const { mood, words } of MOOD_KEYWORDS) {
    if (words.some((w) => text.includes(w))) return mood;
  }
  return "neutral";
}

function CoachBubble({ content }: { content: string }) {
  const mood = detectCoachMood(content);
  const moodEmoji = MOOD_EMOJI[mood];
  return (
    <div
      className={`max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-bl-sm border border-[var(--border)] px-3.5 py-2.5 text-[13px] leading-relaxed ${
        mood === "celebrating"
          ? "bg-[var(--primary)]/5 text-[var(--foreground)]"
          : "bg-[var(--background)] text-[var(--foreground)]"
      }`}
    >
      {moodEmoji && (
        <span className="mr-1" aria-hidden="true">
          {moodEmoji}
        </span>
      )}
      {content}
    </div>
  );
}

interface AnnotationCoachProps {
  /** Existing chat session id. Falls back to the app's active session, then
   *  the backend creates a new session on first send. */
  sessionId?: string;
}

interface TraceLogEntry {
  timestamp?: string;
  type?: string;
  task_id?: string;
  intervention?: {
    kind?: string;
    target?: string;
    rationale?: string;
    timestamp?: string;
  } | null;
}

export default function AnnotationCoach({
  sessionId = "",
}: AnnotationCoachProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<CoachMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [awaitingInput, setAwaitingInput] = useState(false);
  const [flash, setFlash] = useState<CoachFlash | null>(null);
  const flashTimerRef = useRef<number | null>(null);

  const flashCoach = useCallback((ms = 1600) => {
    if (flashTimerRef.current) window.clearTimeout(flashTimerRef.current);
    setFlash({ status: "flash", until: Date.now() + ms });
    flashTimerRef.current = window.setTimeout(() => {
      setFlash(null);
      flashTimerRef.current = null;
    }, ms);
  }, []);

  const [hint, setHint] = useState<string | null>(null);
  const [showShortcuts, setShowShortcuts] = useState(true);

  const clientRef = useRef<UnifiedWSClient | null>(null);
  const sessionIdRef = useRef<string>(sessionId || readStoredActiveSessionId() || "");
  const shownStrugglesRef = useRef<Set<string>>(new Set());
  const listEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      if (window.localStorage.getItem(SHORTCUT_DISMISS_KEY) === "1") {
        setShowShortcuts(false);
      }
    } catch {
      // localStorage unavailable — keep defaults
    }
  }, []);

  const handleEvent = useCallback((event: StreamEvent) => {
    if (event.type === "session") {
      const meta = (event.metadata ?? {}) as { session_id?: string };
      const next = meta.session_id || event.session_id || "";
      if (next) sessionIdRef.current = next;
      return;
    }
    if (event.type === "done") {
      setSending(false);
      setAwaitingInput(false);
      flashCoach(); // 回合完成 → flash（Hermes just_completed→WAVE 借鉴）
      return;
    }
    if (event.type === "error") {
      setSending(false);
      setAwaitingInput(false);
      setMessages((prev) => [
        ...prev,
        { role: "coach", content: event.content || "抱歉，我遇到了一点问题，请稍后再试。" },
      ]);
      flashCoach(); // 错误也 flash（Hermes error→FAILED 借鉴，emoji 走 mood）
      return;
    }
    if (event.type === "wait_for_input") {
      setAwaitingInput(true);
      return;
    }
    if (event.type === "content" && shouldAppendEventContent(event)) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "coach") {
          const next = [...prev];
          next[next.length - 1] = {
            ...last,
            content: `${last.content}${event.content}`,
          };
          return next;
        }
        return [...prev, { role: "coach", content: event.content }];
      });
    }
  }, []);

  const ensureClient = useCallback(() => {
    if (clientRef.current) return clientRef.current;
    const client = new UnifiedWSClient(handleEvent, () => {
      setSending(false);
    });
    clientRef.current = client;
    return client;
  }, [handleEvent]);

  const send = useCallback(() => {
    const content = input.trim();
    if (!content || sending) return;
    setMessages((prev) => [...prev, { role: "user", content }]);
    setInput("");
    setSending(true);

    const client = ensureClient();
    if (!client.connected) client.connect();

    const payload: StartTurnMessage = {
      type: "message",
      content,
      session_id: sessionIdRef.current || null,
      capability: "chat",
      language: readStoredLanguage(),
      persona: "annotation-coach",
    };

    const attemptSend = (attempt = 0) => {
      if (client.connected) {
        client.send(payload);
        return;
      }
      if (attempt >= 10) {
        setSending(false);
        setMessages((prev) => [
          ...prev,
          { role: "coach", content: "连接不上服务，请稍后再试。" },
        ]);
        return;
      }
      window.setTimeout(() => attemptSend(attempt + 1), 200);
    };
    attemptSend();
  }, [input, sending, ensureClient]);

  // 卡点主动介入：~30s 轮询 trace-log，最近 1 分钟内有 struggle 介入 → 弹气泡
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const res = await apiFetch(apiUrl("/api/v1/profile/trace-log?limit=30"), {
          cache: "no-store",
        });
        if (!res.ok) return;
        const data = (await res.json()) as { traces?: TraceLogEntry[] };
        const now = Date.now();
        for (const trace of data.traces ?? []) {
          const intervention = trace.intervention;
          const kind = String(intervention?.kind ?? "");
          if (!intervention || !kind.includes("struggle")) continue;
          const tsRaw = intervention.timestamp ?? trace.timestamp ?? "";
          const ts = Date.parse(String(tsRaw).replace("Z", "+00:00"));
          if (!Number.isFinite(ts) || now - ts > STRUGGLE_WINDOW_MS) continue;
          const marker = `${tsRaw}|${kind}`;
          if (shownStrugglesRef.current.has(marker)) continue;
          shownStrugglesRef.current.add(marker);
          if (!cancelled) {
            setHint(
              t("annotation.coach.struggleHint", {
                defaultValue:
                  "别急，这个坑很多新手都踩过。要我提示一下思路吗？",
              }),
            );
          }
          return;
        }
      } catch {
        // 轮询失败静默
      }
    };
    void check();
    const timer = window.setInterval(check, STRUGGLE_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      if (flashTimerRef.current) window.clearTimeout(flashTimerRef.current);
      clientRef.current?.disconnect();
      clientRef.current = null;
    };
  }, [t]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, open]);

  const dismissShortcuts = () => {
    setShowShortcuts(false);
    try {
      window.localStorage.setItem(SHORTCUT_DISMISS_KEY, "1");
    } catch {
      // ignore
    }
  };

  const toggleShortcuts = (checked: boolean) => {
    if (checked) {
      dismissShortcuts();
    } else {
      setShowShortcuts(true);
      try {
        window.localStorage.removeItem(SHORTCUT_DISMISS_KEY);
      } catch {
        // ignore
      }
    }
  };

  const coachStatus = deriveCoachStatus(sending, awaitingInput);
  const flashActive = flash !== null && Date.now() < flash.until;
  const ringClass = flashActive ? STATUS_RING.flash : STATUS_RING[coachStatus];

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3">
      {hint && (
        <div className="relative max-w-[260px] rounded-2xl rounded-br-sm border border-[var(--border)] bg-[var(--card)] px-3.5 py-2.5 text-[13px] leading-relaxed text-[var(--foreground)] shadow-lg">
          <button
            aria-label="close hint"
            onClick={() => setHint(null)}
            className="absolute -right-2 -top-2 rounded-full border border-[var(--border)] bg-[var(--background)] p-0.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <X className="h-3 w-3" />
          </button>
          {hint}
        </div>
      )}

      {open && (
        <div className="flex h-[440px] w-[340px] flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-xl">
          <div className="flex items-center gap-2 border-b border-[var(--border)] px-3.5 py-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--primary)] text-base">
              🤖
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-[var(--foreground)]">
                  {t("annotation.coach.title", { defaultValue: "标注小助手" })}
                </span>
                <span className="rounded border border-[var(--primary)] px-1.5 py-0.5 text-[10px] leading-none text-[var(--primary)]">
                  AI 助手
                </span>
              </div>
              <p className="text-[11px] text-[var(--muted-foreground)]">
                {t("annotation.coach.subtitle", {
                  defaultValue: "不懂的标注操作随时问我",
                })}
              </p>
            </div>
            <button
              aria-label="close coach"
              onClick={() => setOpen(false)}
              className="rounded-md p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {showShortcuts && (
            <div className="border-b border-[var(--border)] bg-[var(--background)]/60 px-3.5 py-2.5 text-[12px] leading-relaxed">
              <div className="mb-1 flex items-center gap-1.5 font-medium text-[var(--foreground)]">
                <MessageCircle className="h-3.5 w-3.5 text-[var(--primary)]" />
                {t("annotation.coach.shortcuts.title", {
                  defaultValue: "快捷键提示",
                })}
              </div>
              <ul className="space-y-0.5 text-[var(--muted-foreground)]">
                <li>
                  <span className="font-mono text-[11px] text-[var(--foreground)]">B</span>{" "}
                  画框
                  <span className="mx-2 text-[var(--border)]">|</span>
                  <span className="font-mono text-[11px] text-[var(--foreground)]">Ctrl+Z</span>{" "}
                  撤销
                  <span className="mx-2 text-[var(--border)]">|</span>
                  <span className="font-mono text-[11px] text-[var(--foreground)]">Enter</span>{" "}
                  提交
                </li>
              </ul>
              <label className="mt-1.5 flex cursor-pointer items-center gap-1.5 text-[11px] text-[var(--muted-foreground)]">
                <input
                  type="checkbox"
                  checked={!showShortcuts}
                  onChange={(e) => toggleShortcuts(e.target.checked)}
                  className="h-3 w-3 accent-[var(--primary)]"
                />
                {t("annotation.coach.shortcuts.dontShow", {
                  defaultValue: "不再显示",
                })}
              </label>
            </div>
          )}

          <div className="flex-1 space-y-2.5 overflow-y-auto px-3.5 py-3">
            {messages.length === 0 && (
              <div className="rounded-2xl rounded-bl-sm border border-[var(--border)] bg-[var(--background)] px-3.5 py-2.5 text-[13px] leading-relaxed text-[var(--foreground)]">
                {t("annotation.coach.greeting", {
                  defaultValue:
                    "Hi，我是你的标注陪练 🤗 今天想练哪块？有不懂的随时问我，练完我帮你看看哪里能更好。",
                })}
              </div>
            )}
            {messages.map((msg, i) =>
              msg.role === "user" ? (
                <div
                  key={i}
                  className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--primary)] px-3.5 py-2.5 text-[13px] leading-relaxed text-[var(--primary-foreground)]"
                >
                  {msg.content}
                </div>
              ) : (
                <CoachBubble key={i} content={msg.content} />
              ),
            )}
            {sending && (
              <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-[var(--border)] bg-[var(--background)] px-3.5 py-2.5 text-[13px] text-[var(--muted-foreground)]">
                思考中…
              </div>
            )}
            <div ref={listEndRef} />
          </div>

          <div className="flex items-center gap-2 border-t border-[var(--border)] p-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={t("annotation.coach.inputPlaceholder", {
                defaultValue: "输入你的问题…",
              })}
              className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)]"
            />
            <button
              aria-label="send"
              onClick={send}
              disabled={sending || !input.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] transition-opacity disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      <button
        aria-label="toggle annotation coach"
        onClick={() => setOpen((v) => !v)}
        className={`relative flex h-14 w-14 items-center justify-center rounded-full border-2 ${ringClass} bg-[var(--primary)] text-2xl shadow-lg transition-transform hover:scale-105`}
      >
        <span className="pointer-events-none absolute inset-0 animate-ping rounded-full bg-[var(--primary)] opacity-30" />
        <span className="relative">🤖</span>
      </button>
    </div>
  );
}
