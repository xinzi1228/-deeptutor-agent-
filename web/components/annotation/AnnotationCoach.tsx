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
  ChatChartCard,
  type ChartData,
} from "@/components/chat/home/ChatChartCard";
import { readStoredLanguage } from "@/context/app-shell-storage";

const STRUGGLE_POLL_MS = 30_000;
const STRUGGLE_WINDOW_MS = 60_000;
const SHORTCUT_DISMISS_KEY = "annotation.coach.shortcuts.dismissed";
const COACH_SESSION_KEY = "annotation.coach.session_id";
const COACH_POSITION_KEY = "annotation.coach.position";

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
  idle: "border-[var(--border)]",
  working: "border-amber-500/40 border-t-amber-500",
  "waiting-input":
    "border-[var(--muted-foreground)]/40 border-t-[var(--muted-foreground)]",
  flash: "border-emerald-500/60 border-t-emerald-500",
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

// PetPhrase 借鉴（logic.rs layout_group）：快捷语分组，chip 流式 + 使用频率排序
interface QuickPhrase {
  key: string; // i18n key
  label: string; // 默认中文兜底
}

const QUICK_PHRASES: { group: string; phrases: QuickPhrase[] }[] = [
  {
    group: "praise",
    phrases: [
      { key: "annotation.quick.praise.1", label: "夸一下" },
      { key: "annotation.quick.praise.2", label: "画得不错" },
      { key: "annotation.quick.praise.3", label: "进步了" },
    ],
  },
  {
    group: "hint",
    phrases: [
      { key: "annotation.quick.hint.1", label: "给点思路" },
      { key: "annotation.quick.hint.2", label: "我卡住了" },
    ],
  },
  {
    group: "advance",
    phrases: [
      { key: "annotation.quick.advance.1", label: "换一题" },
      { key: "annotation.quick.advance.2", label: "再练一遍" },
    ],
  },
  {
    group: "help",
    phrases: [
      { key: "annotation.quick.help.1", label: "帮我看看" },
      { key: "annotation.quick.help.2", label: "评分规则" },
    ],
  },
];

const QUICK_USES_KEY = "annotation.coach.quick.uses";
const QUESTION_MARKERS = ["？", "?", "不懂", "疑问", "怎么", "为什么", "卡住"];

function detectCoachMood(text: string): CoachMood {
  for (const { mood, words } of MOOD_KEYWORDS) {
    if (words.some((w) => text.includes(w))) return mood;
  }
  return "neutral";
}

// PetPhrase 借鉴：同组内按使用频率降序（同频保预设序），点击不重排
function sortByUses(phrases: QuickPhrase[], uses: Record<string, number>): QuickPhrase[] {
  return [...phrases].sort((a, b) => (uses[b.key] ?? 0) - (uses[a.key] ?? 0));
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
  const [cards, setCards] = useState<ChartData[]>([]);
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
  const [quickUses, setQuickUses] = useState<Record<string, number>>(() => {
    if (typeof window === "undefined") return {};
    try {
      const raw = window.localStorage.getItem(QUICK_USES_KEY);
      return raw ? (JSON.parse(raw) as Record<string, number>) : {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(QUICK_USES_KEY, JSON.stringify(quickUses));
    } catch {
      // localStorage 不可用则仅内存
    }
  }, [quickUses]);

  const clientRef = useRef<UnifiedWSClient | null>(null);
  const sessionIdRef = useRef<string>(sessionId);
  const shownStrugglesRef = useRef<Set<string>>(new Set());
  const listEndRef = useRef<HTMLDivElement | null>(null);
  const [position, setPosition] = useState({ right: 20, bottom: 20 });
  const dragRef = useRef<{ startX: number; startY: number; right: number; bottom: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);

  useEffect(() => {
    if (!sessionIdRef.current) {
      try {
        const stored = window.localStorage.getItem(COACH_SESSION_KEY);
        sessionIdRef.current = stored || `annotation-coach-${crypto.randomUUID()}`;
        window.localStorage.setItem(COACH_SESSION_KEY, sessionIdRef.current);
      } catch {
        sessionIdRef.current = `annotation-coach-${Date.now()}`;
      }
    }
    try {
      const raw = window.localStorage.getItem(COACH_POSITION_KEY);
      if (raw) {
        const stored = JSON.parse(raw) as { right?: number; bottom?: number };
        if (Number.isFinite(stored.right) && Number.isFinite(stored.bottom)) {
          setPosition({ right: Math.max(12, Number(stored.right)), bottom: Math.max(12, Number(stored.bottom)) });
        }
      }
    } catch { /* use default */ }
  }, []);

  const onPointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    dragRef.current = { startX: event.clientX, startY: event.clientY, right: position.right, bottom: position.bottom, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
    const next = {
      right: Math.min(Math.max(12, drag.right - dx), Math.max(12, window.innerWidth - 70)),
      bottom: Math.min(Math.max(12, drag.bottom - dy), Math.max(12, window.innerHeight - 70)),
    };
    setPosition(next);
  };

  const onPointerUp = () => {
    const drag = dragRef.current;
    dragRef.current = null;
    if (!drag) return;
    suppressClickRef.current = drag.moved;
    try { window.localStorage.setItem(COACH_POSITION_KEY, JSON.stringify(position)); } catch { /* ignore */ }
  };

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
    if (event.type === "tool_result") {
      const meta = (event.metadata ?? {}) as Record<string, unknown>;
      const toolMeta = (meta.tool_metadata ?? {}) as Record<string, unknown>;
      const chart = toolMeta.chart as ChartData | undefined;
      if (chart) {
        setCards((prev) => [...prev, chart]);
      }
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
      setAwaitingInput(false);
    });
    clientRef.current = client;
    return client;
  }, [handleEvent]);

  // PetPhrase copy_item 借鉴：发送核心（供输入框 send 与快捷语 sendQuickPhrase 复用）
  const sendText = useCallback(
    (content: string, opts?: { showUserMessage?: boolean }) => {
      const text = content.trim();
      if (!text) return;
      if (sending) {
        // 快捷语不弹忙时提示（不抢焦点）；输入框 send 由调用方处理忙时提示
        if (opts?.showUserMessage === false) return;
        if (!hint) {
          setHint(t("annotation.coach.busyHint", { defaultValue: "我在分析上一个问题，稍等一下～" }));
        }
        return;
      }
      if (opts?.showUserMessage !== false) {
        setMessages((prev) => [...prev, { role: "user", content: text }]);
      }
      setInput("");
      setSending(true);

      if (QUESTION_MARKERS.some((marker) => text.includes(marker))) {
        void apiFetch(apiUrl("/api/v1/profile/workspace/inbox"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: text, source: "annotation", context: { session_id: sessionIdRef.current || null } }),
        }).catch(() => undefined);
      }

      const client = ensureClient();
      if (!client.connected) client.connect();

      const attemptSend = (payload: StartTurnMessage, attempt = 0) => {
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
        window.setTimeout(() => attemptSend(payload, attempt + 1), 200);
      };
      // Resolve a compact snapshot at send time. The visible user message stays
      // clean; only the coach receives task/attempt/memory context.
      void apiFetch(apiUrl("/api/v1/annotation/coach-context"), { cache: "no-store" })
        .then(async (response) => response.ok ? response.json() : null)
        .catch(() => null)
        .then((context) => {
          const contextText = context
            ? `\n\n[系统提供的当前学习上下文，请勿逐字复述]\n${JSON.stringify(context)}\n[学生问题]\n${text}`
            : text;
          const payload: StartTurnMessage = {
            type: "message",
            content: contextText,
            session_id: sessionIdRef.current || null,
            capability: "chat",
            language: readStoredLanguage(),
            persona: "annotation-coach",
          };
          attemptSend(payload);
        });
    },
    [sending, hint, t, ensureClient],
  );

  const send = useCallback(() => {
    sendText(input);
  }, [input, sendText]);

  // PetPhrase copy_item 借鉴：点 chip → 发送 + wave flash + ✓ 高亮 800ms
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const copiedTimerRef = useRef<number | null>(null);

  const sendQuickPhrase = useCallback(
    (phrase: QuickPhrase) => {
      if (sending) return; // 忙时不排队，静默忽略（快捷语不抢焦点）
      setQuickUses((prev) => ({
        ...prev,
        [phrase.key]: (prev[phrase.key] ?? 0) + 1,
      }));
      sendText(phrase.label, { showUserMessage: true });
      flashCoach(); // H2 wave flash
      if (copiedTimerRef.current) window.clearTimeout(copiedTimerRef.current);
      setCopiedKey(phrase.key);
      copiedTimerRef.current = window.setTimeout(() => {
        setCopiedKey(null);
        copiedTimerRef.current = null;
      }, 800);
    },
    [sending, sendText, flashCoach],
  );

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
      if (copiedTimerRef.current) window.clearTimeout(copiedTimerRef.current);
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
  const coachImage = sending
    ? "/coach/coach-thinking.png"
    : hint
      ? "/coach/coach-reminder.png"
      : flashActive
        ? "/coach/coach-success.png"
        : "/coach/coach-default.png";

  return (
    <div className="fixed z-50 flex flex-col items-end gap-3" style={{ right: position.right, bottom: position.bottom }}>
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
            <img src={coachImage} alt="标注教练星仔" className="h-8 w-8 rounded-full bg-white object-cover" />
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
            {cards.map((card, ci) => (
              <div key={`card-${ci}`} className="max-w-[85%]">
                <ChatChartCard chart={card} />
              </div>
            ))}
            {sending && (
              <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-[var(--border)] bg-[var(--background)] px-3.5 py-2.5 text-[13px] text-[var(--muted-foreground)]">
                思考中…
              </div>
            )}
            <div ref={listEndRef} />
          </div>

          {/* PetPhrase 借鉴：快捷语 chip 栏，点 chip 一键发送 */}
          <div className="border-t border-[var(--border)] px-3 pt-2">
            <div className="flex flex-wrap gap-2.5 pb-2">
              {QUICK_PHRASES.map((group) => {
                const sorted = sortByUses(group.phrases, quickUses);
                return (
                  <div key={group.group} className="flex flex-wrap items-center gap-1.5">
                    {sorted.map((phrase) => {
                      const active = copiedKey === phrase.key;
                      return (
                        <button
                          key={phrase.key}
                          onClick={() => sendQuickPhrase(phrase)}
                          disabled={sending}
                          className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                            active
                              ? "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]"
                              : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-[var(--primary)] hover:text-[var(--foreground)]"
                          }`}
                        >
                          {active ? `✓ ${t(phrase.key, phrase.label)}` : t(phrase.key, phrase.label)}
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
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
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onClick={() => {
          if (suppressClickRef.current) {
            suppressClickRef.current = false;
            return;
          }
          setOpen((v) => !v);
        }}
        className={`relative flex h-14 w-14 items-center justify-center rounded-full border-2 ${ringClass} bg-[var(--primary)] text-2xl shadow-lg transition-transform hover:scale-105`}
      >
        <span className="pointer-events-none absolute inset-0 animate-ping rounded-full bg-[var(--primary)] opacity-30" />
        <img src={coachImage} alt="打开标注教练" className="relative h-12 w-12 rounded-full bg-white object-cover" />
      </button>
    </div>
  );
}
