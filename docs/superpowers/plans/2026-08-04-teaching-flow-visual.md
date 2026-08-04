# 教学流程可视化实施计划（6 步状态图）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Progress 页「记录」Tab 新增「教学流程」面板，横向 6 步状态条高亮当前步 + 阻塞原因，让 TeachingFlowEngine 的协议运行可视化。

**Architecture:** 后端 `GET /api/v1/profile/teaching-flow` 只读 flow_state.json（TeachingFlowEngine 无文件时返回 fresh 空态）；前端 `TeachingFlowPanel.tsx` 渲染横向 6 步条（done/in_progress/blocked/pending 颜色），Progress 页 Promise.all 接入。

**Tech Stack:** Python FastAPI, Next.js, react-i18next。

**Spec:** `docs/specs/teaching-flow-visual-design.md`（已提交 `16ccbea3`）

---

### Task 1: 后端 `GET /api/v1/profile/teaching-flow`

**Files:**
- Modify: `deeptutor/api/routers/profile.py`
- Test: `tests/api/test_profile_teaching_flow.py`

- [ ] **Step 1: 写失败测试**

Read `deeptutor/api/routers/profile.py` (the /decisions and /trace-log endpoints) and `deeptutor/services/teaching_flow.py` (TeachingFlowEngine.get_state, FLOW_STEPS). Then create `tests/api/test_profile_teaching_flow.py`:

```python
"""teaching-flow endpoint — current 6-step protocol state (read-only)."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_teaching_flow_no_file_returns_empty():
    from deeptutor.api.routers.profile import teaching_flow_state

    result = await teaching_flow_state()
    assert "has_flow" in result
    assert result["has_flow"] is False
    assert "steps" in result
    assert "current_step" in result


@pytest.mark.asyncio
async def test_teaching_flow_with_state(tmp_path, monkeypatch):
    from deeptutor.api.routers.profile import teaching_flow_state

    # Point the engine at a temp flow_state.json with a started task.
    state_path = tmp_path / "flow_state.json"
    from deeptutor.services.teaching_flow import TeachingFlowEngine

    engine = TeachingFlowEngine(path=state_path)
    engine.start_task("task1")

    monkeypatch.setattr(
        "deeptutor.api.routers.profile.TeachingFlowEngine",
        lambda: TeachingFlowEngine(path=state_path),
    )

    result = await teaching_flow_state()
    assert result["has_flow"] is True
    assert result["task_id"] == "task1"
    assert result["current_step"] == "show_task"
    assert "expert" in result
```

NOTE: read profile.py to see how `TeachingFlowEngine` would be imported (the endpoint does `from deeptutor.services.teaching_flow import TeachingFlowEngine` inside the function per the spec — if so, monkeypatch target is `deeptutor.services.teaching_flow.TeachingFlowEngine`, NOT profile's). Read the endpoint implementation in the plan (Step 3) and match the monkeypatch target to how it actually loads. The cleanest: the endpoint uses `from deeptutor.services.teaching_flow import TeachingFlowEngine` inside the function, so monkeypatch `deeptutor.services.teaching_flow.TeachingFlowEngine` with a factory that returns an engine pointed at tmp_path.

Run to verify FAIL:
`cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_profile_teaching_flow.py -v 2>&1 | Select-Object -Last 6`
Expected: FAIL (ImportError: teaching_flow_state not defined)

- [ ] **Step 2: 实现端点**

Add to `deeptutor/api/routers/profile.py` (near /trace-log):

```python
@router.get("/teaching-flow")
async def teaching_flow_state() -> dict[str, Any]:
    """当前教学流程 6 步状态（TeachingFlowEngine flow_state.json 只读）。"""
    from deeptutor.services.teaching_flow import TeachingFlowEngine

    state = TeachingFlowEngine().get_state()
    return {
        "has_flow": bool(state.get("task_id")),
        "task_id": state.get("task_id"),
        "current_step": state.get("current_step"),
        "expert": state.get("expert"),
        "blocked": state.get("blocked"),
        "steps": state.get("steps", {}),
    }
```

IMPORTANT: read the actual profile.py imports first — `dict[str, Any]` needs `Any` imported (it likely already is). `TeachingFlowEngine` is imported inside the function (avoids top-level cycle). Verify `TeachingFlowEngine().get_state()` returns `{task_id, current_step, expert, blocked, steps}` — read teaching_flow.py to confirm the state shape (it has these keys per earlier exploration).

- [ ] **Step 3: 运行测试确认通过**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_profile_teaching_flow.py -v 2>&1 | Select-Object -Last 6`
Expected: PASS.

- [ ] **Step 4: Ruff + Commit**

Ruff: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m ruff check deeptutor/api/routers/profile.py tests/api/test_profile_teaching_flow.py`

```bash
git add deeptutor/api/routers/profile.py tests/api/test_profile_teaching_flow.py
git commit -m "feat: GET /api/v1/profile/teaching-flow 教学流程6步状态 (只读)"
```

---

### Task 2: 前端 TeachingFlowPanel

**Files:**
- Modify: `web/lib/learning-stats-api.ts`（加 getTeachingFlow + 类型）
- Create: `web/components/learning-stats/TeachingFlowPanel.tsx`
- Modify: `web/app/(workspace)/progress/page.tsx`（Promise.all 接入 + 渲染）

- [ ] **Step 1: API 客户端**

In `web/lib/learning-stats-api.ts` add (following existing patterns):

```ts
export type TeachingFlowStep = {
  status: string;
  ts?: string | null;
  f1?: number | null;
  readiness?: string | null;
};

export type TeachingFlowState = {
  has_flow: boolean;
  task_id?: string | null;
  current_step?: string | null;
  expert?: string | null;
  blocked?: {
    step: string; reason: string; next_action: string;
  } | null;
  steps?: Record<string, TeachingFlowStep>;
};

export async function getTeachingFlow(): Promise<TeachingFlowState> {
  const res = await fetch("/api/v1/profile/teaching-flow", { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to load teaching flow: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: TeachingFlowPanel 组件**

Create `web/components/learning-stats/TeachingFlowPanel.tsx`:

```tsx
"use client";

import { GitBranch } from "lucide-react";
import type { TeachingFlowState } from "@/lib/learning-stats-api";

const STEP_ORDER = ["select_task", "show_task", "waiting", "evaluate", "feedback", "record"];

const STEP_LABELS: Record<string, string> = {
  select_task: "选任务", show_task: "展示任务", waiting: "等待提交",
  evaluate: "评测", feedback: "反馈", record: "记录",
};

const STEP_STATUS_STYLE: Record<string, string> = {
  done: "bg-green-500 text-white",
  in_progress: "bg-blue-500 text-white ring-2 ring-blue-300",
  blocked: "bg-red-500 text-white",
  pending: "bg-[var(--border)] text-[var(--muted-foreground)]",
};

export function TeachingFlowPanel({ flow }: { flow: TeachingFlowState | null }) {
  if (!flow || !flow.has_flow) {
    return (
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-1 flex items-center gap-1.5">
          <GitBranch className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
          <h3 className="text-sm font-semibold">教学流程</h3>
        </div>
        <p className="text-xs text-[var(--muted-foreground)]">
          暂无进行中的任务——和教练开始练习后，这里会显示 6 步教学进度。
        </p>
      </div>
    );
  }

  const steps = flow.steps ?? {};
  const blocked = flow.blocked;

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <GitBranch className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
        <h3 className="text-sm font-semibold">教学流程</h3>
        <span className="ml-auto text-xs text-[var(--muted-foreground)]">
          {flow.task_id ? `任务 ${flow.task_id}` : "进行中"}
          {flow.expert ? ` · 专家: ${flow.expert}` : ""}
        </span>
      </div>
      <div className="flex items-center gap-1">
        {STEP_ORDER.map((step, idx) => {
          const meta = steps[step] ?? {};
          const style = STEP_STATUS_STYLE[meta.status ?? "pending"] ?? STEP_STATUS_STYLE.pending;
          return (
            <div key={step} className="flex flex-1 items-center gap-1">
              <div className="flex flex-1 flex-col items-center gap-1">
                <div className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${style}`}>
                  {idx + 1}
                </div>
                <span className="text-[10px] text-[var(--muted-foreground)]">{STEP_LABELS[step]}</span>
              </div>
              {idx < STEP_ORDER.length - 1 && (
                <div className={`h-px flex-1 ${meta.status === "done" ? "bg-green-500/60" : "bg-[var(--border)]"}`} />
              )}
            </div>
          );
        })}
      </div>
      {blocked && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-[var(--muted-foreground)]">
          <span className="font-semibold text-red-500">阻塞</span>：{blocked.reason}
          <span className="ml-2">建议：{blocked.next_action}</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 接入 progress/page.tsx**

In `web/app/(workspace)/progress/page.tsx`:
1. Import `getTeachingFlow, type TeachingFlowState`
2. Add `const [teachingFlow, setTeachingFlow] = useState<TeachingFlowState | null>(null)`
3. Add `getTeachingFlow().catch(() => null)` to Promise.all (destructure), set state
4. In the 记录 tab, render `<TeachingFlowPanel flow={teachingFlow} />` ABOVE the 教学轨迹 Timeline

- [ ] **Step 4: tsc + Commit**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors

```bash
git add web/lib/learning-stats-api.ts web/components/learning-stats/TeachingFlowPanel.tsx "web/app/(workspace)/progress/page.tsx"
git commit -m "feat: 教学流程面板 (6步状态条高亮当前步+阻塞)"
```

---

### Task 3: 验证

**Files:** none

- [ ] **Step 1: 后端测试**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_profile_teaching_flow.py -q 2>&1 | Select-Object -Last 3`
Expected: PASS.

- [ ] **Step 2: 前端 tsc + build**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors; `Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY -ErrorAction SilentlyContinue; npx next build 2>&1 | Select-Object -Last 4` → succeeds

- [ ] **Step 3: Playwright 冒烟**

With backend (8001) + frontend (3782) running:
1. Navigate to `/progress` → 记录 tab → 教学流程 panel shows "暂无进行中的任务" (empty state, since no flow_state.json in demo)
2. In a chat session, run through task1 (submit a bbox or use annotation flow) to generate flow_state.json — OR simpler: create a flow_state.json via a quick python command `TeachingFlowEngine().start_task("task1")` so the panel has data
3. Reload progress → 记录 tab → panel shows 6-step bar with step 2 (展示任务) highlighted, expert shown
4. Screenshot for record

- [ ] **Step 4: 提交修复（如有）**

If smoke found issues, fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §3 后端端点 → Task 1
- §4 前端面板 → Task 2
- §5 测试 → Task 3
✅ 全覆盖

**2. Placeholder scan:** 所有步骤含具体代码/命令。Task 1 强调 monkeypatch 目标匹配实际 import。✅

**3. Type consistency:** `TeachingFlowState`/`TeachingFlowStep` 类型 Task 2 Step 1 定义，Step 2/3 引用一致；端点返回 `{has_flow, task_id, current_step, expert, blocked, steps}` 与前端类型一致；`TeachingFlowEngine` 在端点函数内 import（避免循环）。✅

**已知风险（沿用 spec §7）：**
1. demo 无 flow_state.json → 空态展示（合理）；冒烟用 `TeachingFlowEngine().start_task()` 临时生成验证
2. `get_state()` 文件损坏时 fallback fresh（已有容错）
