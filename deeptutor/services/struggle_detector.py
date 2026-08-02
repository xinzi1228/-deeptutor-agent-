"""StruggleDetector — deterministic learner-struggle signal detection.

Reads learning records and computes signals that indicate a learner is
stuck: consecutive low F1 scores, a confirmed repeated error pattern, or
task stall timeout. Pure functions — no LLM, no I/O beyond the input
records — so signals are testable, reproducible, and explainable.
"""

from __future__ import annotations

from datetime import datetime, timezone

LOW_F1_THRESHOLD = 0.7
LOW_SCORE_STREAK_MIN = 2
STALL_THRESHOLD_MINUTES = 30

SEVERITY_RANK = {"mild": 1, "moderate": 2, "severe": 3}


class StruggleDetector:
    """Deterministic struggle-signal detector over learning records."""

    # ----------------------------------------------------------- low score

    def low_score_streak(self, records: list[dict]) -> list[dict]:
        """Trigger when N consecutive exercises score below LOW_F1_THRESHOLD."""
        exercises = [r for r in records if r.get("type") == "annotation_exercise"]
        exercises.sort(key=lambda r: r.get("timestamp", ""))
        streak = 0
        signals = []
        for rec in exercises:
            f1 = rec.get("f1")
            try:
                f1v = float(f1)
            except (TypeError, ValueError):
                f1v = None
            if f1v is not None and f1v < LOW_F1_THRESHOLD:
                streak += 1
            else:
                streak = 0
            if streak >= LOW_SCORE_STREAK_MIN:
                signals.append(
                    {
                        "type": "low_score_streak",
                        "severity": "moderate",
                        "skill": rec.get("knowledge_point") or rec.get("task_id", ""),
                        "task_id": rec.get("task_id"),
                        "evidence": f"连续 {streak} 次练习 F1 < {LOW_F1_THRESHOLD}",
                        "count": streak,
                        "ts": rec.get("timestamp", ""),
                    }
                )
        return signals

    # --------------------------------------------------------- error repeat

    def repeated_error(self, records: list[dict]) -> list[dict]:
        """Trigger when an error_pattern is confirmed (≥2 occurrences)."""
        seen: dict[str, dict] = {}
        for rec in records:
            pattern = rec.get("error_pattern")
            if not pattern:
                continue
            if rec.get("pattern_status") == "confirmed":
                seen[pattern] = {
                    "type": "repeated_error",
                    "severity": "severe",
                    "skill": rec.get("knowledge_point") or rec.get("task_id", ""),
                    "task_id": rec.get("task_id"),
                    "evidence": f"错误模式 '{pattern}' 已确认（≥2 次证据）",
                    "pattern": pattern,
                    "count": 2,
                    "ts": rec.get("timestamp", ""),
                }
        return list(seen.values())

    # ---------------------------------------------------------- stall timeout

    def stall_timeout(
        self, records: list[dict], *, now: datetime | None = None, threshold_minutes: int = STALL_THRESHOLD_MINUTES
    ) -> list[dict]:
        """Trigger when the latest exercise is older than the stall threshold."""
        if now is None:
            now = datetime.now(timezone.utc)
        exercises = [r for r in records if r.get("type") == "annotation_exercise"]
        if not exercises:
            return []
        latest = max(exercises, key=lambda r: r.get("timestamp", ""))
        ts = latest.get("timestamp", "")
        try:
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return []
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        elapsed = now - ts_dt
        if elapsed.total_seconds() > threshold_minutes * 60:
            return [
                {
                    "type": "stall_timeout",
                    "severity": "mild",
                    "skill": latest.get("knowledge_point") or latest.get("task_id", ""),
                    "task_id": latest.get("task_id"),
                    "evidence": f"在任务停留超过 {threshold_minutes} 分钟",
                    "count": int(elapsed.total_seconds() // 60),
                    "ts": ts,
                }
            ]
        return []

    # ------------------------------------------------------------- aggregate

    def detect(self, *, records: list[dict], now: datetime | None = None) -> dict:
        """Aggregate all signals. Returns {signals, has_struggle, max_severity}."""
        signals = []
        signals.extend(self.low_score_streak(records))
        signals.extend(self.repeated_error(records))
        signals.extend(self.stall_timeout(records, now=now))
        signals.sort(key=lambda s: SEVERITY_RANK.get(s["severity"], 0), reverse=True)
        max_severity = signals[0]["severity"] if signals else None
        return {
            "signals": signals,
            "has_struggle": bool(signals),
            "max_severity": max_severity,
        }

    # ---------------------------------------------------- intervention mapping

    def intervention_suggestion(self, signal: dict) -> dict:
        """Map a signal to an intervention suggestion (readiness_gate mapping)."""
        s_type = signal.get("type")
        skill = signal.get("skill") or signal.get("task_id") or ""
        if s_type == "low_score_streak":
            return {
                "readiness": "review_first",
                "action": f"建议降到更基础任务重练，复习前置技能 '{skill}'",
                "signal_type": s_type,
                "target": skill,
            }
        if s_type == "repeated_error":
            return {
                "readiness": "diagnose_again",
                "action": f"错误模式 '{signal.get('pattern', '')}' 已确认，建议换教学模式或回退 Phase1 重诊",
                "signal_type": s_type,
                "target": skill,
            }
        if s_type == "stall_timeout":
            return {
                "readiness": "more_practice",
                "action": f"在任务 '{signal.get('task_id', '')}' 停留超时，建议主动询问学生是否需要帮助并给提示",
                "signal_type": s_type,
                "target": signal.get("task_id", ""),
            }
        return {"readiness": "more_practice", "action": "继续观察", "signal_type": s_type, "target": skill}


__all__ = ["StruggleDetector", "LOW_F1_THRESHOLD", "STALL_THRESHOLD_MINUTES"]
