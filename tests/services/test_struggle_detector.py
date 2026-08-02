"""StruggleDetector — deterministic struggle-signal detection tests."""

from __future__ import annotations

from datetime import datetime, timezone

from deeptutor.services.struggle_detector import StruggleDetector


def _rec(*, type="annotation_exercise", task_id="task1", f1=0.6, error_pattern=None,
         pattern_status=None, timestamp="2026-08-01T10:00:00+00:00"):
    r = {"type": type, "task_id": task_id, "f1": f1, "timestamp": timestamp}
    if error_pattern:
        r["error_pattern"] = error_pattern
        r["pattern_status"] = pattern_status or "confirmed"
    return r


def test_low_score_streak_triggers():
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, timestamp="2026-08-01T11:00:00+00:00"),
    ]
    signals = StruggleDetector().low_score_streak(records)
    assert len(signals) == 1
    assert signals[0]["type"] == "low_score_streak"
    assert signals[0]["severity"] == "moderate"


def test_low_score_streak_not_triggered_on_high_score():
    records = [
        _rec(task_id="task1", f1=0.9, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, timestamp="2026-08-01T11:00:00+00:00"),
    ]
    assert StruggleDetector().low_score_streak(records) == []


def test_repeated_error_triggers_on_confirmed():
    records = [
        _rec(task_id="task1", f1=0.6, error_pattern="漏标", pattern_status="confirmed",
             timestamp="2026-08-01T10:00:00+00:00"),
    ]
    signals = StruggleDetector().repeated_error(records)
    assert len(signals) == 1
    assert signals[0]["type"] == "repeated_error"
    assert signals[0]["severity"] == "severe"


def test_repeated_error_not_triggered_on_unconfirmed():
    records = [
        _rec(task_id="task1", f1=0.6, error_pattern="漏标", pattern_status="unconfirmed",
             timestamp="2026-08-01T10:00:00+00:00"),
    ]
    assert StruggleDetector().repeated_error(records) == []


def test_stall_timeout_triggers():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
    ]
    signals = StruggleDetector().stall_timeout(records, now=now, threshold_minutes=30)
    assert len(signals) == 1
    assert signals[0]["type"] == "stall_timeout"
    assert signals[0]["severity"] == "mild"


def test_stall_timeout_not_triggered_recent():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-02T11:50:00+00:00"),
    ]
    assert StruggleDetector().stall_timeout(records, now=now, threshold_minutes=30) == []


def test_stall_timeout_triggers_naive_timestamp():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00"),
    ]
    signals = StruggleDetector().stall_timeout(records, now=now, threshold_minutes=30)
    assert len(signals) == 1
    assert signals[0]["type"] == "stall_timeout"


def test_stall_timeout_not_triggered_naive_recent():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-02T11:50:00"),
    ]
    assert StruggleDetector().stall_timeout(records, now=now, threshold_minutes=30) == []


def test_detect_aggregates_signals():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, error_pattern="漏标", pattern_status="confirmed",
             timestamp="2026-08-01T11:00:00+00:00"),
    ]
    result = StruggleDetector().detect(records=records, now=now)
    assert result["has_struggle"] is True
    assert result["max_severity"] == "severe"
    assert len(result["signals"]) >= 2


def test_detect_empty_records():
    result = StruggleDetector().detect(records=[], now=datetime.now(timezone.utc))
    assert result["has_struggle"] is False
    assert result["signals"] == []


def test_detect_deterministic():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    records = [
        _rec(task_id="task1", f1=0.6, timestamp="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task1", f1=0.5, timestamp="2026-08-01T11:00:00+00:00"),
    ]
    r1 = StruggleDetector().detect(records=records, now=now)
    r2 = StruggleDetector().detect(records=records, now=now)
    assert r1 == r2


def test_intervention_suggestion_low_score():
    s = StruggleDetector().intervention_suggestion(
        {"type": "low_score_streak", "severity": "moderate", "skill": "边界框绘制规范"}
    )
    assert s["readiness"] == "review_first"
    assert "降" in s["action"] or "复习" in s["action"]


def test_intervention_suggestion_repeated_error():
    s = StruggleDetector().intervention_suggestion(
        {"type": "repeated_error", "severity": "severe", "pattern": "漏标"}
    )
    assert s["readiness"] == "diagnose_again"
    assert "换" in s["action"] or "回退" in s["action"]


def test_intervention_suggestion_stall():
    s = StruggleDetector().intervention_suggestion(
        {"type": "stall_timeout", "severity": "mild", "task_id": "task2"}
    )
    assert s["readiness"] == "more_practice"
    assert "帮助" in s["action"] or "提示" in s["action"]
