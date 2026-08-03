# 教学轨迹（Teaching Trace）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Progress 页「记录」Tab 的 Timeline 升级为可展开的教学回合链，显示每条练习的 F1/readiness + 卡住介入 + 关联决策。

**Architecture:** 后端新增 `GET /api/v1/profile/trace-log`（运行时聚合 records + decisions，按时间邻近匹配介入/决策）；前端 Timeline.tsx 练习行可展开显示因果，progress/page.tsx 的 Promise.all 增加获取。

**Tech Stack:** Python FastAPI, Next.js, react-i18next。

**Spec:** `docs/specs/teaching-trace-design.md`（已提交 `3b80c633`）

---

### Task 1: 后端 `GET /api/v1/profile/trace-log`

**Files:**
- Modify: `deeptutor/api/routers/profile.py`
- Test: `tests/api/test_profile_trace_log.py`

- [ ] **Step 1: 写失败测试**

Read `deeptutor/api/routers/profile.py` first to understand `_all_records`/`decisions`/`episodes` internals and the store API. Then create `tests/api/test_profile_trace_log.py`:

```python
"""trace-log endpoint — teaching-turn aggregation (records + decisions)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from deeptutor.services.session import get_path_service  # noqa: F401 (may not exist — check imports used by profile.py)


@pytest.mark.asyncio
async def test_trace_log_returns_records_sorted_desc():
    from deeptutor.api.routers.profile import trace_log

    result = await trace_log(limit=30)
    assert "traces" in result
    traces = result["traces"]
    # sorted by timestamp desc
    ts = [t["timestamp"] for t in traces]
    assert ts == sorted(ts, reverse=True)


@pytest.mark.asyncio
async def test_trace_log_annotation_exercise_has_f1_and_readiness():
    from deeptutor.api.routers.profile import trace_log

    result = await trace_log(limit=30)
    exercises = [t for t in result["traces"] if t["type"] == "annotation_exercise"]
    assert exercises, "expected at least one annotation_exercise in demo data"
    for ex in exercises[:3]:
        assert "f1" in ex
        assert "readiness" in ex
        assert "intervention" in ex  # key present (may be None)


@pytest.mark.asyncio
async def test_trace_log_limit():
    from deeptutor.api.routers.profile import trace_log

    result = await trace_log(limit=1)
    assert len(result["traces"]) <= 1
```

NOTE: read profile.py to see if its functions are async and how they get the store — adapt the test to the actual signatures. The demo data has 2 records (1 annotation_exercise + 1 diagnosis) and 3 decisions.

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_profile_trace_log.py -v 2>&1 | Select-Object -Last 6`
Expected: FAIL (ImportError: trace_log not defined)

- [ ] **Step 3: 实现 trace_log 端点**

Add to `deeptutor/api/routers/profile.py` (near the `/decisions` endpoint ~line 145). Read the existing `/decisions` and `/episodes` implementations first and reuse their store/loading logic:

```python
@router.get("/trace-log")
async def trace_log(limit: int = 30) -> dict[str, Any]:
    """Teaching-turn trace: records + time-adjacent decisions/interventions, desc by time."""
    # Reuse the same record loading as /episodes
    records = _all_records(scope="progress") or _all_records()
    # Reuse the same decision loading as /decisions — find how /decisions loads them and mirror it
    decisions = await decisions_loader()  # adapt to actual loader used by /decisions

    def _ts(ts_str):
        try:
            from datetime import datetime
            return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        except Exception:
            return None

    def _near(a, b, minutes=10):
        if not a or not b:
            return False
        diff = abs((a - b).total_seconds())
        return diff <= minutes * 60

    traces = []
    for r in records:
        rt = _ts(r.get("timestamp"))
        if not rt:
            continue
        trace = {
            "timestamp": r.get("timestamp"),
            "date": str(rt.date()) if rt else None,
            "type": r.get("type"),
            "task_id": r.get("task_id"),
            "knowledge_point": r.get("knowledge_point"),
            "f1": r.get("f1"),
            "precision": r.get("precision"),
            "recall": r.get("recall"),
            "readiness": r.get("readiness"),
            "knowledge_points": r.get("knowledge_points"),
            "foresight_verified": r.get("foresight_verified"),
            "foresight_hit": r.get("foresight_hit"),
            "intervention": None,
            "decision": None,
        }
        for d in decisions:
            dt = _ts(d.get("timestamp"))
            if not _near(rt, dt):
                continue
            kind = str(d.get("kind") or "")
            if "struggle" in kind:
                trace["intervention"] = {"kind": kind, "target": d.get("target"), "rationale": d.get("rationale"), "timestamp": d.get("timestamp")}
            elif any(k in kind for k in ("task_recommendation", "route_choice", "推进", "readiness")):
                trace["decision"] = {"kind": kind, "target": d.get("target"), "rationale": d.get("rationale")}
        traces.append(trace)

    traces.sort(key=lambda t: t["timestamp"] or "", reverse=True)
    return {"traces": traces[: max(1, min(limit, 200))]}
```

IMPORTANT: read the actual `/decisions` endpoint to see how it loads decisions (there may be a `DecisionStore` or a `decisions.jsonl` loader) and reuse THAT exact loader. If `_all_records` has a signature, call it correctly. Do not guess names — read the file.

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_profile_trace_log.py -v 2>&1 | Select-Object -Last 6`
Expected: PASS. Also run existing profile tests: `python -m pytest tests/api/test_profile.py -q 2>&1 | Select-Object -Last 3` (if that file exists — check; else run `tests/api/ -q` for the profile router).

- [ ] **Step 5: Ruff + Commit**

Ruff: `python -m ruff check deeptutor/api/routers/profile.py tests/api/test_profile_trace_log.py`

```bash
git add deeptutor/api/routers/profile.py tests/api/test_profile_trace_log.py
git commit -m "feat: GET /api/v1/profile/trace-log 教学回合聚合 (records+decisions)"
```

---

### Task 2: 前端 Timeline 可展开 + trace-log 接入

**Files:**
- Modify: `web/lib/learning-stats-api.ts`（加 `getTraceLog` + `TraceLog`/`TraceItem` 类型）
- Modify: `web/components/learning-stats/Timeline.tsx`（练习行可展开 + 显示介入/决策）
- Modify: `web/app/(workspace)/progress/page.tsx`（Promise.all 加 getTraceLog，传入 Timeline）

- [ ] **Step 1: 加 API 客户端函数**

Read `web/lib/learning-stats-api.ts` to see the existing `getEpisodes`/type patterns. Add:

```ts
export type TraceItem = {
  timestamp: string;
  date?: string | null;
  type: string;
  task_id?: string | null;
  knowledge_point?: string | null;
  f1?: number | null;
  precision?: number | null;
  recall?: number | null;
  readiness?: string | null;
  knowledge_points?: string[] | null;
  foresight_verified?: boolean;
  foresight_hit?: boolean;
  intervention?: {
    kind: string; target?: string; rationale?: string; timestamp?: string;
  } | null;
  decision?: {
    kind: string; target?: string; rationale?: string;
  } | null;
};

export async function getTraceLog(limit = 30): Promise<{ traces: TraceItem[] }> {
  const res = await fetch(`/api/v1/profile/trace-log?limit=${limit}`, { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to load trace log: ${res.status}`);
  return res.json();
}
```

Follow the existing fetch/error pattern in that file exactly.

- [ ] **Step 2: 改造 Timeline.tsx**

Read the current Timeline.tsx (80 lines, shows episodes by date with F1/readiness/foresight). Modify so:
1. Accept a new optional prop `traces: TraceItem[]` (or keep episodes + merge). PREFER: pass `traces` and build the display from it (simpler than merging two structures). Keep the daily grouping visual OR switch to a flat list — your call, keep it clean.
2. Each **annotation_exercise** trace row is clickable (useState for expanded key). Expanded shows:
   - `knowledge_points` joined by ·
   - intervention badge (red/orange, "卡住介入: {rationale}")
   - decision badge (blue, "{kind}: {rationale}")
3. Keep diagnosis/theory rows as-is (icon + knowledge_point).
4. Empty state: "暂无记录" when no traces.

Use lucide icons consistent with the existing file. Chinese labels hardcoded (page convention): 卡住介入 / 推进决策 / 展开 / 收起.

- [ ] **Step 3: 接入 progress/page.tsx**

In `web/app/(workspace)/progress/page.tsx`:
1. Add `getTraceLog` import + `const [traces, setTraces] = useState<TraceItem[]>([])`
2. Add `getTraceLog().catch(() => ({ traces: [] as TraceItem[] }))` to the Promise.all; set state
3. Pass `traces={traces}` to `<Timeline>` (it's in the 记录 tab)

- [ ] **Step 4: tsc 验证**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors

- [ ] **Step 5: Commit**

```bash
git add web/lib/learning-stats-api.ts web/components/learning-stats/Timeline.tsx "web/app/(workspace)/progress/page.tsx"
git commit -m "feat: Timeline 升级为可展开教学回合链 (F1/readiness/卡住介入/决策)"
```

---

### Task 3: 验证

**Files:** none

- [ ] **Step 1: 后端测试**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_profile_trace_log.py tests/api/ -q --continue-on-collection-errors 2>&1 | Select-Object -Last 4`
Expected: trace-log tests pass; profile API tests pass (no new failures vs baseline)

- [ ] **Step 2: 前端 tsc + build**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit` → 0 errors; then `Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY -ErrorAction SilentlyContinue; npx next build 2>&1 | Select-Object -Last 4` → build succeeds

- [ ] **Step 3: Playwright 冒烟**

With backend (8001) + frontend (3782) running:
1. Navigate to `/progress` → click 记录 tab → Timeline shows
2. Click an annotation_exercise row → expands to show F1/readiness + intervention/decision badges (if demo data has nearby decisions)
3. Screenshot for record

- [ ] **Step 4: 提交修复（如有）**

If smoke found issues, fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §3 后端 trace-log → Task 1
- §4 前端 Timeline → Task 2
- §5 测试 → Task 3
✅ 全覆盖

**2. Placeholder scan:** 所有步骤含具体代码/命令。Task 1 强调"读实际 loader 复用"（明确不猜名）。Task 2 Step 2 的 Timeline 改造有明确要求。✅

**3. Type consistency:** `TraceItem` 类型在 Task 2 Step 1 定义，Step 2/3 引用一致；`trace_log` 端点返回 `{"traces": [...]}` 与前端 `getTraceLog` 解析一致。✅

**已知风险（沿用 spec §7）：**
1. decisions/records 时间匹配用邻近启发式——匹配不到显示无介入（不误报）
2. demo 数据少（2 records + 3 decisions）——轨迹初始数据少但结构正确
