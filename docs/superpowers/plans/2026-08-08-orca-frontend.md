# 第八轮优化实现计划：前端状态点原语 + 时长反馈规范（借鉴 stablyai/orca）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 借鉴 `stablyai/orca` 前端，新增共享状态点原语 + 统一状态词汇表（O1）+ 时长反馈规范（O2），对齐 Coach 状态环色值。

**Architecture:** O1 = 新建 `web/components/common/AgentStateDot.tsx`（AgentDotState 类型 + agentStateLabel + 渲染，跨组件共享），Coach 状态环（H2）色值对齐词汇表。O2 = ChatComposer/提交按钮加时长反馈（阶段标签 + 预占空间）。

**Tech Stack:** TypeScript React / Tailwind / lucide-react。参考 clone：`%TEMP%\opencode\refs\orca\orca\`（AgentStateDot.tsx / AgentWorkingSpinner.tsx / docs/STYLEGUIDE.md）。

---

## 背景（已核实）

- 现有 CSS 变量：`--primary`/`--destructive`/`--muted-foreground`（**无 `--success`**）。
- `web/components/common/` 有共享组件（AssistantResponse/StandardDialog/Tooltip 等）——AgentStateDot 放这里。
- Coach 状态环（H2，AnnotationCoach `STATUS_RING`）：working=primary 环 / waiting-input=muted 环 / idle=border 环 / flash=primary 环。**色值与 Orca 词汇表不同**（Orca: yellow=working/emerald=done/amber=waiting）。
- ChatComposer 提交按钮：`Loader2 animate-spin` + disabled，无 3s+ 阶段标签。

## 任务分解

### Task 1: O1——共享 AgentStateDot 原语

**Files:**
- Create: `web/components/common/AgentStateDot.tsx`

- [ ] **Step 1: 创建组件**——借鉴 Orca AgentStateDot，适配我们 CSS 变量（无 --success → 用 emerald-500/amber-500 等 Tailwind 色，与 lucide 图标配合）：

```tsx
"use client";

import { CircleCheck, Loader2, MessageCircleQuestion } from "lucide-react";
import { cn } from "@/lib/utils";

export type AgentDotState =
  | "working"
  | "blocked"
  | "waiting"
  | "failed"
  | "done"
  | "idle";

export function agentStateLabel(state: AgentDotState): string {
  switch (state) {
    case "working":
      return "Working";
    case "blocked":
      return "Blocked";
    case "waiting":
      return "Waiting for input";
    case "failed":
      return "Failed";
    case "done":
      return "Done";
    case "idle":
      return "Idle";
  }
}

interface AgentStateDotProps {
  state: AgentDotState;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Shared status-glyph primitive (borrowed from stablyai/orca AgentStateDot).
 * One vocabulary across every surface: working=spin, done=check,
 * waiting=question, blocked/failed=red dot, idle=gray dot.
 */
export function AgentStateDot({ state, size = "sm", className }: AgentStateDotProps) {
  const box = size === "md" ? "h-3.5 w-3.5" : "h-3 w-3";
  const inner = size === "md" ? "h-2.5 w-2.5" : "h-2 w-2";
  const icon = size === "md" ? "h-3.5 w-3.5" : "h-3 w-3";

  if (state === "working") {
    return (
      <span
        className={cn("inline-flex shrink-0 items-center justify-center", box, className)}
        aria-label={agentStateLabel(state)}
      >
        <Loader2 className={cn("h-2.5 w-2.5 animate-spin text-amber-500", icon)} aria-hidden="true" />
      </span>
    );
  }
  if (state === "done") {
    return (
      <span
        className={cn("inline-flex shrink-0 items-center justify-center", box, className)}
        aria-label={agentStateLabel(state)}
      >
        <CircleCheck className={cn("text-emerald-500", icon)} aria-hidden="true" />
      </span>
    );
  }
  if (state === "waiting") {
    return (
      <span
        className={cn("inline-flex shrink-0 items-center justify-center", box, className)}
        aria-label={agentStateLabel(state)}
      >
        <MessageCircleQuestion className={cn("text-amber-500", icon)} aria-hidden="true" />
      </span>
    );
  }
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center", box, className)}
      aria-label={agentStateLabel(state)}
    >
      <span
        className={cn(
          "block rounded-full",
          inner,
          state === "blocked" || state === "failed"
            ? "bg-red-500"
            : "bg-neutral-500/40",
        )}
      />
    </span>
  );
}
```

> 注：确认 `cn` 工具函数存在（`@/lib/utils`，shadcn 惯例）——若不存在用模板字符串拼接。

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/common/AgentStateDot.tsx
git commit -m "feat: 共享 AgentStateDot 状态点原语 (⑧轮O1 orca借鉴)"
```

---

### Task 2: O1——Coach 状态环对齐词汇表

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`（STATUS_RING 色值对齐）

- [ ] **Step 1: 对齐色值**——`STATUS_RING`（L48 附近）改为 Orca 词汇表（working=amber 环/done=emerald，保留 flash 强调）：

```tsx
const STATUS_RING: Record<string, string> = {
  idle: "border-[var(--border)]",
  working: "border-amber-500/40 border-t-amber-500",
  "waiting-input": "border-[var(--muted-foreground)]/40 border-t-[var(--muted-foreground)]",
  flash: "border-emerald-500/60 border-t-emerald-500",
};
```

> 说明：working 从 primary 改为 amber（对齐 Orca yellow=working）；flash 从 primary 改为 emerald（done 语义）；waiting-input 保持 muted（学生回合，非 agent 状态）。**保留 ring 样式，只改色值。**

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "feat: Coach 状态环对齐 Orca 状态词汇表 (⑧轮O1)"
```

---

### Task 3: O2——时长反馈规范（提交按钮）

**Files:**
- Modify: `web/components/chat/home/ChatComposer.tsx`（提交按钮加载反馈）

- [ ] **Step 1: 加阶段标签**——ChatComposer 的提交按钮（L833-836 Loader2 区域）加 3s+ 阶段标签。先读该文件确认结构，改造为：

```tsx
// Orca STYLEGUIDE 时长反馈：0-100ms 无反馈 / 100ms-1s 禁用 / 1-3s 禁用+spinner / 3s+ 阶段标签
// 预占空间：按钮固定宽高，标签不引起布局跳动
<button
  disabled={recorder.state === "transcribing" || isStreaming}
  className={`... h-8 w-8 shrink-0 ...`}
  aria-label={...}
>
  {isStreaming ? (
    <>
      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      <span className="sr-only">分析中…</span>
    </>
  ) : (
    <Send className="size-4" />
  )}
</button>
```

> 说明：MVP 加 `sr-only` 阶段标签（屏幕阅读器 + 语义）；完整"3s+ 显示文字阶段标签"需更大改动（按钮扩宽），列 P2。**预占空间已由 `h-8 w-8` 固定**（现结构已满足）。

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/chat/home/ChatComposer.tsx
git commit -m "feat: 提交按钮时长反馈阶段标签 (⑧轮O2)"
```

---

### Task 4: O3——单色设计纪律文档（可选）

**Files:**
- Create: `docs/frontend-design-discipline.md`

- [ ] **Step 1: 写纪律文档**——借鉴 Orca STYLEGUIDE，记录我们的前端设计规则：

```markdown
# 前端设计纪律（借鉴 stablyai/orca STYLEGUIDE）

## 单色安静
- 中性灰（--muted-foreground/--border）承载 chrome；**颜色只留给状态**。
- 状态色词汇表：working=amber / done=emerald / waiting=amber question / blocked=failed=red / idle=gray。
- 共享原语：`AgentStateDot`（web/components/common/）。

## 时长反馈（提交/加载）
- 0-100ms 无反馈；100ms-1s 仅禁用；1-3s 禁用+spinner；3s+ 阶段标签。
- **预占空间**：会变长的控件固定 width，避免点击瞬间跳动。
- 远端/慢操作：禁用立即绑定（防双击），可见加载延迟 ~200ms。

## Token 纪律
- 优先用现有 CSS 变量（--primary/--border/--muted-foreground）；需要色调用
  `color-mix(in srgb, var(--token) 12%, var(--background))`，**不造新 hex**。
- token 成对（surface + foreground 对比）。

## 兄弟组件一致性
- 相邻组件读作一个设计（同图标/同快捷键/同提交语义）。
- back-out（Cancel/Close）保持安静，视觉重量留给确认动作。
```

- [ ] **Step 2: Commit**

```bash
git add docs/frontend-design-discipline.md
git commit -m "docs: 前端设计纪律 (⑧轮O3 orca借鉴)"
```

---

## 验证
- 前端：`cd web && npx tsc --noEmit`（清代理）+ eslint
- 冒烟（可选）：Coach 状态环 working 变 amber；提交按钮加载有 sr-only 阶段标签；AgentStateDot 可复用

## 提交（仅 commit，不 push）
- 按 Task 拆 4 个 commit，大版本完成后等用户指示统一 push。**不触碰 annotation_tool*.html / 后端**。
