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
    """Extract the date (YYYY-MM-DD) from an ISO timestamp; naive timestamps treated as UTC."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except (ValueError, AttributeError):
        return None


def _is_timed(r: dict) -> bool:
    """A usable timestamp is a non-empty string; anything else is treated as absent."""
    ts = r.get("timestamp")
    return isinstance(ts, str) and bool(ts)


def _timestamps(records: list[dict]) -> list[str]:
    """Non-empty string timestamps, in record order."""
    return [r["timestamp"] for r in records if _is_timed(r)]


class AchievementService:
    """Deterministic check-in + badge derivation over learning records."""

    def __init__(self, records: list[dict] | None = None, *, now: datetime | None = None) -> None:
        self._records = records if records is not None else _load_records()
        self._now = now or datetime.now(timezone.utc)

    # --------------------------------------------------------------- checkin

    def checkin(self) -> dict:
        dates = sorted({d for d in (_local_date(r.get("timestamp", "")) for r in self._records) if d})
        today = self._now.date().isoformat()
        total_days = len(dates)
        streak = 0
        cursor = self._now.date()
        if cursor.isoformat() not in dates:
            cursor -= timedelta(days=1)
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
        checkin = self.checkin()
        streak = checkin["streak"]
        practices = [r for r in self._records if r.get("type") == PRACTICE_TYPE and _is_timed(r)]
        first_pass_dt = next(
            (r["timestamp"] for r in practices if _as_float(r.get("f1")) is not None and _as_float(r.get("f1")) >= 0.7),
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
            "first_step": min(_timestamps(self._records), default=None) if conditions["first_step"] else None,
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
        plan = _load_course_plan()
        has_plan = bool(plan and plan.get("modules"))
        if has_plan:
            for module in plan["modules"]:
                tasks = [t for t in module.get("tasks", []) if isinstance(t, str)]
                if not tasks:
                    continue
                task_f1s: dict[str, float] = {}
                for r in self._records:
                    if r.get("type") == PRACTICE_TYPE and _is_timed(r) and r.get("task_id") in tasks:
                        f1 = _as_float(r.get("f1"))
                        if f1 is not None:
                            prev = task_f1s.get(r["task_id"])
                            task_f1s[r["task_id"]] = max(prev, f1) if prev is not None else f1
                if all(task_f1s.get(t, 0) >= 0.7 for t in tasks):
                    return max(_timestamps([
                        r for r in self._records
                        if r.get("type") == PRACTICE_TYPE and _is_timed(r) and r.get("task_id") in tasks
                    ]), default=None)
            return None
        practiced = {r.get("task_id") for r in self._records if r.get("type") == PRACTICE_TYPE and r.get("task_id")}
        if len(practiced) >= MODULE_CLEAR_MIN_DISTINCT_TASKS:
            return max(_timestamps([r for r in self._records if r.get("type") == PRACTICE_TYPE]), default=None)
        return None

    def _streak_unlock_time(self, streak: int, n: int) -> str | None:
        if streak < n:
            return None
        checkin = self.checkin()
        dates = set(checkin["dates"])
        cursor = self._now.date()
        if cursor.isoformat() not in dates:
            cursor -= timedelta(days=1)
        target = cursor - timedelta(days=n - 1)
        if target.isoformat() in dates:
            for r in self._records:
                if _is_timed(r) and _local_date(r["timestamp"]) == target.isoformat():
                    return r["timestamp"]
        return None

    def _practice_10_time(self, practices: list[dict]) -> str | None:
        if len(practices) < 10:
            return None
        sorted_p = sorted(practices, key=lambda r: r["timestamp"])
        return sorted_p[9]["timestamp"]


def _as_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _load_records() -> list[dict]:
    from deeptutor.services.learning_records import LearningRecordStore

    return LearningRecordStore().list_records()


def _load_course_plan() -> dict | None:
    from deeptutor.services.course_plan import CoursePlanStore

    return CoursePlanStore().get()


__all__ = ["BADGES", "AchievementService", "RECORD_TYPES"]
