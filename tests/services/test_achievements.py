"""AchievementService — deterministic checkin + badge derivation from learning records."""

from __future__ import annotations

from datetime import datetime, timezone

from deeptutor.services.achievements import BADGES, AchievementService


def _rec(*, type="annotation_exercise", task_id="task1", f1=0.9, ts="2026-08-01T10:00:00+00:00"):
    r = {"type": type, "timestamp": ts}
    if task_id:
        r["task_id"] = task_id
    if f1 is not None:
        r["f1"] = f1
    return r


def _service(records, now=None):
    return AchievementService(records=records, now=now)


def _badge_map(svc):
    return {b["id"]: b for b in svc.badges()}


def test_checkin_dates_deduped():
    svc = _service([
        _rec(ts="2026-08-01T10:00:00+00:00"),
        _rec(ts="2026-08-01T18:00:00+00:00"),
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
        [_rec(ts="2026-08-01T10:00:00+00:00"), _rec(ts="2026-08-02T10:00:00+00:00"), _rec(ts="2026-07-30T10:00:00+00:00")],
        now=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
    )
    # today (08-03) not checked -> streak counts from yesterday (08-02); 08-02 checked, 08-01 checked, 07-31 gap -> streak 2
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
    assert _badge_map(svc)["first_step"]["unlocked"] is True


def test_badge_streak_3_and_7():
    svc = _service(
        [_rec(ts=f"2026-08-0{d}T10:00:00+00:00") for d in range(1, 8)],
        now=datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc),
    )
    badges = _badge_map(svc)
    assert badges["streak_3"]["unlocked"] is True
    assert badges["streak_7"]["unlocked"] is True
    assert badges["streak_3"]["unlocked_at"] is not None


def test_badge_first_pass_needs_f1_ge_07():
    svc = _service([_rec(task_id="task1", f1=0.5, ts="2026-08-01T10:00:00+00:00")])
    assert _badge_map(svc)["first_pass"]["unlocked"] is False

    svc2 = _service([_rec(task_id="task1", f1=0.85, ts="2026-08-01T10:00:00+00:00")])
    assert _badge_map(svc2)["first_pass"]["unlocked"] is True


def test_badge_practice_10():
    recs = [_rec(task_id=f"task{i % 3 + 1}", ts=f"2026-08-0{d % 9 + 1}T10:00:00+00:00") for i, d in enumerate(range(1, 11))]
    svc = _service(recs)
    assert _badge_map(svc)["practice_10"]["unlocked"] is True


def test_badge_module_clear_with_course_plan(tmp_path, monkeypatch):
    # monkeypatch _load_course_plan to return a plan where 标注基础 has task1/3/5
    import json
    from pathlib import Path

    import deeptutor.services.achievements as mod

    plan = {"modules": [{"name": "标注基础", "tasks": ["task1", "task3", "task5"]}]}
    monkeypatch.setattr(mod, "_load_course_plan", lambda: plan)

    recs = [
        _rec(task_id="task1", f1=0.8, ts="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task3", f1=0.75, ts="2026-08-02T10:00:00+00:00"),
        _rec(task_id="task5", f1=0.7, ts="2026-08-03T10:00:00+00:00"),
    ]
    svc = _service(recs)
    assert _badge_map(svc)["module_clear"]["unlocked"] is True


def test_badge_module_clear_fallback_without_course_plan(monkeypatch):
    import deeptutor.services.achievements as mod

    monkeypatch.setattr(mod, "_load_course_plan", lambda: None)

    recs = [_rec(task_id=f"task{i}", f1=0.8, ts=f"2026-08-0{d}T10:00:00+00:00") for i, d in zip(range(1, 6), range(1, 6))]
    svc = _service(recs)
    assert _badge_map(svc)["module_clear"]["unlocked"] is True


def test_all_badges_unlocked_ordering():
    svc = _service([_rec(ts="2026-08-01T10:00:00+00:00")])
    badges = svc.badges()
    assert len(badges) == 6
    assert [b["id"] for b in badges] == [b["id"] for b in BADGES]


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


def test_badge_module_clear_fallback_ignored_when_plan_present(monkeypatch):
    # plan authoritative: practiced 5 distinct tasks but cleared no module -> NOT unlocked
    import deeptutor.services.achievements as mod

    plan = {"modules": [{"name": "标注基础", "tasks": ["task1", "task3", "task5"]}]}
    monkeypatch.setattr(mod, "_load_course_plan", lambda: plan)

    recs = [
        _rec(task_id="task1", f1=0.8, ts="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task2", f1=0.8, ts="2026-08-02T10:00:00+00:00"),
        _rec(task_id="task4", f1=0.8, ts="2026-08-03T10:00:00+00:00"),
        _rec(task_id="task6", f1=0.8, ts="2026-08-04T10:00:00+00:00"),
        _rec(task_id="task7", f1=0.8, ts="2026-08-05T10:00:00+00:00"),
    ]
    svc = _service(recs)
    assert _badge_map(svc)["module_clear"]["unlocked"] is False


def test_badge_module_clear_fallback_when_plan_has_no_modules(monkeypatch):
    import deeptutor.services.achievements as mod

    monkeypatch.setattr(mod, "_load_course_plan", lambda: {"modules": []})

    recs = [_rec(task_id=f"task{i}", f1=0.8, ts=f"2026-08-0{d}T10:00:00+00:00") for i, d in zip(range(1, 6), range(1, 6))]
    svc = _service(recs)
    assert _badge_map(svc)["module_clear"]["unlocked"] is True


def test_badge_tolerates_missing_timestamp():
    svc = _service([
        {"type": "annotation_exercise", "task_id": "task1", "f1": 0.9, "timestamp": None},
        _rec(type="diagnosis", task_id="", ts="2026-08-01T10:00:00+00:00"),
        _rec(task_id="task2", f1=0.95, ts="2026-08-01T11:00:00+00:00"),
        {"type": "annotation_exercise", "task_id": "task3", "f1": 0.9, "timestamp": ""},
    ])
    badges = _badge_map(svc)
    assert len(badges) == 6
    assert badges["first_step"]["unlocked"] is True
    assert badges["first_pass"]["unlocked"] is True
    assert isinstance(badges["first_pass"]["unlocked_at"], str) and badges["first_pass"]["unlocked_at"]
    assert badges["first_step"]["unlocked_at"] == "2026-08-01T10:00:00+00:00"
    assert badges["module_clear"]["unlocked"] is False


def test_empty_records_all_badges_locked():
    svc = _service([])
    badges = _badge_map(svc)
    for badge in BADGES:
        assert badges[badge["id"]]["unlocked"] is False
        assert badges[badge["id"]]["unlocked_at"] is None


def test_unlocked_at_is_nonempty_string_when_unlocked():
    svc = _service([_rec(type="diagnosis", ts="2026-08-01T10:00:00+00:00")])
    badges = _badge_map(svc)
    assert badges["first_step"]["unlocked"] is True
    assert isinstance(badges["first_step"]["unlocked_at"], str)
    assert badges["first_step"]["unlocked_at"]
