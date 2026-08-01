"""Learner knowledge graph — deterministic derivative index over learning records.

The JSONL learning records remain the single source of truth; the graph is a
rebuildable derived index seeded from the static competency tree + task bank
ontology and incrementally updated as learning records are appended.
"""

from __future__ import annotations

import json
from pathlib import Path

from deeptutor.services.path_service import get_path_service

MASTERED_F1 = 0.7
ADVANCE_READINESS = ("advance", "advance_with_caution")

SCHEMA_VERSION = 1


class KnowledgeGraphStore:
    """Build, persist, and incrementally update the learner knowledge graph."""

    def __init__(self, root: Path | None = None) -> None:
        if root is not None:
            self._root = root
        else:
            self._root = get_path_service().get_workspace_dir() / "learning"
        self._file = self._root / "knowledge_graph.json"

    # ------------------------------------------------------------------ build

    @staticmethod
    def build(*, tree: dict, bank: dict, records: list[dict]) -> dict:
        """Deterministic full rebuild from ontology + records. Pure function."""
        tree = tree or {}
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        learner_id = "learner:default"
        if isinstance(tree, dict) and "tree" in tree:
            tree = tree["tree"]

        # --- ontology nodes (skills, task groups, tasks) ---
        for group in _iter_task_groups(tree):
            nodes.setdefault(group["id"], {"type": "TaskGroup", "name": group["name"], "level": 2})
        for skill in _iter_skills(tree):
            nodes.setdefault(
                skill["id"],
                {"type": "Skill", "name": skill["name"], "level": 4},
            )
        for task_id, task in bank.items():
            nodes.setdefault(
                task_id,
                {
                    "type": "Task",
                    "name": task.get("title", task_id),
                    "difficulty": task.get("difficulty", ""),
                },
            )

        # --- ontology edges ---
        for skill in _iter_skills(tree):
            for prereq in skill.get("prerequisites", []) or []:
                edges.append(
                    {"source": skill["id"], "type": "prerequisite", "target": prereq["id"]}
                )
        for task_id, task in bank.items():
            for kp in task.get("knowledge_points", []) or []:
                skill_id = _find_skill_id_by_name(tree, kp)
                if skill_id:
                    edges.append({"source": task_id, "type": "requires", "target": skill_id})
            group_id = _task_group_for(tree, task)
            if group_id is not None:
                edges.append({"source": task_id, "type": "belongs_to", "target": group_id})

        # --- learner node ---
        nodes.setdefault(learner_id, {"type": "Learner", "name": "当前学习者"})

        # --- learning traces (mastered / struggling) ---
        latest: dict[str, tuple[tuple[str, int], str, dict]] = {}
        for idx, rec in enumerate(records):
            target = _record_target(rec, tree)
            if not target:
                continue
            edge_type = _classify(rec)
            if edge_type is None:
                continue
            key = (rec.get("timestamp", ""), idx)
            if target not in latest or key >= latest[target][0]:
                latest[target] = (key, edge_type, rec)

        for idx, rec in enumerate(records):
            target = _record_target(rec, tree)
            if not target:
                continue
            edge_type = _classify(rec)
            if edge_type is None:
                continue
            if latest[target][0] != (rec.get("timestamp", ""), idx):
                continue
            edge = {
                "source": learner_id,
                "type": edge_type,
                "target": target,
                "evidence": rec.get("type", "practice"),
                "ts": rec.get("timestamp", ""),
            }
            if rec.get("f1") is not None:
                edge["f1"] = rec["f1"]
            edges.append(edge)

        return {
            "schema_version": SCHEMA_VERSION,
            "built_at": _deterministic_built_at(records),
            "source": "deterministic_graph_builder",
            "nodes": nodes,
            "edges": edges,
        }

    # ---------------------------------------------------------------- persist

    def _ensure_dir(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, graph: dict) -> Path:
        self._ensure_dir()
        from deeptutor.services.file_io import atomic_write_text

        data = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
        atomic_write_text(self._file, data)
        return self._file

    def get(self) -> dict | None:
        if not self._file.exists():
            return None
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None


# --------------------------------------------------------------- helpers

def _iter_task_groups(tree: dict):
    for group in tree.get("children", []):
        yield {"id": group["id"], "name": group["name"]}


def _iter_skills(tree: dict):
    for group in tree.get("children", []):
        for task in group.get("children", []):
            for skill in task.get("skills", []) or []:
                yield skill


def _find_skill_id_by_name(tree: dict, name: str) -> str | None:
    for skill in _iter_skills(tree):
        if skill.get("name") == name:
            return skill["id"]
    return None


def _task_group_for(tree: dict, task: dict) -> str | None:
    """Resolve a bank task to its competency-tree group via its knowledge points."""
    for kp in task.get("knowledge_points", []) or []:
        skill_id = _find_skill_id_by_name(tree, kp)
        if skill_id:
            group = _group_for_skill(tree, skill_id)
            if group is not None:
                return group
    return None


def _group_for_skill(tree: dict, skill_id: str) -> str | None:
    for group in tree.get("children", []):
        for task in group.get("children", []):
            for skill in task.get("skills", []) or []:
                if skill.get("id") == skill_id:
                    return group["id"]
    return None


def _record_target(rec: dict, tree: dict) -> str | None:
    """Trace edge target — skill ID when the knowledge point resolves to one."""
    kp = rec.get("knowledge_point")
    if kp:
        skill_id = _find_skill_id_by_name(tree, kp)
        if skill_id:
            return skill_id
        return kp
    task_id = rec.get("task_id")
    if task_id:
        return task_id
    return None


def _deterministic_built_at(records: list[dict]) -> str:
    timestamps = [rec["timestamp"] for rec in records if rec.get("timestamp")]
    return max(timestamps) if timestamps else "1970-01-01T00:00:00+00:00"


def _classify(rec: dict) -> str | None:
    """Deterministic mastered/struggling classification (aligns with facts())."""
    f1 = rec.get("f1")
    if f1 is not None:
        try:
            f1v = float(f1)
        except (TypeError, ValueError):
            f1v = None
        if f1v is not None:
            if f1v >= MASTERED_F1:
                return "mastered"
            return "struggling"
    readiness = rec.get("readiness")
    if readiness in ADVANCE_READINESS:
        return "mastered"
    if readiness:
        return "struggling"
    return None


__all__ = ["KnowledgeGraphStore", "MASTERED_F1"]
