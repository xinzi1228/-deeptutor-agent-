# 打卡徽章引擎实施计划（Check-in & Achievements）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 learning records 派生打卡（日历+streak）与 6 个徽章（确定性、无新数据文件），Progress 页展示 GitHub 热力图风格打卡日历 + 徽章墙。

**Architecture:** `AchievementService` 纯函数服务（读 `LearningRecordStore.list_records()` 派生 checkin/badges）→ `GET /api/v1/achievements` 路由 → Progress 页 `CheckinCalendar`（热力图）+ `BadgeWall`（徽章墙）。

**Tech Stack:** Python 3.13, pytest + pytest-asyncio, FastAPI, Next.js (TSX)。确定性引擎（无 LLM in core）。

**Spec:** `docs/specs/checkin-achievements-design.md`（已提交 `aec81539`）

---

### Task 1: `AchievementService` 服务——打卡 + 6 徽章派生

**Files:**
- Create: `deeptutor/services/achievements.py`
- Test: `tests/services/test_achievements.py`

- [ ] **Step 1: Write the failing test**

Create `tests/services/test_achievements.py`:

```python
"""AchievementService — deterministic checkin + badge derivation from learning records."""

from __future__ import annotations

from datetime import datetime, timezone

from deeptutor.services.achievements import BADGES, AchievementService

RECORD_TYPES = ("diagnosis", "theory_mastered", "annotation_exercise")


def _rec(*, type="annotation_exercise", task_id="task1", f1=0.9, ts="2026-08-01T10:00:00+00:00"):
    r = {"type": type, "timestamp": ts}
    if task_id:
        r["task_id"] = task_id
    if f1 is not None:
        r["f1"] = f1
    return r


def _service(records, now=None):
    return AchievementService(records=records, now=now)


def test_checkin_dates_deduped():
    svc = _service([
        _rec(ts="2026-08-01T10:00:00+00:00"),
        _rec(ts="2026-08-01T18:00:00+00:00"),  # same day
        _rec(ts="2026-08-02T10:00:00+00:00"),
    ])
    result = svc.checkin()
    assert result["total_days"] == 2
    assert "2026-08-01" in result["dates"]
    assert "2026-08-02" in result["dates"]


def test_streak_contiguous():
    svc = _service(
        [_rec(ts=f"2026-08-0{d}T10:00:00+00:00") for d in range(1, 4)],
        now=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert svc.checkin()["streak"] == 3


def test_streak_breaks_on_gap():
    svc = _service(
        [_rec(ts=f"2026-08-0{d}T10:00:00+00:00") for d in range(1, 3)] + [_rec(ts="2026-07-30T10:00:00+00:00")],
        now=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
    )
    # today (08-03) not checked, 08-02 checked -> streak 2 (stops at 07-31 gap)
    assert svc.checkin()["streak"] == 2


def test_streak_zero_when_no_records():
    svc = _service([], now=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc))
    assert svc.checkin()["streak"] == 0
    assert svc.checkin()["total_days"] == 0


def test_today_checked_flag():
    svc = _service([_rec(ts="2026-08-03T08:00:00+00:00")], now=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc))
    assert svc.checkin()["today_checked"] is True


def test_badge_first_step():
    svc = _service([_rec(type="diagnosis", ts="2026-08-01T10:00:00+00:00")])
    badges = {b["id"]: b for b in svc.badges()}
    assert badges["first_step"]["unlocked"] is True


def test_badge_streak_3_and_7():
    svc = _service(
        [_rec(ts=f"2026-08-0{d}T10:00:00+00:00") for d in range(1, 8)],
        now=datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc),
    )
    badges = {b["id"]: b for b in svc.badges()}
    assert badges["streak_3"]["unlocked"] is True
    assert badges["streak_7"]["unlocked"] is True
    assert badges["streak_3"]["unlocked_at"] is not None


def test_badge_first_pass_needs_f1_ge_07():
    svc = _service([_rec(task_id="task1", f1=0.5, ts="2026-08-01T10:00:00+00:00")])
    assert svc.badges()["first_pass"]["unlocked"] is False if isinstance(svc.badges(), dict) else \
        {b["id"]: b for b in svc.badges()}["first_pass"]["unlocked"] is False

    svc2 = _service([_rec(task_id="task1", f1=0.85, ts="2026-08-01T10:00:00+00:00")])
    assert {b["id"]: b for b in svc2.badges()}["first_pass"]["unlocked"] is True


def test_badge_practice_10():
    recs = [_rec(task_id=f"task{i % 3 + 1}", ts=f"2026-08-0{d % 9 + 1}T10:00:00+00:00") for i, d in enumerate(range(1, 11))]
    svc = _service(recs)
    assert {b["id"]: b for b in svc.badges()}["practice_10"]["unlocked"] is True


def test_badge_module_clear_with_course_plan():
    # 4 modules; module "标注基础" has tasks task1/task3/task5 all F1>=0.7 -> clear
    recs = [
        _rec(task_id="task1", f1=0.8, ts="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task3", f1=0.75, ts="2026-08-02T10:00:00+00:00"),
        _rec(task_id="task5", f1=0.7, ts="2026-08-03T10:00:00+00:00"),
    ]
    svc = _service(recs, now=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc))
    badges = {b["id"]: b for b in svc.badges()}
    assert badges["module_clear"]["unlocked"] is True


def test_badge_module_clear_fallback_without_course_plan():
    # no course_plan available -> fallback: >=5 distinct task_ids have practice
    recs = [_rec(task_id=f"task{i}", f1=0.8, ts=f"2026-08-0{d % 28 + 1}T10:00:00+00:00") for i, d in zip(range(1, 6), range(1, 6))]
    svc = _service(recs)
    assert {b["id"]: b for b in svc.badges()}["module_clear"]["unlocked"] is True


def test_all_badges_unlocked_ordering():
    svc = _service([_rec(ts="2026-08-01T10:00:00+00:00")])
    badges = svc.badges()
    assert len(badges) == 6
    assert badges[0]["id"] == BADGES[0]["id"]  # order preserved


def test_deterministic():
    recs = [
        _rec(task_id="task1", f1=0.5, ts="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.85, ts="2026-08-02T10:00:00+00:00"),
    ]
    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    a = AchievementService(records=recs, now=now)
    b = AchievementService(records=recs, now=now)
    assert a.checkin() == b.checkin()
    assert a.badges() == b.badges()
```

NOTE: The test references `svc.badges()` — decide whether it returns a **dict** `{id: badge}` or a **list** `[{badge}]`. The tests use BOTH patterns (some `svc.badges()["first_pass"]`, some `{b["id"]: b for b in svc.badges()}`). **Pick ONE** — the cleanest is `badges()` returning a **list** in spec order (per `test_all_badges_unlocked_ordering` which asserts `badges[0]["id"] == BADGES[0]["id"]`). Update the tests to consistently use list + `{b["id"]: b for b in ...}`. Do NOT keep both patterns.

Also `test_badge_first_pass_needs_f1_ge_07` has a convoluted conditional — clean it up to the list-conversion form.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_achievements.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/services/achievements.py`:

```python
"""AchievementService — deterministic checkin + badge derivation from learning records.

Reads learning records (diagnosis / theory_mastered / annotation_exercise) and
derives: (1) a check-in calendar (daily activity dates -> total days + current
streak counting back from today) and (2) a fixed 6-badge achievement set whose
conditions are computed from the records. Pure functions — no LLM, no writes —
so results are testable, reproducible, and auditable.

Borrowed shape from Streaky / GitHub contribution streaks: the streak counts
consecutive calendar days ending today (or yesterday if today is not yet done).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

BADGES: list[dict] = [
    {"id": "first_step", "name": "新手上路", "description": "完成首次学习"},
    {"id": "streak_3", "name": "小有坚持", "description": "连续打卡 3 天"},
    {"id": "streak_7", "name": "持之以恒", "description": "连续打卡 7 天"},
    {"id": "first_pass", "name": "初战告捷", "description": "首个练习 F1 ≥ 0.7"},
    {"id": "practice_10", "name": "熟能生巧", "description": "累计完成 10 个练习"},
    {"id": "module_clear", "name": "阶段通关", "description": "完成一个学习模块"},
]

RECORD_TYPES = ("diagnosis", "theory_mastered", "annotation_exercise")
PRACTICE_TYPE = "annotation_exercise"
MODULE_CLEAR_MIN_DISTINCT_TASKS = 5


def _local_date(ts: str) -> str | None:
    """Extract the date (YYYY-MM-DD) from an ISO timestamp, naive timestamps treated as UTC."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except (ValueError, AttributeError):
        return None


class AchievementService:
    """Deterministic check-in + badge derivation over learning records."""

    def __init__(self, records: list[dict] | None = None, *, now: datetime | None = None) -> None:
        self._records = records if records is not None else _load_records()
        self._now = now or datetime.now(timezone.utc)

    # --------------------------------------------------------------- checkin

    def checkin(self) -> dict:
        """Derive {dates, total_days, streak, today_checked} from record timestamps."""
        dates = sorted({d for d in (_local_date(r.get("timestamp", "")) for r in self._records) if d})
        today = self._now.date().isoformat()
        total_days = len(dates)
        streak = 0
        cursor = self._now.date()
        if cursor.isoformat() not in dates:
            cursor -= timedelta(days=1)  # today not done yet -> streak counts from yesterday
        while cursor.isoformat() in dates:
            streak += 1
            cursor -= timedelta(days=1)
        return {
            "dates": dates,
            "total_days": total_days,
            "streak": streak,
            "today_checked": today in dates,
        }

    # ---------------------------------------------------------------- badges

    def badges(self) -> list[dict]:
        """Derive the 6-badge set with unlocked + unlocked_at."""
        checkin = self.checkin()
        streak = checkin["streak"]
        total_days = checkin["total_days"]
        practices = [r for r in self._records if r.get("type") == PRACTICE_TYPE]
        first_pass_dt = next(
            (r.get("timestamp") for r in practices if _as_float(r.get("f1")) is not None and _as_float(r.get("f1")) >= 0.7),
            None,
        )
        module_clear_at = self._module_clear_time()
        conditions = {
            "first_step": checkin["total_days"] > 0,
            "streak_3": streak >= 3,
            "streak_7": streak >= 7,
            "first_pass": first_pass_dt is not None,
            "practice_10": len(practices) >= 10,
            "module_clear": module_clear_at is not None,
        }
        unlocked_at = {
            "first_step": min((r.get("timestamp") for r in self._records), default=None) if conditions["first_step"] else None,
            "streak_3": self._streak_unlock_time(streak, 3),
            "streak_7": self._streak_unlock_time(streak, 7),
            "first_pass": first_pass_dt,
            "practice_10": self._practice_10_time(practices),
            "module_clear": module_clear_at,
        }
        result = []
        for badge in BADGES:
            bid = badge["id"]
            result.append({
                **badge,
                "unlocked": bool(conditions[bid]),
                "unlocked_at": unlocked_at[bid],
            })
        return result

    # ------------------------------------------------------------ module clear

    def _module_clear_time(self) -> str | None:
        """Time the first module was cleared via course_plan; fallback to distinct-task heuristic."""
        plan = _load_course_plan()
        if plan and plan.get("modules"):
            for module in plan["modules"]:
                tasks = [t for t in module.get("tasks", []) if isinstance(t, str)]
                if not tasks:
                    continue
                task_f1s: dict[str, float] = {}
                for r in self._records:
                    if r.get("type") == PRACTICE_TYPE and r.get("task_id") in tasks:
                        f1 = _as_float(r.get("f1"))
                        if f1 is not None:
                            prev = task_f1s.get(r["task_id"])
                            task_f1s[r["task_id"]] = max(prev, f1) if prev is not None else f1
                if tasks and all(task_f1s.get(t, 0) >= 0.7 for t in tasks):
                    return max((r.get("timestamp") for r in self._records if r.get("type") == PRACTICE_TYPE and r.get("task_id") in tasks), default=None)
        # fallback: >=5 distinct practiced tasks
        practiced = {r.get("task_id") for r in self._records if r.get("type") == PRACTICE_TYPE and r.get("task_id")}
        if len(practiced) >= MODULE_CLEAR_MIN_DISTINCT_TASKS:
            return max((r.get("timestamp") for r in self._records if r.get("type") == PRACTICE_TYPE), default=None)
        return None

    def _streak_unlock_time(self, streak: int, n: int) -> str | None:
        if streak < n:
            return None
        # unlock at the nth consecutive checked day (from today backward: the earliest of the streak window)
        checkin = self.checkin()
        dates = set(checkin["dates"])
        cursor = self._now.date()
        if cursor.isoformat() not in dates:
            cursor -= timedelta(days=1)
        target = cursor - timedelta(days=n - 1)
        if target.isoformat() in dates:
            # find the first record timestamp on that day
            for r in self._records:
                d = _local_date(r.get("timestamp", ""))
                if d == target.isoformat():
                    return r.get("timestamp")
        return None

    def _practice_10_time(self, practices: list[dict]) -> str | None:
        if len(practices) < 10:
            return None
        sorted_p = sorted(practices, key=lambda r: r.get("timestamp", ""))
        return sorted_p[9].get("timestamp")


def _as_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_records() -> list[dict]:
    from deeptutor.services.learning_records import LearningRecordStore

    return LearningRecordStore().list_records()


def _load_course_plan() -> dict | None:
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "data" / "user" / "workspace" / "learning" / "course_plan.json"
    if not p.exists():
        return None
    import json

    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


__all__ = ["BADGES", "AchievementService", "RECORD_TYPES"]
```

NOTE: Read `deeptutor/services/learning_records.py` `list_records()` first to confirm the return shape (a list of dicts with `type`/`timestamp`/`f1`/`task_id`). Adapt `_load_records` if the signature differs (it may take a `user_id` or be a method needing a store instance). The `now` injection + in-memory `records` in the constructor make tests deterministic without touching the real store.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_achievements.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Ruff + Commit**

Ruff: `python -m ruff check deeptutor/services/achievements.py tests/services/test_achievements.py`

```bash
git add deeptutor/services/achievements.py tests/services/test_achievements.py
git commit -m "feat: AchievementService 打卡+6徽章派生 (确定性, 从 learning records)"
```

---

### Task 2: `achievements` API 端点

**Files:**
- Create: `deeptutor/api/routers/achievements.py`
- Modify: `deeptutor/api/main.py` (import + include_router)
- Test: `tests/api/test_achievements.py`

- [ ] **Step 1: Write the failing test**

Read an existing router test to follow the pattern (e.g. `tests/api/test_memory.py` or a simple GET router test). Create `tests/api/test_achievements.py`:

```python
"""achievements API tests."""

from __future__ import annotations

import pytest

from deeptutor.api.routers.achievements import router


def test_router_path_and_method():
    for route in router.routes:
        if getattr(route, "path", "") == "/achievements" and "GET" in getattr(route, "methods", set()):
            return
    pytest.fail("GET /achievements route not found")


@pytest.mark.asyncio
async def test_achievements_endpoint_shape(monkeypatch) -> None:
    from deeptutor.api.routers.achievements import get_achievements

    async def _fake_derive(records=None, now=None):
        return {
            "checkin": {"dates": [], "total_days": 0, "streak": 0, "today_checked": False},
            "badges": [],
        }

    monkeypatch.setattr("deeptutor.api.routers.achievements._derive_payload", _fake_derive)
    result = await get_achievements()
    assert "checkin" in result
    assert "badges" in result
```

NOTE: The endpoint implementation should call a `_derive_payload()` module function (wrapping `AchievementService`) so tests can monkeypatch it. Design `get_achievements` accordingly (it may take a `user_id` dependency or just derive from the default store — match how sibling simple GET routers do it; read e.g. `deeptutor/api/routers/dashboard.py` or `memory.py`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_achievements.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the endpoint**

Create `deeptutor/api/routers/achievements.py`:

```python
"""achievements router — check-in calendar + badge wall derived from learning records."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/achievements")
async def get_achievements() -> dict:
    """Return the learner's check-in calendar + badge set (derived, no writes)."""
    return _derive_payload()


def _derive_payload() -> dict:
    from deeptutor.services.achievements import AchievementService

    svc = AchievementService()
    return {"checkin": svc.checkin(), "badges": svc.badges()}


__all__ = ["router", "get_achievements"]
```

(Adapt the endpoint signature to match sibling routers — e.g. if they take a `user_id`/auth dependency, mirror it. Read `deeptutor/api/routers/dashboard.py` first.)

- [ ] **Step 4: Mount in main.py**

Edit `deeptutor/api/main.py`:
1. Add `achievements,` to the `from deeptutor.api.routers import (...)` block (alphabetical).
2. Add `app.include_router(achievements.router, prefix="/api/v1", tags=["achievements"], dependencies=_auth)` near the other `/api/v1` routers (follow the `dashboard`/`chat` pattern — check whether `dashboard.router` is mounted with `prefix="/api/v1"`).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_achievements.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

Verify the app imports cleanly: `python -c "import deeptutor.api.main"` — no circular import.

- [ ] **Step 6: Ruff + Commit**

Ruff: `python -m ruff check deeptutor/api/routers/achievements.py deeptutor/api/main.py tests/api/test_achievements.py`

```bash
git add deeptutor/api/routers/achievements.py deeptutor/api/main.py tests/api/test_achievements.py
git commit -m "feat: GET /api/v1/achievements 端点 (打卡+徽章)"
```

---

### Task 3: Progress 页打卡日历 + 徽章墙组件

**Files:**
- Create: `web/components/learning-stats/CheckinCalendar.tsx`
- Create: `web/components/learning-stats/BadgeWall.tsx`
- Modify: `web/app/(workspace)/progress/page.tsx`
- Test: none (frontend; verify with `npx tsc --noEmit`)

- [ ] **Step 1: Read the existing Progress page + a learning-stats component**

Read `web/app/(workspace)/progress/page.tsx` (how it fetches data + renders panels) and `web/components/learning-stats/KnowledgeGraphPanel.tsx` or `StatCards.tsx` (component style: client component, apiFetch, etc.). Also check `web/lib/api.ts` for `apiFetch`/`apiUrl`.

- [ ] **Step 2: Create `CheckinCalendar.tsx`**

```tsx
"use client";

import { useTranslation } from "react-i18next";

import { apiFetch, apiUrl } from "@/lib/api";

interface CheckinData {
  dates: string[];
  total_days: number;
  streak: number;
  today_checked: boolean;
}

const WEEKS = 12;

function isoDate(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

/** GitHub-contribution-style check-in heatmap (last ~12 weeks) + streak. */
export function CheckinCalendar() {
  const { t } = useTranslation();
  const [data, setData] = React.useState<CheckinData | null>(null);

  React.useEffect(() => {
    apiFetch(apiUrl("/api/v1/achievements"))
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => setData(payload?.checkin ?? null))
      .catch(() => setData(null));
  }, []);

  if (!data) return null;

  const checked = new Set(data.dates);
  const todayIso = isoDate(0);
  // build columns of 7 days (Mon..Sun) for the last WEEKS weeks
  const cols: string[][] = [];
  for (let w = 0; w < WEEKS; w++) {
    const col: string[] = [];
    for (let d = 6 - w * 7; d > -w * 7 - 1; d--) {
      col.push(isoDate(-d));
    }
    cols.push(col);
  }

  return (
    <div className="rounded-lg border border-[var(--border)]/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[15px] font-medium">{t("打卡日历")}</h3>
        <div className="text-[13px] text-[var(--muted-foreground)]">
          🔥 {t("连续打卡")} {data.streak} 天 · {t("累计")} {data.total_days} 天
          {data.today_checked ? " · ✅ 今日已打卡" : ""}
        </div>
      </div>
      <div className="flex gap-1 overflow-x-auto">
        {cols.map((col, ci) => (
          <div key={ci} className="flex flex-col gap-1">
            {col.map((date) => (
              <div
                key={date}
                title={date}
                className={`h-3 w-3 rounded-[3px] ${
                  date === todayIso
                    ? "bg-[var(--primary)] ring-1 ring-[var(--primary)]"
                    : checked.has(date)
                      ? "bg-[var(--primary)]/60"
                      : "bg-[var(--muted)]/40"
                }`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
```

NOTE: verify `React` is imported or use explicit `useState`/`useEffect` imports (check how KnowledgeGraphPanel imports React). Match the existing component conventions exactly.

- [ ] **Step 3: Create `BadgeWall.tsx`**

```tsx
"use client";

import { useTranslation } from "react-i18next";

import { apiFetch, apiUrl } from "@/lib/api";

interface Badge {
  id: string;
  name: string;
  description: string;
  unlocked: boolean;
  unlocked_at: string | null;
}

/** 6-badge achievement wall — unlocked badges lit, locked greyed. */
export function BadgeWall() {
  const { t } = useTranslation();
  const [badges, setBadges] = React.useState<Badge[] | null>(null);

  React.useEffect(() => {
    apiFetch(apiUrl("/api/v1/achievements"))
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => setBadges(payload?.badges ?? null))
      .catch(() => setBadges(null));
  }, []);

  if (!badges) return null;

  return (
    <div className="rounded-lg border border-[var(--border)]/60 p-4">
      <h3 className="mb-3 text-[15px] font-medium">{t("成就徽章")}</h3>
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        {badges.map((b) => (
          <div
            key={b.id}
            title={b.unlocked ? `${b.name} · ${b.unlocked_at ?? ""}` : b.description}
            className={`flex flex-col items-center gap-1 rounded-lg border p-2 text-center ${
              b.unlocked
                ? "border-[var(--primary)]/40 bg-[var(--primary)]/[0.06]"
                : "border-[var(--border)]/40 opacity-45"
            }`}
          >
            <span className="text-2xl">{b.unlocked ? "🏆" : "🔒"}</span>
            <span className="text-[12px] leading-tight">{b.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire into Progress page**

Edit `web/app/(workspace)/progress/page.tsx`: import `CheckinCalendar` + `BadgeWall` and render them in a sensible spot (e.g. near the top, after the page header, or alongside StatCards). Follow how existing panels are placed.

- [ ] **Step 5: Verify tsc**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -Last 5`
Expected: no output (0 errors)

- [ ] **Step 6: Commit**

```bash
git add web/components/learning-stats/CheckinCalendar.tsx web/components/learning-stats/BadgeWall.tsx web/app/'(workspace)'/progress/page.tsx
git commit -m "feat: Progress 页打卡日历热力图 + 成就徽章墙"
```

---

### Task 4: 全量回归 + 冒烟

**Files:** none (verification)

- [ ] **Step 1: Run feature tests**

Run: `cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -m pytest tests/services/test_achievements.py tests/api/test_achievements.py -q 2>&1 | Select-Object -Last 5`
Expected: PASS

- [ ] **Step 2: Backend full regression**

Run: `python -m pytest tests/ -q 2>&1 | Select-Object -Last 6`
Expected: no NEW failures vs the known pre-existing baseline (Windows path/sep, GBK locale, missing optional deps, sandbox env — ~33 pre-existing failures).

- [ ] **Step 3: Frontend tsc + build**

Run: `cd "D:\自己\git帅\-deeptutor-agent-\web"; npx tsc --noEmit 2>&1 | Select-Object -Last 3` → clean.
Then: `npm run build 2>&1 | Select-Object -Last 15` → success.

- [ ] **Step 4: End-to-end smoke (derive on real records)**

Run:
```powershell
cd "D:\自己\git帅\-deeptutor-agent-"; $env:PYTHONIOENCODING="utf-8"; python -c @"
from deeptutor.services.achievements import AchievementService
svc = AchievementService()
c = svc.checkin()
b = svc.badges()
print('checkin:', c['total_days'], 'days | streak:', c['streak'], '| today_checked:', c['today_checked'])
print('badges:', [(x['id'], x['unlocked']) for x in b])
print('badge count:', len(b))
assert len(b) == 6
print('SMOKE OK')
"@
```
Expected: real records produce a checkin summary + 6 badges, SMOKE OK.

- [ ] **Step 5: Commit any fixes**

If smoke/full-run found issues, fix + commit. Otherwise no commit.

---

## Self-Review

**1. Spec coverage:**
- §4 AchievementService → Task 1
- §5.1 API → Task 2
- §5.2 前端 → Task 3
- §6 测试验证 → Task 4
✅ 全覆盖

**2. Placeholder scan:** 所有代码块完整。Task 1 的 `badges()` 返回类型（list vs dict）测试中有矛盾写法——implementer 需统一为 list（已标注）；`_load_records`/`_load_course_plan` 需按实际签名适配（已标注）。

**3. Type consistency:**
- `checkin()` → `{dates, total_days, streak, today_checked}` — Task 1/2/4 一致
- `badges()` → `[{id, name, description, unlocked, unlocked_at}]` — Task 1/2 一致
- 徽章 id: `first_step/streak_3/streak_7/first_pass/practice_10/module_clear` — Task 1/3 一致
- API: `GET /api/v1/achievements` → `{checkin, badges}` — Task 2/3 一致

**已知风险：**
1. `list_records()` 签名可能需用户上下文——Task 1 `_load_records` 适配
2. `course_plan.json` 是运行时数据，测试需注入（Task 1 用内存 records，模块通关测 course_plan 路径需临时文件或 monkeypatch `_load_course_plan`）——implementer 处理
3. Progress 页组件用 `React.useState`——需按现有组件导入惯例适配
4. API 端点的 auth 依赖——按 sibling router 模式挂载
