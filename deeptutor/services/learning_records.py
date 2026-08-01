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

    def list_records(
        self, scope: str | None = None, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        """Return persisted records in insertion order, optionally by scope.

        Archived records (merged away by reflection) are excluded unless
        ``include_archived=True``.
        """
        records = self._read_records()
        if not include_archived:
            records = [r for r in records if not r.get("archived")]
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

    def reflect(self) -> dict[str, Any]:
        """Memory evolution (EverOS Reflection): merge / dedupe / archive.

        Clusters active exercise + theory records by (type, task_id,
        knowledge_point). For clusters with >1 record:
          * keeps the LATEST as the canonical record (latest F1/metrics);
          * merges error_pattern evidence from older records and promotes
            ``pattern_status`` to ``confirmed`` when a pattern recurs ≥2×;
          * merges knowledge_points (deduped);
          * marks older records ``archived`` (excluded from stats).
        ``reflect()`` is a pure in-memory transformation of the JSONL truth —
        nothing is deleted, so it is reversible by un-archiving.
        """
        records = self._read_records()
        active = [r for r in records if not r.get("archived")]
        archived = [r for r in records if r.get("archived")]

        clusters: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        standalone: list[dict[str, Any]] = []
        for r in active:
            kind = r.get("type")
            if kind in ("annotation_exercise", "theory_mastered"):
                key = (kind, str(r.get("task_id", "")), str(r.get("knowledge_point", "")))
                if key[1] or key[2]:  # needs a clustering anchor
                    clusters.setdefault(key, []).append(r)
                    continue
            standalone.append(r)

        merged_count = 0
        archived_count = 0
        out: list[dict[str, Any]] = []
        for group in clusters.values():
            if len(group) <= 1:
                out.extend(group)
                continue
            group.sort(key=lambda x: x.get("timestamp", ""))
            latest = dict(group[-1])
            older = group[:-1]

            # merge error_pattern evidence + promote repeated patterns
            patterns: dict[str, int] = {}
            evidence: list[Any] = []
            for r in group:
                ep = r.get("error_pattern")
                if ep:
                    patterns[ep] = patterns.get(ep, 0) + 1
                for e in (r.get("pattern_evidence") or []):
                    if e not in evidence:
                        evidence.append(e)
            if evidence:
                latest["pattern_evidence"] = evidence
                if any(v >= 2 for v in patterns.values()):
                    latest["pattern_status"] = "confirmed"
                else:
                    latest.setdefault("pattern_status", "unconfirmed")

            # merge knowledge_points
            kps: set[str] = set()
            for r in group:
                kps.update(r.get("knowledge_points") or [])
            if kps:
                latest["knowledge_points"] = sorted(kps)

            latest["merged_count"] = len(group)
            for r in older:
                r["archived"] = True
                archived_count += 1
            out.append(latest)
            out.extend(older)  # archived records stay (reversible truth)
            merged_count += 1

        out.extend(standalone)
        # preserve archived records so reflection stays reversible
        out.extend(archived)
        self._write_all(out)
        return {
            "clusters_merged": merged_count,
            "records_archived": archived_count,
            "active_records": len([r for r in out if not r.get("archived")]),
        }

    def _write_all(self, records: list[dict[str, Any]]) -> None:
        """Rewrite the whole JSONL (truth-preserving). Called by reflect()."""
        self._ensure_dir()
        lines = [
            json.dumps(r, ensure_ascii=False, separators=(",", ":"))
            for r in records
        ]
        from deeptutor.services.file_io import atomic_write_text

        atomic_write_text(self._file, "\n".join(lines) + ("\n" if lines else ""))

    # ── foresights (EverOS: predict what's next, then verify) ──────────────

    def open_foresights(self, limit: int = 1) -> list[dict[str, Any]]:
        """Return the most recent records carrying an unresolved ``foresight``.

        Each entry: ``{"index": <position in file>, "record": {...}}`` so the
        caller can resolve it via :meth:`resolve_foresight`.
        """
        records = self._read_records()
        open_items: list[dict[str, Any]] = []
        for index, r in enumerate(records):
            if r.get("foresight") and not r.get("foresight_verified"):
                open_items.append({"index": index, "record": r})
        return open_items[-limit:]

    def resolve_foresight(
        self, index: int, hit: bool, note: str = ""
    ) -> dict[str, Any] | None:
        """Mark an open foresight as verified (hit or miss).

        Hits become a ``correction``-style learning signal: the record keeps
        its foresight, gains ``foresight_verified=True`` + ``foresight_hit``.
        """
        records = self._read_records()
        if not 0 <= index < len(records):
            return None
        target = records[index]
        target["foresight_verified"] = True
        target["foresight_hit"] = bool(hit)
        if note:
            target["foresight_note"] = note
        self._write_all(records)
        return target

    # ── episodes (EverOS: daily-log grouping for a timeline view) ──────────

    def episodes(self, days: int = 14) -> list[dict[str, Any]]:
        """Group active records into daily episodes, newest first.

        Returns ``[{"date": "YYYY-MM-DD", "records": [...], "count": n}, ...]``
        with one entry per day that has at least one record.
        """
        from datetime import date as _date

        by_day: dict[str, list[dict[str, Any]]] = {}
        for r in self.list_records():  # active only
            day = (r.get("timestamp") or "")[:10]
            if not day:
                continue
            by_day.setdefault(day, []).append(r)

        episodes = []
        for day in sorted(by_day.keys(), reverse=True):
            group = by_day[day]
            episodes.append(
                {"date": day, "records": group, "count": len(group)}
            )
            if len(episodes) >= days:
                break
        return episodes

    # ── atomic facts (EverOS: standalone mastered-fact layer) ──────────────

    def _fact_file(self) -> Path:
        return self._root / "facts.jsonl"

    def list_facts(self) -> list[dict[str, Any]]:
        path = self._fact_file()
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
        return rows

    def facts(self) -> dict[str, Any]:
        """Derive atomic facts from active records (EverOS atomic_facts).

        A fact is one ``knowledge_point`` that the learner has evidenced as
        mastered (practice F1 ≥ 0.7 OR theory readiness advance). Returning
        the derived set is enough for the skill tree / dashboard; we do not
        duplicate storage — the records are the source of truth.
        """
        mastered: dict[str, str] = {}
        for e in [
            r for r in self.list_records(scope="progress")
            if r.get("type") == "annotation_exercise"
        ]:
            if float(e.get("f1") or 0) >= 0.7:
                for kp in (e.get("knowledge_points") or []):
                    mastered[kp] = "practice"
        for e in [
            r for r in self.list_records(scope="progress")
            if r.get("type") == "theory_mastered"
        ]:
            if e.get("readiness") in ("advance", "advance_with_caution") and e.get("knowledge_point"):
                mastered[e["knowledge_point"]] = "theory"
        facts = [
            {"knowledge_point": kp, "evidence": src}
            for kp, src in sorted(mastered.items())
        ]
        return {"facts": facts, "count": len(facts)}

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


class TeachingChangelog:
    """Versioned record of coach-flow improvements (Self-Improving loop).

    Each entry captures ONE applied fix to a teaching flow file: the target
    file/section, what changed, why (from the adversarial review), and the new
    version. Nothing is deleted — a ``previous`` snapshot is kept so flows are
    rollback-able. Lives at ``workspace/learning/teaching_changelog.jsonl``.
    """

    def __init__(self) -> None:
        from deeptutor.services.path_service import get_path_service

        self._root = get_path_service().get_workspace_dir() / "learning"
        self._file = self._root / "teaching_changelog.jsonl"

    def list_changes(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self._file.exists():
            return []
        rows: list[dict[str, Any]] = []
        with open(self._file, encoding="utf-8") as handle:
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

    async def record(self, change: dict[str, Any]) -> dict[str, Any]:
        """Append one applied improvement (single-point fix + rationale)."""
        if "timestamp" not in change:
            change["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        if "version" not in change:
            change["version"] = len(self.list_changes(limit=100000)) + 1
        self._root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(change, ensure_ascii=False, separators=(",", ":"))
        async with _lock_for(self._file):
            from deeptutor.services.file_io import atomic_write_text

            def _write() -> None:
                existing = self._file.read_text(encoding="utf-8") if self._file.exists() else ""
                atomic_write_text(self._file, existing + ("" if existing.endswith("\n") else "\n") + line + "\n")

            await asyncio.to_thread(_write)
        return change


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

    def foresight_stats(self) -> dict[str, Any]:
        """Verified-foresight summary: how often the coach's predictions hold."""
        records = self._store.list_records(include_archived=False)
        with_foresight = [r for r in records if r.get("foresight")]
        verified = [r for r in with_foresight if r.get("foresight_verified")]
        hits = [r for r in verified if r.get("foresight_hit")]
        return {
            "total": len(with_foresight),
            "verified": len(verified),
            "hits": len(hits),
            "hit_rate": round(len(hits) / len(verified), 2) if verified else None,
            "open": len(with_foresight) - len(verified),
        }

    def coach_metrics(self) -> dict[str, Any]:
        """Coach success metrics (agency-agents Success Metrics borrowing).

        All derived from the existing learning store — nothing new to persist.
        """
        progress = self._progress()
        exercises = self._exercises(progress)

        # F1 growth: first vs latest practice
        f1s = [float(e.get("f1") or 0) for e in exercises if e.get("f1")]
        f1_growth = None
        if len(f1s) >= 2 and f1s[0] > 0:
            f1_growth = round((f1s[-1] - f1s[0]) / f1s[0], 3)

        # pattern confirmation: count records with confirmed patterns
        patterns_confirmed = sum(
            1 for e in exercises if e.get("pattern_status") == "confirmed"
        )
        patterns_total = sum(
            1 for e in exercises if e.get("error_pattern")
        )

        # teaching self-improvement: changelog versions
        from deeptutor.services.learning_records import TeachingChangelog

        try:
            improvements = len(TeachingChangelog().list_changes(limit=100000))
        except Exception:
            improvements = 0

        # decision audit completeness
        try:
            decisions = len(self._store.list_decisions(limit=100000))
        except Exception:
            decisions = 0

        foresight = self.foresight_stats()

        return {
            "f1_growth": f1_growth,
            "latest_f1": f1s[-1] if f1s else None,
            "pattern_confirmation_rate": (
                round(patterns_confirmed / patterns_total, 2) if patterns_total else None
            ),
            "foresight_hit_rate": foresight["hit_rate"],
            "teaching_improvements": improvements,
            "decision_audit_entries": decisions,
            "tasks_completed": len(exercises),
        }


__all__ = [
    "LearningRecordStore",
    "LearningStats",
    "TeachingChangelog",
    "RECORD_TYPES",
    "validate_record",
]
