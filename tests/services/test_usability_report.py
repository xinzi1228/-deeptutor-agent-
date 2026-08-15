"""Usability report generator tests.

Covers metric aggregation, missing values, A/B pairing, deletion recompute,
manual-correction history, hash validation, and draft marking. Real participant
testing is a separate manual acceptance step — these tests only verify the
deterministic reporting pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.services.usability_study.models import (
    ConsentRecord,
    DeletionRequest,
    ManualCorrection,
    Quote,
    StudyEvent,
    StudyRun,
    utcnow,
)
from deeptutor.services.usability_study.report import UsabilityReportGenerator
from deeptutor.services.usability_study.store import UsabilityStudyStore


def _consent(participant: str) -> list[ConsentRecord]:
    return [
        ConsentRecord(participant_id=participant, scope="participate", granted=True),
        ConsentRecord(participant_id=participant, scope="screen_record", granted=True),
        ConsentRecord(participant_id=participant, scope="quote", granted=False),
    ]


def _run(
    participant: str,
    round_name: str,
    task_version: str = "traffic-vehicle-1.0",
    *,
    with_consent: bool = True,
) -> StudyRun:
    return StudyRun(
        participant_id=participant,
        round=round_name,  # type: ignore[arg-type]
        task_version=task_version,
        consent=_consent(participant) if with_consent else [],
    )


def _events(run_id: str, *, durations: list[tuple[str, float]], stuck: int = 0) -> list[StudyEvent]:
    events: list[StudyEvent] = []
    base = 1000.0
    for index, (stage, duration) in enumerate(durations):
        base += index * 10 + duration
        events.append(
            StudyEvent(
                run_id=run_id,
                timestamp=utcnow(),
                stage=stage,
                event_type="stage_complete",
            )
        )
        events.append(
            StudyEvent(
                run_id=run_id,
                timestamp=utcnow(),
                stage=stage,
                event_type="duration",
                value=duration,
            )
        )
    for _ in range(stuck):
        events.append(
            StudyEvent(run_id=run_id, timestamp=utcnow(), stage="labeling", event_type="stuck")
        )
    events.append(StudyEvent(run_id=run_id, timestamp=utcnow(), stage="labeling", event_type="error"))
    return events


def _seed_two_rounds(store: UsabilityStudyStore, participant: str) -> None:
    """One participant with A (slower) and B (faster) rounds."""
    run_a = _run(participant, "A")
    store.add_run(run_a)
    store.add_events(_events(run_a.run_id, durations=[("diagnosis", 60), ("labeling", 200), ("report", 40)], stuck=3))
    run_b = _run(participant, "B", task_version="traffic-vehicle-1.1")
    store.add_run(run_b)
    store.add_events(_events(run_b.run_id, durations=[("diagnosis", 40), ("labeling", 120), ("report", 25)], stuck=1))


def _generator(tmp_path: Path) -> tuple[UsabilityStudyStore, UsabilityReportGenerator]:
    store = UsabilityStudyStore(tmp_path / "study")
    return store, UsabilityReportGenerator(store)


# ── aggregation & missing values ──────────────────────────────────────────


def test_report_aggregates_metrics_and_pairs_ab(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    _seed_two_rounds(store, "S01")
    _seed_two_rounds(store, "S02")
    _seed_two_rounds(store, "T01")

    report = generator.generate()
    assert report["draft"] is False
    assert set(report["participants"]) == {"S01", "S02", "T01"}
    assert len(report["ab_pairs"]) == 3
    assert report["summary"]["participant_count"] == 3
    assert report["summary"]["run_count"] == 6
    # B is faster than A for every participant → negative deltas.
    for pair in report["ab_pairs"]:
        assert pair["total_delta_s"]["delta"] < 0


def test_missing_consent_flags_run_and_marks_draft(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    run = _run("S01", "A", with_consent=False)
    store.add_run(run)
    store.add_events(_events(run.run_id, durations=[("diagnosis", 30)]))

    report = generator.generate()
    assert report["draft"] is True
    assert report["draft_mark"]
    assert any("缺少" in problem for problem in report["validation_problems"])


def test_unknown_task_version_rejected_at_model_level(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未知任务版本"):
        _run("S01", "A", task_version="nope")


def test_invalid_participant_rejected_at_model_level() -> None:
    with pytest.raises(ValueError, match="非法参与者"):
        StudyRun(participant_id="S99", round="A", task_version="traffic-vehicle-1.0")


def test_out_of_order_events_marked_draft(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    run = _run("S01", "A")
    store.add_run(run)
    store.add_events(
        [
            StudyEvent(run_id=run.run_id, timestamp="2026-08-15T10:00:02+00:00", stage="labeling", event_type="error"),
            StudyEvent(run_id=run.run_id, timestamp="2026-08-15T10:00:01+00:00", stage="labeling", event_type="stuck"),
        ]
    )
    report = generator.generate()
    assert report["draft"] is True
    assert any("时间倒序" in problem for problem in report["validation_problems"])


# ── manual corrections & deletion recompute ───────────────────────────────


def test_manual_correction_keeps_history_and_applies(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    _seed_two_rounds(store, "S01")
    run_b = next(r for r in store.list_runs() if r.round == "B")

    store.add_correction(
        ManualCorrection(
            run_id=run_b.run_id,
            metric_path="errors",
            original=1,
            corrected=2,
            reason="复查发现第二次误点",
            operator="reviewer-01",
        )
    )
    report = generator.generate()
    assert len(report["corrections"]) == 1
    metric = next(m for m in report["per_participant"]["S01"] if m["round"] == "B")
    # Correction applied to errors after aggregation.
    assert metric["errors"] == 2


def test_deletion_recompute_excludes_participant_and_bumps_version(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    _seed_two_rounds(store, "S01")
    _seed_two_rounds(store, "S02")

    store.add_deletion_request(
        DeletionRequest(participant_id="S02", scope="retention", requested_by="admin")
    )
    report = generator.recompute_after_deletion("S02", report_version="2")
    assert set(report["participants"]) == {"S01"}
    assert report["report_version"] == "2"
    assert report["summary"]["participant_count"] == 1


# ── hashes & evidence package ─────────────────────────────────────────────


def test_source_hashes_are_stable_and_validate(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    _seed_two_rounds(store, "S01")
    report_a = generator.generate()
    report_b = generator.generate()
    assert report_a["source_hashes"] == report_b["source_hashes"]
    run = next(r for r in store.list_runs())
    events = store.list_events(run.run_id)
    assert report_a["source_hashes"][run.run_id] == generator._run_source_hash(run, events)


def test_export_package_has_anonymised_index(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    _seed_two_rounds(store, "S01")
    store.add_quote(Quote(participant_id="S01", round="A", text="比以前好找", approved=True))
    store.add_quote(Quote(participant_id="S01", round="A", text="未批准原话", approved=False))

    package = generator.export_package(tmp_path)
    assert package["draft"] is False
    assert len(package["runs_index"]) == 2
    # Only approved quotes are exported.
    assert len(package["quotes"]) == 1
    assert package["quotes"][0]["text"] == "比以前好找"
    for row in package["runs_index"]:
        assert "participant_id" in row
        assert "source_hash" in row
    serialized = str(package).lower()
    assert "姓名" not in serialized and "password" not in serialized


# ── empty state ───────────────────────────────────────────────────────────


def test_empty_study_reports_zero_runs(tmp_path: Path) -> None:
    store, generator = _generator(tmp_path)
    report = generator.generate()
    assert report["draft"] is False
    assert report["summary"]["participant_count"] == 0
    assert report["participants"] == []
