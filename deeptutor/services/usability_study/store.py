"""File-backed store for usability study records.

All records live under a study root (admin workspace by default). The store is
append-friendly: runs are immutable once written, events are keyed by run, and
manual corrections / deletion requests are kept as append-only journals so the
report generator can recompute deterministically after any deletion or edit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from deeptutor.services.file_io import atomic_write_json

from .models import (
    DeletionRequest,
    Issue,
    ManualCorrection,
    Quote,
    StudyEvent,
    StudyRun,
    utcnow,
)

RUNS_FILENAME = "runs.json"
EVENTS_DIRNAME = "events"
CORRECTIONS_FILENAME = "corrections.jsonl"
DELETIONS_FILENAME = "deletions.jsonl"
ISSUES_FILENAME = "issues.json"
QUOTES_FILENAME = "quotes.json"


class UsabilityStudyStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs_file = root / RUNS_FILENAME
        self.events_dir = root / EVENTS_DIRNAME
        self.corrections_file = root / CORRECTIONS_FILENAME
        self.deletions_file = root / DELETIONS_FILENAME
        self.issues_file = root / ISSUES_FILENAME
        self.quotes_file = root / QUOTES_FILENAME

    # ── runs ────────────────────────────────────────────────────────────

    def list_runs(self) -> list[StudyRun]:
        data = self._read_json(self.runs_file, default={"runs": []})
        return [StudyRun.model_validate(item) for item in data.get("runs", [])]

    def get_run(self, run_id: str) -> StudyRun | None:
        for run in self.list_runs():
            if run.run_id == run_id:
                return run
        return None

    def add_run(self, run: StudyRun) -> StudyRun:
        runs = self.list_runs()
        if any(existing.run_id == run.run_id for existing in runs):
            raise ValueError(f"运行已存在：{run.run_id}")
        runs.append(run)
        self._write_json(self.runs_file, {"runs": [r.model_dump(mode="json") for r in runs]})
        return run

    def save_runs(self, runs: Iterable[StudyRun]) -> None:
        self._write_json(
            self.runs_file,
            {"runs": [r.model_dump(mode="json") for r in runs]},
        )

    # ── events ──────────────────────────────────────────────────────────

    def add_events(self, events: list[StudyEvent]) -> None:
        if not events:
            return
        run_id = events[0].run_id
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"运行不存在：{run_id}")
        for event in events:
            if event.run_id != run_id:
                raise ValueError("同一批次事件必须属于同一运行")
        path = self.events_dir / f"{run_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def list_events(self, run_id: str) -> list[StudyEvent]:
        path = self.events_dir / f"{run_id}.jsonl"
        if not path.exists():
            return []
        try:
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            return []
        return [StudyEvent.model_validate(item) for item in rows]

    # ── manual corrections (append-only) ────────────────────────────────

    def add_correction(self, correction: ManualCorrection) -> None:
        self._append_jsonl(self.corrections_file, correction.model_dump(mode="json"))

    def list_corrections(self) -> list[ManualCorrection]:
        return [
            ManualCorrection.model_validate(item)
            for item in self._read_jsonl(self.corrections_file)
        ]

    # ── deletion requests (append-only audit) ───────────────────────────

    def add_deletion_request(self, request: DeletionRequest) -> None:
        self._append_jsonl(self.deletions_file, request.model_dump(mode="json"))

    def list_deletion_requests(self) -> list[DeletionRequest]:
        return [
            DeletionRequest.model_validate(item)
            for item in self._read_jsonl(self.deletions_file)
        ]

    def mark_deletion_actioned(self, participant_id: str, *, scope: str, requested_by: str) -> bool:
        requests = self.list_deletion_requests()
        target = next(
            (r for r in requests if r.participant_id == participant_id and r.scope == scope),
            None,
        )
        if target is None:
            return False
        target.actioned_at = utcnow()
        target.requested_by = requested_by
        self._rewrite_jsonl(self.deletions_file, [r.model_dump(mode="json") for r in requests])
        return True

    # ── issues / quotes ─────────────────────────────────────────────────

    def list_issues(self) -> list[Issue]:
        data = self._read_json(self.issues_file, default={"issues": []})
        return [Issue.model_validate(item) for item in data.get("issues", [])]

    def add_issue(self, issue: Issue) -> None:
        issues = self.list_issues()
        issues.append(issue)
        self._write_json(self.issues_file, {"issues": [i.model_dump(mode="json") for i in issues]})

    def list_quotes(self) -> list[Quote]:
        data = self._read_json(self.quotes_file, default={"quotes": []})
        return [Quote.model_validate(item) for item in data.get("quotes", [])]

    def add_quote(self, quote: Quote) -> None:
        quotes = self.list_quotes()
        quotes.append(quote)
        self._write_json(self.quotes_file, {"quotes": [q.model_dump(mode="json") for q in quotes]})

    # ── low-level helpers ───────────────────────────────────────────────

    def _read_json(self, path: Path, *, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, data)

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            return [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError):
            return []

    def _rewrite_jsonl(self, path: Path, records: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def participant_runs(store: UsabilityStudyStore, participant_id: str) -> list[StudyRun]:
    return [run for run in store.list_runs() if run.participant_id == participant_id]


__all__ = ["UsabilityStudyStore", "participant_runs"]
