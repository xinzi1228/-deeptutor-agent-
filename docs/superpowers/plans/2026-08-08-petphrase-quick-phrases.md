# 第七轮优化实现计划：Coach 快捷语面板（借鉴 PetPhrase）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 借鉴 PetPhrase「点 chip → 动画反馈」交互，给 AnnotationCoach 加快捷语 chip 栏——一键发送教学快捷语（表扬/提示/推进/求助）+ 使用频率排序 + wave flash + ✓ 高亮反馈。

**Architecture:** 全在 `web/components/annotation/AnnotationCoach.tsx`。`QUICK_PHRASES` 常量（i18n 本地化）+ `useCount`（localStorage 持久化，点击不重排）+ `sendQuickPhrase`（复用 send 的 WS 核心，抽成 `sendText` helper）+ 点 chip → `flashCoach()` + chip `copied` 800ms ✓。

**Tech Stack:** TypeScript React / i18n JSON。参考 clone：`%TEMP%\opencode\refs\petphrase\PetPhrase\`（logic.rs layout_group / main.rs copy_item）。

---

## 背景（已核实）

- `AnnotationCoach.tsx`（514 行）：`send()`（L242-285+，含忙时提示/乐观锁/attemptSend）、`flashCoach()`（H2）、`ensureClient()`、`CoachBubble`、`handleEvent`（含 tool_result chart → cards）。**无快捷语机制。**
- i18n：`web/locales/zh/app.json` + `en/app.json`（flat key，`annotation.coach.*` 命名空间，字母序）。
- 现有 localStorage key 模式：`annotation.coach.shortcuts.dismissed`（SHORTCUT_DISMISS_KEY）。

## 任务分解

### Task 1: 抽 `sendText` helper（复用 send 核心）

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`

- [ ] **Step 1: 抽取发送核心**——把 `send()`（L242-285+）的发送主体抽成 `sendText`，`send()` 变薄壳：

```tsx
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
    setCards([]);

    const client = ensureClient();
    if (!client.connected) client.connect();

    const payload: StartTurnMessage = {
      type: "message",
      content: text,
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
  },
  [sending, hint, t, ensureClient],
);
```

- [ ] **Step 2: 改 `send()` 为薄壳**——`send()` 调 `sendText`：

```tsx
const send = useCallback(() => {
  sendText(input);
}, [input, sendText]);
```

- [ ] **Step 3: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 4: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "refactor: 抽取 sendText 发送核心 (⑦轮 PetPhrase)"
```

---

### Task 2: QUICK_PHRASES 常量 + useCount 排序

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`

- [ ] **Step 1: 加快捷语常量**——`MOOD_EMOJI` 常量后（L64 附近）：

```tsx
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
```

- [ ] **Step 2: 加 useCount state + localStorage 读写**——`showShortcuts` state（L162 附近）后：

```tsx
const [quickUses, setQuickUses] = useState<Record<string, number>>(() => {
  try {
    const raw = window.localStorage.getItem(QUICK_USES_KEY);
    return raw ? (JSON.parse(raw) as Record<string, number>) : {};
  } catch {
    return {};
  }
});
```

- [ ] **Step 3: 加排序 helper**——`detectCoachMood` 后：

```tsx
// PetPhrase 借鉴：同组内按使用频率降序（同频保预设序），点击不重排
function sortByUses(phrases: QuickPhrase[], uses: Record<string, number>): QuickPhrase[] {
  return [...phrases].sort((a, b) => (uses[b.key] ?? 0) - (uses[a.key] ?? 0));
}
```

- [ ] **Step 4: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 5: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "feat: Coach 快捷语常量 + 使用频率排序 (⑦轮)"
```

---

### Task 3: chip 栏渲染 + sendQuickPhrase + 反馈

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`

- [ ] **Step 1: 加 sendQuickPhrase + copied 状态**——`send` 后：

```tsx
const [copiedKey, setCopiedKey] = useState<string | null>(null);
const copiedTimerRef = useRef<number | null>(null);

// PetPhrase copy_item 借鉴：点 chip → 发送 + wave flash + ✓ 高亮 800ms
const sendQuickPhrase = useCallback(
  (phrase: QuickPhrase) => {
    if (sending) return; // 忙时不排队，静默忽略（快捷语不抢焦点）
    setQuickUses((prev) => {
      const next = { ...prev, [phrase.key]: (prev[phrase.key] ?? 0) + 1 };
      try {
        window.localStorage.setItem(QUICK_USES_KEY, JSON.stringify(next));
      } catch {
        // localStorage 不可用则仅内存
      }
      return next;
    });
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
```

- [ ] **Step 2: 渲染 chip 栏**——输入框 div（L335-358，`<div className="flex items-center gap-2 border-t...">`）之前加：

```tsx
{/* PetPhrase 借鉴：快捷语 chip 栏，点 chip 一键发送 */}
<div className="border-t border-[var(--border)] px-3 pt-2">
  <div className="flex flex-wrap gap-1.5 pb-2">
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
                className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
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
```

> 说明：`t(phrase.key, phrase.label)` 用 i18n key + 中文兜底。分组间留 gap 但整体流式。

- [ ] **Step 3: cleanup copied timer on unmount**——struggle cleanup（H2 已加 flashTimer）处加：

```tsx
if (copiedTimerRef.current) window.clearTimeout(copiedTimerRef.current);
```

- [ ] **Step 4: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 5: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "feat: Coach 快捷语 chip 栏 + wave flash + ✓ 反馈 (⑦轮 PetPhrase)"
```

---

### Task 4: i18n keys

**Files:**
- Modify: `web/locales/zh/app.json` + `web/locales/en/app.json`

- [ ] **Step 1: 加 zh keys**——`annotation.coach.*` 命名空间字母序插入：

```json
"annotation.quick.praise.1": "夸一下",
"annotation.quick.praise.2": "画得不错",
"annotation.quick.praise.3": "进步了",
"annotation.quick.hint.1": "给点思路",
"annotation.quick.hint.2": "我卡住了",
"annotation.quick.advance.1": "换一题",
"annotation.quick.advance.2": "再练一遍",
"annotation.quick.help.1": "帮我看看",
"annotation.quick.help.2": "评分规则"
```

en 对应英文。

- [ ] **Step 2: 验证 JSON**

```
node -e "JSON.parse(require('fs').readFileSync('web/locales/zh/app.json','utf8')); JSON.parse(require('fs').readFileSync('web/locales/en/app.json','utf8')); console.log('JSON ok')"
```

- [ ] **Step 3: Commit**

```bash
git add web/locales/zh/app.json web/locales/en/app.json
git commit -m "feat: Coach 快捷语 i18n keys (⑦轮)"
```

---

## 验证
- 前端：`cd web && npx tsc --noEmit`（清代理）+ eslint
- 冒烟（可选）：`start_all.bat` → annotation 页 → Coach 气泡底部出现快捷语 chip → 点「夸一下」→ 发送 + 头像 wave flash + chip ✓ 高亮 → Coach 响应；再点常用 chip → 排序更新（localStorage 持久化）

## 提交（仅 commit，不 push）
- 按 Task 拆 4 个 commit，大版本完成后等用户指示统一 push。**不触碰 ChatMessages.tsx / annotation_tool*.html / 后端 / PERSONA**。
