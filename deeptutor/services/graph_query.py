"""Deterministic graph queries over the learner knowledge graph."""

from __future__ import annotations

from typing import Any

from deeptutor.services.knowledge_graph import LEARNER_ID


class GraphQueryService:
    """Read-only, deterministic queries. No LLM calls here."""

    def __init__(self, graph: dict) -> None:
        self._graph = graph or {}
        self._nodes: dict[str, dict] = self._graph.get("nodes", {})
        self._edges: list[dict] = self._graph.get("edges", [])

    # -------------------------------------------------------------- helpers

    def _out(self, node_id: str, edge_type: str | None = None) -> list[dict]:
        out = []
        for e in self._edges:
            if e["source"] != node_id:
                continue
            if edge_type and e["type"] != edge_type:
                continue
            out.append(e)
        return out

    def _in(self, node_id: str, edge_type: str | None = None) -> list[dict]:
        out = []
        for e in self._edges:
            if e["target"] != node_id:
                continue
            if edge_type and e["type"] != edge_type:
                continue
            out.append(e)
        return out

    def _name(self, node_id: str) -> str:
        return (self._nodes.get(node_id) or {}).get("name", node_id)

    # ----------------------------------------------------------------- query

    def mastery_snapshot(self) -> dict:
        mastered, struggling = [], []
        for e in self._edges:
            if e["source"] != LEARNER_ID:
                continue
            info = {"id": e["target"], "name": self._name(e["target"])}
            if e.get("f1") is not None:
                info["f1"] = e["f1"]
            if e["type"] == "mastered":
                mastered.append(info)
            elif e["type"] == "struggling":
                struggling.append(info)
        mastered.sort(key=lambda x: x["id"])
        struggling.sort(key=lambda x: x["id"])
        # next_suggested reserved for future suggestion logic (API contract)
        return {"mastered": mastered, "struggling": struggling, "next_suggested": []}

    def concepts(self, skill_id: str) -> dict:
        """Return navigation info around a skill.

        ``belongs_to`` is populated for task targets (task → group via the
        ``belongs_to`` edge); skill → group membership is not currently
        emitted, so a skill target yields an empty list here.
        """
        prereqs = [
            {"id": e["target"], "name": self._name(e["target"])}
            for e in self._out(skill_id, "prerequisite")
        ]
        dependents = [
            {"id": e["source"], "name": self._name(e["source"])}
            for e in self._in(skill_id, "prerequisite")
        ]
        tasks = [
            {"id": e["source"], "name": self._name(e["source"])}
            for e in self._in(skill_id, "requires")
        ]
        belongs = self._out(skill_id, "belongs_to")
        return {
            "skill": skill_id,
            "name": self._name(skill_id),
            "prerequisites": prereqs,
            "dependents": dependents,
            "tasks": tasks,
            "belongs_to": [self._name(e["target"]) for e in belongs],
        }

    def risk_path(self, target: str) -> dict:
        result: dict[str, Any] = {
            "target": target,
            "target_name": self._name(target),
            "missing_prereqs": [],
            "struggling": [],
            "affected_downstream": [],
            "confidence": "low",
        }
        if target not in self._nodes:
            return result

        snap = self.mastery_snapshot()
        struggling_by_id = {x["id"]: x for x in snap["struggling"]}
        struggling_ids = set(struggling_by_id)
        mastered_ids = {x["id"] for x in snap["mastered"]}
        target_skills = self._target_skills(target)

        # walk the full prerequisite closure from the target's skills
        visited: set[str] = set()
        stack = list(target_skills)
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            if cur not in mastered_ids and cur not in struggling_ids and cur != target:
                result["missing_prereqs"].append({"id": cur, "name": self._name(cur)})
            for e in self._out(cur, "prerequisite"):
                stack.append(e["target"])

        involved = set(target_skills) | visited
        result["struggling"] = []
        for s in struggling_ids:
            if s not in involved:
                continue
            entry = {"id": s, "name": self._name(s)}
            f1 = struggling_by_id[s].get("f1")
            if f1 is not None:
                entry["f1"] = f1
            result["struggling"].append(entry)
        result["missing_prereqs"].sort(key=lambda x: x["id"])
        result["struggling"].sort(key=lambda x: x["id"])

        affected: list[dict] = []
        for e in self._in(target, "prerequisite"):
            affected.append(
                {"id": e["source"], "name": self._name(e["source"]), "via": "prerequisite",
                 "reason": f"依赖'{self._name(target)}'"}
            )
        for e in self._in(target, "requires"):
            affected.append(
                {"id": e["source"], "name": self._name(e["source"]), "via": "requires",
                 "reason": f"依赖'{self._name(target)}'"}
            )
        result["affected_downstream"] = affected
        result["affected_downstream"].sort(key=lambda x: x["id"])
        result["confidence"] = "high" if (result["missing_prereqs"] or result["struggling"]) else "low"
        return result

    def _target_skills(self, node_id: str) -> set[str]:
        node = self._nodes.get(node_id) or {}
        if node.get("type") == "Skill":
            return {node_id}
        # Task → required skills
        return {e["target"] for e in self._out(node_id, "requires")}


__all__ = ["GraphQueryService"]
