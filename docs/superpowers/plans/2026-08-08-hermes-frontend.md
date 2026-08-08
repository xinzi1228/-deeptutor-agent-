# 第六轮优化实现计划：AnnotationCoach 前端 UX 增强（借鉴 hermes-agent）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 借鉴 `NousResearch/hermes-agent` 三大前端机制，增强 AnnotationCoach：H2 状态环 + 瞬态情绪 flash（升级 C2 mood）、H3 乐观忙锁 + 忙时提示、H1 分段式卡片渲染（卡片落在叙述间）。

**Architecture:** 全在 `web/components/annotation/AnnotationCoach.tsx`（独立组件）。H2 = 从现有信号（sending/messages/wait_for_input）派生状态环 + `flash` TTL 瞬态层；H3 = 提交瞬间同步置忙；H1 = handleEvent 处理 tool_result chart → `cards[]` 数组，渲染插在叙述间（复用 ChatChartCard）。

**Tech Stack:** TypeScript React / i18n JSON。参考 clone：`%TEMP%\opencode\refs\hermes\hermes-agent\`（turnController.ts/petFlashStore.ts/state.py/submissionCore.ts）。

---

## 背景（已核实）

- `AnnotationCoach.tsx`（435 行）：`CoachMessage{role, content}`、`CoachBubble`（含 mood 检测，L73-91）、`handleEvent`（session/done/error/content，L139-164）、`send()`（L115-150，`sending` 布尔）、struggle 轮询、问候语（上轮 C3 已改陪伴化）。
- `ChatChartCard`（ChatMessages 同目录）：`ChartData` 联合类型（scorecard/radar/progress/graph/quiz_card/ls_task_card），`export function ChatChartCard`。chart 契约 = `tool_result.metadata.tool_metadata.chart`。
- `WAIT_FOR_INPUT` 事件（stream.py:34）——ask_user 暂停时发出，AnnotationCoach 可监听（现在没监听）。
- `isStreaming`/`sending`：AnnotationCoach 独立 WS，有自己的 `sending` 状态。

## 任务分解

### Task 1: H2——Coach 状态环 + 瞬态情绪 flash

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`

- [ ] **Step 1: 加状态环类型 + 派生函数**——`CoachMood` 类型后（L27 附近）：

```tsx
type CoachStatus = "idle" | "working" | "waiting-input" | "flash";

interface CoachFlash {
  status: CoachStatus;
  until: number;
}

// Hermes 宠物状态机借鉴（state.py derive_pet_state 优先级）：
// waiting-input(学生回合) > working(发送中) > idle；flash 瞬态覆盖稳态。
function deriveCoachStatus(sending: boolean, awaitingInput: boolean): CoachStatus {
  if (awaitingInput) return "waiting-input";
  if (sending) return "working";
  return "idle";
}

const STATUS_RING: Record<string, string> = {
  idle: "", // 无环
  working: "border-[var(--primary)]/40 border-t-[var(--primary)]",
  "waiting-input": "border-[var(--muted-foreground)]/40 border-t-[var(--muted-foreground)]",
  flash: "border-[var(--primary)]/60 border-t-[var(--primary)]",
};
```

- [ ] **Step 2: 加状态 + flash state**——组件内（`const [sending, setSending] = useState(false)` 附近）：

```tsx
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
```

- [ ] **Step 3: handleEvent 扩展**——在 `done` 分支（L145-148）加 flash：

```tsx
if (event.type === "done") {
  setSending(false);
  flashCoach(); // 回合完成 → wave flash（Hermes just_completed→WAVE 借鉴）
  return;
}
```

在 `error` 分支（L149-156）加失败 flash：

```tsx
if (event.type === "error") {
  setSending(false);
  setMessages((prev) => [
    ...prev,
    { role: "coach", content: event.content || "抱歉，我遇到了一点问题，请稍后再试。" },
  ]);
  flashCoach(); // 错误也 flash（Hermes error→FAILED 借鉴，emoji 走 mood）
  return;
}
```

在 `content` 分支前加 `wait_for_input` 处理：

```tsx
if (event.type === "wait_for_input") {
  setAwaitingInput(true);
  return;
}
```

在 `done` 分支也重置 awaitingInput：

```tsx
if (event.type === "done") {
  setSending(false);
  setAwaitingInput(false);
  flashCoach();
  return;
}
```

> 注意：`wait_for_input` 在 ask_user 暂停时发出；`done` 是回合结束。学生回合（waiting-input）状态环 = 灰环。

- [ ] **Step 4: 浮动按钮加状态环**——渲染区（L362-369 的 `button` 加状态类）：

```tsx
const coachStatus = deriveCoachStatus(sending, awaitingInput);
const flashActive = flash !== null && Date.now() < flash.until;
const ringClass = flashActive ? STATUS_RING.flash : STATUS_RING[coachStatus];

<button
  aria-label="toggle annotation coach"
  onClick={() => setOpen((v) => !v)}
  className={`relative flex h-14 w-14 items-center justify-center rounded-full border-2 ${ringClass} bg-[var(--primary)] text-2xl shadow-lg transition-transform hover:scale-105`}
>
  <span className="pointer-events-none absolute inset-0 animate-ping rounded-full bg-[var(--primary)] opacity-30" />
  <span className="relative">🤖</span>
</button>
```

- [ ] **Step 5: 清理 flash timer on unmount**——struggle 轮询的 cleanup（L196-198）加：

```tsx
return () => {
  cancelled = true;
  window.clearInterval(timer);
  if (flashTimerRef.current) window.clearTimeout(flashTimerRef.current);
  clientRef.current?.disconnect();
  clientRef.current = null;
};
```

- [ ] **Step 6: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 7: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "feat: Coach 状态环 + 瞬态情绪 flash (⑥轮H2 hermes借鉴)"
```

---

### Task 2: H3——乐观忙锁 + 忙时提示

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`

- [ ] **Step 1: send() 同步置忙 + 忙时提示**——`send`（L115-150）改为：

```tsx
const send = useCallback(() => {
  const content = input.trim();
  if (!content) return;
  // Hermes markSubmitting 借鉴：同步置忙，防双击竞态
  if (sending) {
    setMessages((prev) => [
      ...prev,
      { role: "coach", content: "我在分析上一个问题，稍等一下～" },
    ]);
    return;
  }
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
```

> 关键改动：① `sending` 检查提前到函数开头（原 L117 `if (!content || sending) return` 拆成两步——无内容直接 return，忙时弹提示）；② 忙时提示文案（教学陪伴风格）。

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "feat: Coach 乐观忙锁 + 忙时提示 (⑥轮H3)"
```

---

### Task 3: H1——分段式卡片渲染

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`
- Modify: `web/locales/zh/app.json` + `web/locales/en/app.json`（如需新 key）

- [ ] **Step 1: handleEvent 加 tool_result chart 处理**——`content` 分支后（L164 附近）加：

```tsx
if (event.type === "tool_result") {
  const meta = (event.metadata ?? {}) as Record<string, unknown>;
  const toolMeta = (meta.tool_metadata ?? {}) as Record<string, unknown>;
  const chart = toolMeta.chart as ChartData | undefined;
  if (chart) {
    setCards((prev) => [...prev, chart]);
  }
  return;
}
```

- [ ] **Step 2: 加 cards state**——`const [messages, setMessages] = useState<CoachMessage[]>([]);` 后：

```tsx
const [cards, setCards] = useState<ChartData[]>([]);
```

> import：`import { ChatChartCard, type ChartData } from "@/components/chat/home/ChatChartCard";`。**若 `ChartData` 未从 ChatChartCard.tsx 导出，先加 `export type ChartData`（该文件 L5 的 `type ChartData = ...` 改为 `export type ChartData`）。**

- [ ] **Step 3: 渲染 cards 在叙述间**——消息渲染区（`messages.map` 之后、`sending` 占位之前）加：

```tsx
{cards.map((card, ci) => (
  <div key={`card-${ci}`} className="max-w-[85%]">
    <ChatChartCard chart={card} />
  </div>
))}
```

> 说明：卡片按 tool_result 到达顺序累积在 `cards[]`，渲染在消息流末尾（当前版本）。「落在叙述间」的完整分段（卡片紧跟对应叙述）需要消息级分段——**MVP 先做"卡片独立块渲染在消息流中"**（区别于当前完全混在文本气泡），叙述间精确插入列为 P2。

- [ ] **Step 4: 验证 tsc + eslint**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
cd web; npx eslint components/annotation/AnnotationCoach.tsx
```

Expected: 无新错误（预存在 warning 可接受）。

- [ ] **Step 5: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx web/components/chat/home/ChatChartCard.tsx
git commit -m "feat: Coach 卡片分段渲染 (⑥轮H1)"
```
（若 ChatChartCard 未导出 ChartData 则加 `export type ChartData`。）

---

## 验证
- 前端：`cd web && npx tsc --noEmit`（清代理）+ eslint
- 冒烟（可选）：`start_all.bat` → annotation 页 → Coach：发送中头像转圈环（working）、ask_user 时灰环（waiting-input）、回合完成头像 flash 环、忙时再输入弹提示、render_ui 卡片独立渲染

## 提交（仅 commit，不 push）
- 按 Task 拆 3 个 commit，大版本完成后等用户指示统一 push。**不触碰 annotation_tool*.html / ChatMessages.tsx / 后端**。
