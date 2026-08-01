"""Persistent learning-record store for the annotation-coach persona.

The coach writes structured synapse records (diagnosis / theory_mastered /
annotation_exercise) that drive the /progress dashboard and let the coach
resume a learner from their last checkpoint. These are distinct from the
user-preference records `write_memory` handles, so they live in their own
JSONL store rather than the L3 preferences doc.

Layout (per-user, resolved through PathService):
    data/user/workspace/learning/records.jsonl

Each line is one JSON record. Records are append-only; the dashboard reads
them back in insertion order. A short human-readable summary is also
mirrored into L3 ``recent.md`` so ``read_memory`` surfaces the coach's
resume point to the next conversation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RECORD_TYPES = ("diagnosis", "theory_mastered", "annotation_exercise")

# Field requirements per record type — the coach must supply these for the
# dashboard to render meaningful per-type cards / series.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "diagnosis": ("teaching_mode",),
    "theory_mastered": ("knowledge_point", "readiness"),
    "annotation_exercise": ("task_id",),
}

_locks: dict[str, asyncio.Lock] = {}


def _lock_for(path: Path) -> asyncio.Lock:
    key = str(path)
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


class LearningRecordStore:
    """Append-only JSONL store for structured learning records."""

    def __init__(self) -> None:
        from deeptutor.services.path_service import get_path_service

        self._root = get_path_service().get_workspace_dir() / "learning"
        self._file = self._root / "records.jsonl"

    @property
    def file(self) -> Path:
        return self._file

    def _ensure_dir(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    def _normalize_record(self, record: dict[str, Any]) -> None:
        """Fill dual-SOT scope + feynman pattern fields with safe defaults.

        Backwards-compatible: old records without ``scope`` are inferred by
        type. An ``error_pattern`` that isn't null must carry a
        ``pattern_status`` (defaults to ``unconfirmed``) so a single-session
        observation is never treated as a stable profile.
        """
        scope = record.get("scope")
        if scope not in ("learner", "progress"):
            record["scope"] = "learner" if record.get("type") == "diagnosis" else "progress"
        if record.get("error_pattern") and not record.get("pattern_status"):
            record["pattern_status"] = "unconfirmed"

    def list_records(self, scope: str | None = None) -> list[dict[str, Any]]:
        """Return all persisted records in insertion order, optionally by scope."""
        records = self._read_records()
        if scope:
            records = [r for r in records if r.get("scope") == scope]
        return records

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.list_records()[-limit:]

    def save_brief(self, brief: dict[str, Any]) -> Path:
        """Persist a Phase-0 diagnosis brief (lumen-style intake contract).

        Lives outside the records stream so course shape and learner state
        stay separable. Returns the written file path.
        """
        self._ensure_dir()
        path = self._root / "brief.json"
        import json as _json

        with open(path, "w", encoding="utf-8") as handle:
            _json.dump(brief, handle, ensure_ascii=False, indent=2)
        return path

    def get_brief(self) -> dict[str, Any] | None:
        """Load the latest diagnosis brief, or ``None`` if absent."""
        path = self._root / "brief.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    # ── decision audit log (lumen: audit every agent decision) ────────────

    def _decision_file(self) -> Path:
        return self._root / "decisions.jsonl"

    def list_decisions(self, limit: int = 20) -> list[dict[str, Any]]:
        path = self._decision_file()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    async def append_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Append one coach decision with its rationale (audit trail)."""
        if "timestamp" not in decision:
            decision["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        self._ensure_dir()
        line = json.dumps(decision, ensure_ascii=False, separators=(",", ":"))
        path = self._decision_file()
        async with _lock_for(path):
            from deeptutor.services.file_io import atomic_write_text

            def _write() -> None:
                existing = path.read_text(encoding="utf-8") if path.exists() else ""
                atomic_write_text(path, existing + ("" if existing.endswith("\n") else "\n") + line + "\n")

            await asyncio.to_thread(_write)
        return decision

    # ── teaching-plan evaluations (adversarial review results) ────────────

    def _evaluation_file(self) -> Path:
        return self._root / "evaluations.jsonl"

    def list_evaluations(self, limit: int = 10) -> list[dict[str, Any]]:
        path = self._evaluation_file()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append(row)
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    async def append_evaluation(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        """Persist a full adversarial teaching-plan evaluation."""
        if "timestamp" not in evaluation:
            evaluation["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        self._ensure_dir()
        line = json.dumps(evaluation, ensure_ascii=False, separators=(",", ":"))
        path = self._evaluation_file()
        async with _lock_for(path):
            from deeptutor.services.file_io import atomic_write_text

            def _write() -> None:
                existing = path.read_text(encoding="utf-8") if path.exists() else ""
                atomic_write_text(path, existing + ("" if existing.endswith("\n") else "\n") + line + "\n")

            await asyncio.to_thread(_write)
        return evaluation

    def _read_records(self) -> list[dict[str, Any]]:
        if not self._file.exists():
            return []
        records: list[dict[str, Any]] = []
        with open(self._file, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed learning record line: %r", line[:80])
                    continue
                if isinstance(record, dict):
                    records.append(record)
        return records

    async def append(self, record: dict[str, Any]) -> dict[str, Any]:
        """Atomically append one record and mirror a summary into L3 recent.md.

        Returns the persisted record (timestamp added if absent).
        """
        self._normalize_record(record)
        if "timestamp" not in record:
            record["timestamp"] = datetime.now(tz=timezone.utc).isoformat()

        self._ensure_dir()
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        async with _lock_for(self._file):
            from deeptutor.services.file_io import atomic_write_text

            def _write() -> None:
                existing = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
                atomic_write_text(
                    self._file,
                    existing + ("" if existing.endswith("\n") else "\n") + line + "\n",
                )

            await asyncio.to_thread(_write)

        await self._mirror_recent_summary(record)
        return record

    async def _mirror_recent_summary(self, record: dict[str, Any]) -> None:
        """Append a one-line human summary to L3 recent.md for ``read_memory``."""
        summary = _summary_line(record)
        if not summary:
            return
        try:
            from deeptutor.services.memory import get_memory_store
            from deeptutor.services.memory.trace import TraceEvent

            store = get_memory_store()
            event = TraceEvent.new("chat", "learning_record_written", record)
            await store.emit(event)
            await store.append_learning_summary(
                text=summary,
                ref=event.id,
            )
        except Exception as exc:  # never let mirroring break the write
            logger.warning("Failed to mirror learning summary into recent.md: %s", exc)


def _summary_line(record: dict[str, Any]) -> str:
    """Render a compact human summary for the memory workbench / read_memory."""
    kind = record.get("type")
    ts = (record.get("timestamp") or "")[:10]
    if kind == "annotation_exercise":
        f1 = record.get("f1")
        f1_text = f"{f1:.0%}" if isinstance(f1, (int, float)) else "?"
        return (
            f"{ts} 练习 {record.get('task_id', '?')} ({record.get('knowledge_point', '')}) "
            f"F1={f1_text} readiness={record.get('readiness', '?')}"
        ).strip()
    if kind == "theory_mastered":
        return (
            f"{ts} 掌握知识点: {record.get('knowledge_point', '?')} "
            f"readiness={record.get('readiness', '?')}"
        ).strip()
    if kind == "diagnosis":
        return (
            f"{ts} 诊断完成: 教学模式={record.get('teaching_mode', '?')} "
            f"目标={record.get('goal_type', '?')}"
        ).strip()
    return ""


def validate_record(record: dict[str, Any]) -> str | None:
    """Validate a candidate record; return an error string or ``None``."""
    if not isinstance(record, dict):
        return "record must be a JSON object"
    kind = record.get("type")
    if kind not in RECORD_TYPES:
        return f"type must be one of: {', '.join(RECORD_TYPES)}"
    missing = [f for f in _REQUIRED_FIELDS.get(kind, ()) if not record.get(f)]
    if missing:
        return f"record of type {kind!r} is missing required fields: {', '.join(missing)}"
    return None


class LearningStats:
    """Shared aggregation over the learning store.

    Used by both the /api/v1/profile router and the CLI teaching commands
    (``/progress``, ``/concept-map``) so the two never drift apart.
    """

    def __init__(self, store: LearningRecordStore | None = None) -> None:
        self._store = store or LearningRecordStore()

    def _progress(self) -> list[dict[str, Any]]:
        return self._store.list_records(scope="progress")

    def _learners(self) -> list[dict[str, Any]]:
        return self._store.list_records(scope="learner")

    @staticmethod
    def _latest_diagnosis(entries: list[dict]) -> dict | None:
        for entry in reversed(entries):
            if entry.get("type") == "diagnosis":
                return entry
        return None

    @staticmethod
    def _exercises(entries: list[dict]) -> list[dict]:
        return [e for e in entries if e.get("type") == "annotation_exercise"]

    @staticmethod
    def _theory(entries: list[dict]) -> list[dict]:
        return [e for e in entries if e.get("type") == "theory_mastered"]

    def overview(self) -> dict[str, Any]:
        progress = self._progress()
        diagnosis = self._latest_diagnosis(self._learners())
        exercises = self._exercises(progress)
        theory = self._theory(progress)

        total = len(exercises)
        passed = sum(
            1 for e in exercises if float(e.get("f1") or e.get("accuracy") or 0) >= 0.7
        )
        latest = None
        for e in reversed(exercises):
            if "f1" in e:
                latest = {
                    "f1": float(e["f1"]),
                    "precision": float(e.get("precision", 0)),
                    "recall": float(e.get("recall", 0)),
                }
                break

        return {
            "total_tasks_completed": total,
            "tasks_passed": passed,
            "pass_rate": round(passed / total, 2) if total else 0,
            "total_theory_mastered": len(theory),
            "latest_f1": latest["f1"] if latest else None,
            "latest_precision": latest["precision"] if latest else None,
            "latest_recall": latest["recall"] if latest else None,
            "teaching_mode": diagnosis.get("teaching_mode") if diagnosis else None,
            "mission": diagnosis.get("mission") if diagnosis else None,
            "goal_type": diagnosis.get("goal_type") if diagnosis else None,
        }

    def radar(self) -> dict[str, Any]:
        exercises = self._exercises(self._progress())
        bbox_precision = 0.0
        label_accuracy = 0.0
        recall_completeness = 0.0
        consistency = 0.0
        n = 0

        for e in exercises:
            f1 = float(e.get("f1") or 0)
            precision = float(e.get("precision") or 0)
            recall = float(e.get("recall") or 0)
            bbox_precision += precision
            recall_completeness += recall
            n += 1
            if "classification" not in str(e.get("task_id", "")):
                label_accuracy += f1
            score = str(e.get("teach_back_score", "") or "1/1/1").split("/")
            try:
                consistency += float(score[0]) / 3.0
            except (ValueError, IndexError):
                consistency += 0.5

        denom = max(n, 1)
        knowledge = len(self._theory(self._progress()))
        return {
            "dimensions": [
                {"name": "框精度", "english": "box_precision", "score": round(bbox_precision / denom * 100, 1), "max": 100},
                {"name": "标签准确", "english": "label_accuracy", "score": round(label_accuracy / denom * 100, 1), "max": 100},
                {"name": "完整性", "english": "recall", "score": round(recall_completeness / denom * 100, 1), "max": 100},
                {"name": "一致性", "english": "consistency", "score": round(consistency / denom * 100, 1), "max": 100},
                {"name": "知识掌握", "english": "knowledge", "score": round(min(knowledge / 29 * 100, 100.0), 1), "max": 100},
            ],
        }

    def f1_trend(self) -> dict[str, Any]:
        points: list[dict] = []
        for e in sorted(self._exercises(self._progress()), key=lambda x: x.get("timestamp", "")):
            points.append({
                "task_id": e.get("task_id", "?"),
                "f1": round(float(e.get("f1") or 0) * 100, 1),
                "precision": round(float(e.get("precision") or 0) * 100, 1),
                "recall": round(float(e.get("recall") or 0) * 100, 1),
                "difficulty": e.get("difficulty", "easy"),
                "date": (e.get("timestamp", "") or "")[:10],
            })
        return {"points": points}

    def skill_tree(self) -> dict[str, Any]:
        progress = self._progress()
        mastered_kps: set[str] = set()
        for e in self._exercises(progress):
            if float(e.get("f1") or 0) >= 0.7:
                mastered_kps.update(e.get("knowledge_points") or [])
        for e in self._theory(progress):
            if e.get("readiness") in ("advance", "advance_with_caution") and e.get("knowledge_point"):
                mastered_kps.add(e["knowledge_point"])

        from deeptutor.tools.competency_tool import _load_competency_tree

        tree = _load_competency_tree().get("tree", {})

        def _build(node: dict) -> dict:
            result: dict[str, Any] = {
                "name": node.get("name", ""),
                "id": node.get("id", ""),
                "level": node.get("level", 1),
            }
            if node.get("level", 1) == 4:
                result["mastered"] = node.get("name", "") in mastered_kps
            elif "children" in node or "skills" in node:
                children = []
                for child in node.get("children", []):
                    children.append(_build(child))
                for skill in node.get("skills", []):
                    children.append(_build(skill))
                result["children"] = children
                leaves = [c for c in children if c.get("level", 1) == 4]
                mastered = [c for c in leaves if c.get("mastered", False)]
                result["mastered_count"] = len(mastered)
                result["total_leaves"] = len(leaves) or 1
            return result

        return {"tree": _build(tree)}


__all__ = [
    "LearningRecordStore",
    "LearningStats",
    "RECORD_TYPES",
    "validate_record",
]
