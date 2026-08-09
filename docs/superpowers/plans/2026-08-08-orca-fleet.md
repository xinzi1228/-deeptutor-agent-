# 第八轮优化实现计划 B：专家 Fleet 看板（借鉴 stablyai/orca AgentKanbanBoard）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 delegate 专家系统可视化——消息流内新增**专家 Fleet 看板**（每专家一行：状态点 + 专家名 + 实时状态 + 结果摘要），借鉴 Orca AgentKanbanBoard + dashboard-snapshot 契约。复用前端 O1 的 `AgentStateDot` 原语。纯前端、零后端改动。

**Architecture:** 新增 `web/components/chat/home/ExpertFleetBoard.tsx`（纯展示组件，接收 `events: StreamEvent[]` 扫描 delegate 事件），在 `ChatMessages.tsx` 的 `AssistantMessage` 中渲染（每助手消息一个 board，聚合该消息内全部 delegate 调用）。

**Tech Stack:** TypeScript React / Tailwind v4 / lucide-react。参考：`%TEMP%\opencode\refs\orca\orca\src\renderer\src\components\AgentKanbanBoard.tsx`。

---

## 背景（已核实，explore 子代理）

- **delegate 事件形态**（全在 `msg.events`，按 `call_id` 分组）：
  1. `tool_call` — `metadata.args.expert_id` + `tool_name:"delegate_to_expert"` → **start 信号**（working）
  2. `progress`（`trace_kind:"tool_log"`、`call_kind:"subagent_delegate"`、`query:<expert_id>`）— "专家 X 分析中…" → **实时状态文本**
  3. `progress`（`call_state:"complete"`/`"error"`）— 完成标记
  4. `tool_result` — `content` = 结论文本，`metadata.tool_metadata.delegate = {expert, result}` → **done + 摘要**
- **StreamEvent 类型**（`web/lib/unified-ws.ts:34-44`）：`{type, source, stage, content, metadata, session_id, turn_id, seq, timestamp}`。
- **StreamEventType**：`"tool_call"`/`"tool_result"`/`"progress"` 均为合法值。
- **AgentStateDot**（`web/components/common/AgentStateDot.tsx`，已实现）：`AgentDotState` = working/done/waiting/blocked/failed/idle；`AgentStateDot` + `agentStateLabel` 具名导出。
- **ChatMessages.tsx**：`AssistantMessage`（L279-543）是渲染入口；`MessageItem`/`ChatMessageItem` 含 `events?: StreamEvent[]`。
- **专家 id**：`learning_planner`/`task_guide`/`grading_expert`/`struggle_detective`/`report_analyst`/`session_steward`。

## 任务分解

### Task 1: 新建 `ExpertFleetBoard.tsx`

**Files:**
- Create: `web/components/chat/home/ExpertFleetBoard.tsx`

- [ ] **Step 1: 创建组件**——纯展示，扫描 `events[]` 派生专家状态：

```tsx
"use client";

import { useMemo } from "react";

import { AgentStateDot, agentStateLabel } from "@/components/common/AgentStateDot";
import type { StreamEvent } from "@/lib/unified-ws";

export interface ExpertTask {
  expertId: string;
  /** human-readable 专家名（含中文标签映射） */
  label: string;
  state: "working" | "done" | "failed" | "waiting";
  /** 最新实时状态文本（progress） */
  status?: string;
  /** 结论摘要（tool_result 内容前 120 字符） */
  summary?: string;
}

const EXPERT_LABELS: Record<string, string> = {
  learning_planner: "学习规划师",
  task_guide: "任务导引师",
  grading_expert: "评测专家",
  struggle_detective: "卡点侦探",
  report_analyst: "报告分析师",
  session_steward: "会话管家",
};

function summarize(content: string): string {
  const trimmed = content.replace(/^专家\s*\S+\s*结论[：:]\s*/u, "").trim();
  return trimmed.length > 120 ? `${trimmed.slice(0, 120)}…` : trimmed;
}

function expertStateFromEvents(expertId: string, events: StreamEvent[]): ExpertTask {
  const label = EXPERT_LABELS[expertId] ?? expertId;
  const progress = events.filter(
    (e) => e.type === "progress" && e.metadata?.query === expertId,
  );
  const latest = progress[progress.length - 1];
  const done = events.find(
    (e) => e.type === "tool_result" && (e.metadata as any)?.tool_metadata?.delegate?.expert === expertId,
  );
  if (done) {
    return {
      expertId,
      label,
      state: "done",
      status: "分析完成",
      summary: summarize(done.content || ""),
    };
  }
  return {
    expertId,
    label,
    state: "working",
    status: latest?.content,
  };
}

export function ExpertFleetBoard({ events, className = "" }: { events: StreamEvent[]; className?: string }) {
  const tasks = useMemo(() => {
    const calls = events.filter(
      (e) => e.type === "tool_call" && (e.metadata as any)?.tool_name === "delegate_to_expert",
    );
    return calls
      .map((c) => expertStateFromEvents((c.metadata as any)?.args?.expert_id, events))
      .filter((t) => t.expertId);
  }, [events]);

  if (tasks.length === 0) return null;

  return (
    <div className={`space-y-1.5 rounded-xl border border-[var(--border)] bg-[var(--muted)]/30 p-3 ${className}`}>
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--muted-foreground)]">
        <span className="inline-block size-1.5 rounded-full bg-[var(--primary)]" />
        专家协作看板
      </div>
      {tasks.map((task) => (
        <div
          key={task.expertId}
          className="flex items-start gap-2 rounded-lg bg-[var(--background)] px-2.5 py-2"
        >
          <span className="mt-0.5 shrink-0">
            <AgentStateDot state={task.state} size="sm" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-[13px] font-medium text-[var(--foreground)]">
                {task.label}
              </span>
              <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
                {agentStateLabel(task.state)}
              </span>
            </div>
            {task.state === "done" ? (
              task.summary && (
                <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
                  {task.summary}
                </p>
              )
            ) : (
              task.status && (
                <p className="mt-0.5 text-xs leading-relaxed text-[var(--muted-foreground)]">
                  {task.status}
                </p>
              )
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

> 说明：
> - `expertStateFromEvents`：优先找 tool_result（done + 摘要）；否则 working（用最新 progress 文本）。
> - 分组 key = `expert_id`（一次回合内同专家不会重复 delegate——实际每个 delegate 调用独立 expert，若同一专家被重复委托会合并显示，可接受）。
> - `(e.metadata as any)` 为 StreamEvent.metadata 是 `Record<string, unknown>`，取嵌套字段需断言。

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/chat/home/ExpertFleetBoard.tsx
git commit -m "feat: 专家 Fleet 看板组件 (⑧轮F1 orca借鉴)"
```

---

### Task 2: 挂载到 ChatMessages.AssistantMessage

**Files:**
- Modify: `web/components/chat/home/ChatMessages.tsx`

- [ ] **Step 1: 挂载组件**——在 `AssistantMessage` 内、`AssistantActivity` trace 之后渲染 ExpertFleetBoard（有 delegate 事件才显示，组件自身空态返回 null）：

```tsx
import ExpertFleetBoard from "@/components/chat/home/ExpertFleetBoard";
```

在 AssistantMessage 的 return 中（AssistantActivity 之后、branch dispatch 之前）加：

```tsx
{/* 专家 Fleet 看板：聚合该消息内 delegate 调用 */}
<ExpertFleetBoard events={message.events ?? []} className="mb-2" />
```

> 注意：确认 ExpertFleetBoard 用具名导出——按 Task 1 代码 `export function ExpertFleetBoard`，import 应为 `import { ExpertFleetBoard } from "..."`。以实际导出版本为准。

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/chat/home/ChatMessages.tsx
git commit -m "feat: ChatMessages 挂载专家 Fleet 看板 (⑧轮F1)"
```

---

### Task 3: 冒烟验证 + review

- [ ] **Step 1: 全量验证**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 0 错误。

- [ ] **Step 2: spec 审查**——对照设计文档 F1 逐项：
  - 状态点复用 AgentStateDot（working=amber spin / done=emerald check）✓
  - 状态桶语义：working/done（Needs You 即 ask_user 场景暂缺——delegate 不提问，可留 waiting 空状态）
  - 消息摘要 + 专家名中文标签 ✓
  - 零后端改动 ✓（未碰 delegate_expert_tool.py / StreamEventType）

- [ ] **Step 3: Commit（若有 review 修复）**

---

## 验证
- `cd web && npx tsc --noEmit`（清代理）
- 冒烟（可选，需服务在跑）：annotation 页委派学习规划师 → 看板出现 working 卡 → 完成后变 emerald check + 摘要

## 提交（仅 commit，不 push）
- 按 Task 拆 2-3 个 commit。**不触碰后端 / annotation_tool*.html**。
