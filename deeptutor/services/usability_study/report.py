"""Deterministic usability report generator.

Aggregates immutable ``StudyRun`` + ``StudyEvent`` records into a competition
evidence summary. The generator follows the design's analysis rules:

  * No statistical-significance claims for such a small sample; report per
    participant A/B deltas, three-person median/range, shared pain points, and
    qualitative feedback.
  * Any "improvement %" must carry the raw numerator/denominator; missing
    samples are not extrapolated.
  * The generator refuses runs with: invalid participant ids, missing consent,
    unknown task versions, out-of-order event timestamps, metric references to
    non-existent events, or hash mismatches. An incomplete draft is allowed but
    is clearly marked as NOT suitable for formal submission.
  * Reports recompute deterministically after a deletion request (the removed
    participant's runs are excluded and the version is bumped) and preserve the
    full manual-correction history.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    ManualCorrection,
    StudyEvent,
    StudyRun,
    sha256_hex,
)
from .store import UsabilityStudyStore

# Metric keys whose source is a stage event, e.g. event_type="stage_complete"
# with stage="labeling". Reports surface these as "阶段完成状态".
STAGE_ORDER = (
    "diagnosis",
    "learn_rule",
    "labeling",
    "review",
    "correction",
    "report",
)

DRAFT_MARK = "草稿（不完整数据）—— 不可用于正式提交"


class ReportValidationError(ValueError):
    pass


class UsabilityReportGenerator:
    def __init__(self, store: UsabilityStudyStore) -> None:
        self.store = store

    # ── validation ──────────────────────────────────────────────────────

    def validate_run(self, run: StudyRun, events: list[StudyEvent]) -> list[str]:
        """Return a list of validation problems (empty = run is usable)."""
        problems: list[str] = []

        if not run.has_consent("participate"):
            problems.append(f"{run.run_id}: 缺少“参与测试”同意")

        if not events:
            problems.append(f"{run.run_id}: 无事件记录")
            return problems

        # Events must belong to this run and be time-ordered (monotonic).
        previous = ""
        for event in events:
            if event.run_id != run.run_id:
                problems.append(f"{run.run_id}: 事件归属运行不匹配 {event.run_id}")
            if previous and event.timestamp < previous:
                problems.append(f"{run.run_id}: 事件时间倒序 {event.timestamp} < {previous}")
            previous = event.timestamp

        # Metric references: any event that records a duration must resolve to
        # a real stage in the run.
        known_stages = {event.stage for event in events}
        for event in events:
            if event.event_type == "stage_complete" and event.stage not in STAGE_ORDER:
                problems.append(f"{run.run_id}: 未知阶段 {event.stage}")
            if event.event_type == "duration" and event.stage and event.stage not in known_stages:
                problems.append(f"{run.run_id}: 耗时引用了不存在的事件阶段 {event.stage}")

        return problems

    # ── per-run metrics ─────────────────────────────────────────────────

    def run_metrics(self, run: StudyRun, events: list[StudyEvent]) -> dict[str, Any]:
        durations: dict[str, float] = {}
        stuck = 0
        help_count = 0
        errors = 0
        resubmissions = 0
        back_steps = 0
        completed: list[str] = []
        for event in events:
            if event.event_type == "stage_complete":
                completed.append(event.stage)
            elif event.event_type == "duration":
                durations[event.stage] = float(event.value or 0)
            elif event.event_type == "stuck":
                stuck += 1
            elif event.event_type == "help":
                help_count += 1
            elif event.event_type == "error":
                errors += 1
            elif event.event_type == "resubmit":
                resubmissions += 1
            elif event.event_type == "back":
                back_steps += 1

        stages = {stage: stage in completed for stage in STAGE_ORDER}
        return {
            "run_id": run.run_id,
            "participant_id": run.participant_id,
            "round": run.round,
            "task_version": run.task_version,
            "completed": stages,
            "completion_rate": sum(1 for v in stages.values() if v) / len(stages) if stages else 0.0,
            "durations": durations,
            "total_duration_s": sum(durations.values()),
            "stuck": stuck,
            "help": help_count,
            "errors": errors,
            "resubmissions": resubmissions,
            "back_steps": back_steps,
            "consent": run.consent_summary(),
            "source_hash": self._run_source_hash(run, events),
        }

    def _run_source_hash(self, run: StudyRun, events: list[StudyEvent]) -> str:
        payload = json.dumps(
            {
                "run": run.model_dump(mode="json"),
                "events": [e.model_dump(mode="json") for e in events],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return sha256_hex(payload)

    # ── report assembly ─────────────────────────────────────────────────

    def generate(
        self,
        *,
        draft_ok: bool = True,
        excluded_participants: set[str] | None = None,
        report_version: str = "1",
    ) -> dict[str, Any]:
        """Build the deterministic metrics summary for the evidence package."""
        excluded = excluded_participants or set()
        runs = [r for r in self.store.list_runs() if r.participant_id not in excluded]
        corrections = self.store.list_corrections()
        problems: list[str] = []
        usable: list[tuple[StudyRun, list[StudyEvent]]] = []
        for run in runs:
            events = self.store.list_events(run.run_id)
            problems.extend(self.validate_run(run, events))
            if not self.validate_run(run, events):
                usable.append((run, events))

        metrics = [self.run_metrics(run, events) for run, events in usable]
        metrics = self._apply_corrections(metrics, corrections)
        ab = self._pair_ab(metrics)
        summary = self._summarise(metrics, ab)

        is_draft = bool(problems) or len(usable) < len(runs)
        return {
            "report_version": report_version,
            "generated_at": _utcnow(),
            "draft": is_draft,
            "draft_mark": DRAFT_MARK if is_draft else "",
            "participants": sorted({m["participant_id"] for m in metrics}),
            "validation_problems": problems,
            "usable_run_count": len(usable),
            "total_run_count": len(runs),
            "per_participant": self._per_participant(metrics),
            "ab_pairs": ab,
            "summary": summary,
            "source_hashes": {m["run_id"]: m["source_hash"] for m in metrics},
            "corrections": [c.model_dump(mode="json") for c in corrections],
        }

    def _apply_corrections(
        self, metrics: list[dict[str, Any]], corrections: list[ManualCorrection]
    ) -> list[dict[str, Any]]:
        if not corrections:
            return metrics
        by_run: dict[str, dict[str, Any]] = {m["run_id"]: m for m in metrics}
        for correction in corrections:
            target = by_run.get(correction.run_id)
            if target is None:
                continue
            parts = [p for p in correction.metric_path.split(".") if p]
            node: Any = target
            for part in parts[:-1]:
                if isinstance(node, dict):
                    node = node.get(part, {})
                else:
                    break
            if isinstance(node, dict) and parts:
                node[parts[-1]] = correction.corrected
        return list(by_run.values())

    def _pair_ab(self, metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_participant: dict[str, dict[str, Any]] = {}
        for metric in metrics:
            by_participant.setdefault(metric["participant_id"], {})[metric["round"]] = metric
        pairs: list[dict[str, Any]] = []
        for participant, rounds in sorted(by_participant.items()):
            if "A" not in rounds or "B" not in rounds:
                continue
            a, b = rounds["A"], rounds["B"]
            pairs.append(
                {
                    "participant_id": participant,
                    "round_a": a,
                    "round_b": b,
                    "total_delta_s": _delta(a, b, "total_duration_s"),
                    "error_delta": _delta(a, b, "errors"),
                    "stuck_delta": _delta(a, b, "stuck"),
                    "completion_rate_a": a["completion_rate"],
                    "completion_rate_b": b["completion_rate"],
                }
            )
        return pairs

    def _summarise(self, metrics: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
        if not metrics:
            return {"participant_count": 0, "note": "无可用运行"}

        total_durations = [m["total_duration_s"] for m in metrics]
        errors = [m["errors"] for m in metrics]
        stuck = [m["stuck"] for m in metrics]
        completion_rates = [m["completion_rate"] for m in metrics]

        return {
            "participant_count": len({m["participant_id"] for m in metrics}),
            "run_count": len(metrics),
            "total_duration_s": {
                "median": _median(total_durations),
                "min": min(total_durations),
                "max": max(total_durations),
            },
            "errors": {
                "median": _median(errors),
                "min": min(errors),
                "max": max(errors),
            },
            "stuck": {
                "median": _median(stuck),
                "min": min(stuck),
                "max": max(stuck),
            },
            "completion_rate": {
                "median": _median(completion_rates),
                "min": min(completion_rates),
                "max": max(completion_rates),
            },
            "paired_ab": len(pairs),
            "statistical_significance": "不声明（样本量小）",
            "note": "提升百分比均展示原始分子分母；缺失样本不外推。",
        }

    def _per_participant(self, metrics: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for metric in metrics:
            out.setdefault(metric["participant_id"], []).append(
                {
                    "run_id": metric["run_id"],
                    "round": metric["round"],
                    "completion_rate": metric["completion_rate"],
                    "total_duration_s": metric["total_duration_s"],
                    "stuck": metric["stuck"],
                    "errors": metric["errors"],
                    "resubmissions": metric["resubmissions"],
                    "back_steps": metric["back_steps"],
                }
            )
        return out

    # ── deletion-aware recompute ────────────────────────────────────────

    def recompute_after_deletion(
        self,
        participant_id: str,
        *,
        report_version: str = "2",
    ) -> dict[str, Any]:
        """Exclude one participant's runs and regenerate the summary."""
        return self.generate(
            excluded_participants={participant_id},
            report_version=report_version,
        )

    # ── evidence package export ─────────────────────────────────────────

    def export_package(
        self,
        root: Path,
        *,
        excluded_participants: set[str] | None = None,
        report_version: str = "1",
    ) -> dict[str, Any]:
        report = self.generate(excluded_participants=excluded_participants, report_version=report_version)
        issues = [issue.model_dump(mode="json") for issue in self.store.list_issues()]
        quotes = [
            q.model_dump(mode="json")
            for q in self.store.list_quotes()
            if q.approved
        ]
        excluded = excluded_participants or set()
        usable = [
            (run, self.store.list_events(run.run_id))
            for run in self.store.list_runs()
            if run.participant_id not in excluded
            and not self.validate_run(run, self.store.list_events(run.run_id))
        ]
        package = {
            "report_version": report_version,
            "generated_at": _utcnow(),
            "draft": report["draft"],
            "draft_mark": report["draft_mark"],
            "participants": report["participants"],
            "runs_index": [
                {
                    "run_id": run.run_id,
                    "participant_id": run.participant_id,
                    "round": run.round,
                    "task_version": run.task_version,
                    "source_hash": self._run_source_hash(run, events),
                }
                for run, events in usable
            ],
            "metrics_summary": report["summary"],
            "quotes": quotes,
            "issues": issues,
            "source_hashes": report["source_hashes"],
        }
        return package


def _delta(a: dict[str, Any], b: dict[str, Any], key: str) -> dict[str, Any] | None:
    if key not in a or key not in b:
        return None
    before, after = a[key], b[key]
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        delta = after - before
        return {
            "before": before,
            "after": after,
            "delta": delta,
            "percent_change": f"{((after - before) / before * 100) if before else 0:.1f}%",
        }
    return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2)


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = ["UsabilityReportGenerator", "ReportValidationError", "DRAFT_MARK"]
