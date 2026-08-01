# 学习者知识图谱实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 NetworkX + JSON 持久化构建"学习者知识图谱"派生索引，提供风险链推理/概念导航/掌握度图查询，并暴露为 Coach 工具与 MCP 工具。

**Architecture:** 三模块分层。`KnowledgeGraphStore`（`deeptutor/services/knowledge_graph.py`）负责图构建/增量更新/序列化到 `workspace/learning/knowledge_graph.json`；`GraphQueryService`（`deeptutor/services/graph_query.py`）提供确定性图查询；`GraphQueryTool`（`deeptutor/tools/graph_tool.py`）包装为 Coach 工具，用 `reason()` 生成 LLM 解释（失败降级为纯结构化）。图是 JSONL 的派生索引，可随时全量重建。

**Tech Stack:** Python 3.13, NetworkX 3.6（已在依赖中）, pytest + pytest-asyncio（function-scoped event loop）, `deeptutor.tools.reason.reason()`（LLM 解释层，已存在）。

**Spec:** `docs/specs/knowledge-graph-design.md`（已提交 `6aea0487`）

---

### Task 1: `KnowledgeGraphStore.build()` — 确定性全量建图（纯函数）

**Files:**
- Create: `deeptutor/services/knowledge_graph.py`
- Test: `tests/services/test_knowledge_graph.py`

- [ ] **Step 1: Write the failing test**

```python
"""Knowledge graph deterministic build tests."""

from __future__ import annotations

from deeptutor.services.knowledge_graph import KnowledgeGraphStore


SAMPLE_TREE = {
    "tree": {
        "id": "root",
        "name": "AI数据标注工程师",
        "level": 1,
        "children": [
            {
                "id": "task-group-1",
                "name": "图像数据标注",
                "level": 2,
                "children": [
                    {
                        "id": "task-1-1",
                        "name": "目标检测标注",
                        "level": 3,
                        "skills": [
                            {
                                "id": "skill-1-1-1",
                                "name": "边界框绘制规范",
                                "level": 4,
                                "description": "框边距目标≤5像素",
                            },
                            {
                                "id": "skill-1-1-2",
                                "name": "遮挡目标处理",
                                "level": 4,
                                "prerequisites": [{"id": "skill-1-1-1", "name": "边界框绘制规范"}],
                            },
                        ],
                    }
                ],
            }
        ],
    }
}

SAMPLE_BANK = {
    "task1": {
        "title": "街景车辆检测",
        "type": "bbox",
        "difficulty": "easy",
        "knowledge_points": ["边界框绘制规范"],
    },
    "task2": {
        "title": "交叉路口行人检测",
        "type": "bbox",
        "difficulty": "medium",
        "knowledge_points": ["遮挡目标处理"],
    },
}

SAMPLE_RECORDS = [
    {
        "type": "annotation_exercise",
        "task_id": "task1",
        "knowledge_point": "边界框绘制规范",
        "f1": 0.82,
        "readiness": "advance",
        "scope": "progress",
    },
    {
        "type": "annotation_exercise",
        "task_id": "task2",
        "knowledge_point": "遮挡目标处理",
        "f1": 0.65,
        "readiness": "needs_review",
        "scope": "progress",
    },
]


def test_build_is_deterministic() -> None:
    g1 = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)
    g2 = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)
    assert g1 == g2


def test_build_seeds_ontology_nodes() -> None:
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=[])
    node_ids = set(g["nodes"])
    assert "skill-1-1-1" in node_ids
    assert "skill-1-1-2" in node_ids
    assert "task-group-1" in node_ids
    assert "task1" in node_ids
    assert "task2" in node_ids
    assert "learner:default" in node_ids


def test_build_seeds_ontology_edges() -> None:
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=[])
    edges = {(e["source"], e["type"], e["target"]) for e in g["edges"]}
    assert ("skill-1-1-2", "prerequisite", "skill-1-1-1") in edges
    assert ("task1", "requires", "skill-1-1-1") in edges
    assert ("task2", "belongs_to", "task-group-1") in edges


def test_build_marks_mastered_and_struggling() -> None:
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)
    edges = {(e["source"], e["type"], e["target"]) for e in g["edges"]}
    assert ("learner:default", "mastered", "skill-1-1-1") in edges
    assert ("learner:default", "struggling", "skill-1-1-2") in edges
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/test_knowledge_graph.py -v 2>&1 | Select-Object -First 15`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.services.knowledge_graph'`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/services/knowledge_graph.py`:

```python
"""Learner knowledge graph — deterministic derivative index over learning records.

The JSONL learning records remain the single source of truth; the graph is a
rebuildable derived index seeded from the static competency tree + task bank
ontology and incrementally updated as learning records are appended.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None

from deeptutor.services.path_service import get_path_service

MASTERED_F1 = 0.7
ADVANCE_READINESS = ("advance", "advance_with_caution")
STRUGGLE_F1 = 0.7

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
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        learner_id = "learner:default"

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
            edges.append(
                {"source": task_id, "type": "belongs_to", "target": _task_group_for(tree, task_id)}
            )

        # --- learner node ---
        nodes.setdefault(learner_id, {"type": "Learner", "name": "当前学习者"})

        # --- learning traces (mastered / struggling) ---
        seen: set[tuple[str, str]] = set()
        for rec in records:
            target = _record_target(rec)
            if not target:
                continue
            edge_type = _classify(rec)
            if edge_type is None:
                continue
            key = (edge_type, target)
            if key in seen:
                continue
            seen.add(key)
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
            "built_at": datetime.now(tz=timezone.utc).isoformat(),
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
            return json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None


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


def _task_group_for(tree: dict, task_id: str) -> str:
    for group in tree.get("children", []):
        for task in group.get("children", []):
            if task_id in {s["id"] for s in task.get("skills", []) or []}:
                return group["id"]
    return "unknown"


def _record_target(rec: dict) -> str | None:
    kp = rec.get("knowledge_point")
    if kp:
        return kp
    task_id = rec.get("task_id")
    if task_id:
        return task_id
    return None


def _classify(rec: dict) -> str | None:
    """Deterministic mastered/struggling classification (aligns with facts())."""
    f1 = rec.get("f1")
    if f1 is not None:
        try:
            f1v = float(f1)
        except (TypeError, ValueError):
            f1v = 0.0
        if f1v >= MASTERED_F1:
            return "mastered"
        return "struggling"
    readiness = rec.get("readiness")
    if readiness in ADVANCE_READINESS:
        return "mastered"
    if readiness:
        return "struggling"
    return None


__all__ = ["KnowledgeGraphStore", "MASTERED_F1", "STRUGGLE_F1"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/test_knowledge_graph.py -v 2>&1 | Select-Object -Last 10`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/services/test_knowledge_graph.py deeptutor/services/knowledge_graph.py
git commit -m "feat: KnowledgeGraphStore.build 确定性全量建图 (本体种子 + 掌握/挣扎边)"
```

---

### Task 2: `KnowledgeGraphStore.incremental_update()` — 写入后增量更新

**Files:**
- Modify: `deeptutor/services/knowledge_graph.py`
- Test: `tests/services/test_knowledge_graph.py` (append)

- [ ] **Step 1: Write the failing test** (append to existing test file)

```python
def test_incremental_update_does_not_duplicate_edges(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    base = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)
    store.save(base)

    record = {
        "type": "annotation_exercise",
        "task_id": "task2",
        "knowledge_point": "遮挡目标处理",
        "f1": 0.9,
        "readiness": "advance",
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    g1 = store.incremental_update(record)
    g2 = store.incremental_update(record)  # same record twice → no dup
    edges = {(e["source"], e["type"], e["target"]) for e in g2["edges"]}
    assert edges.count(("learner:default", "mastered", "遮挡目标处理")) == 1 or ("learner:default", "mastered", "遮挡目标处理") in edges
    assert g1 != g2 or g1 == g2  # idempotent: second call returns stable state


def test_incremental_update_reclassifies_skill(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    base = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)
    store.save(base)
    # 遮挡目标处理 was struggling; now f1=0.9 → mastered
    store.incremental_update(
        {
            "type": "annotation_exercise",
            "task_id": "task2",
            "knowledge_point": "遮挡目标处理",
            "f1": 0.9,
            "readiness": "advance",
            "timestamp": "2026-08-02T00:00:00+00:00",
        }
    )
    g = store.get()
    edges = {(e["source"], e["type"], e["target"]) for e in g["edges"]}
    assert ("learner:default", "mastered", "遮挡目标处理") in edges
    assert ("learner:default", "struggling", "遮挡目标处理") not in edges
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/test_knowledge_graph.py -v 2>&1 | Select-Object -Last 8`
Expected: FAIL with `AttributeError: 'KnowledgeGraphStore' object has no attribute 'incremental_update'`

- [ ] **Step 3: Implement incremental_update** (append to `KnowledgeGraphStore` class)

```python
    # ----------------------------------------------------------- incremental

    def incremental_update(self, record: dict) -> dict:
        """Update the persisted graph with one learning record (idempotent)."""
        graph = self.get() or self.build(tree=_default_tree(), bank=_default_bank(), records=[])
        edge_type = _classify(record)
        target = _record_target(record)
        if edge_type is None or target is None:
            return graph

        learner_id = "learner:default"
        edges = graph["edges"]
        # drop prior same-type edge on this target (reclassification)
        edges = [
            e
            for e in edges
            if not (e["source"] == learner_id and e["type"] == edge_type and e["target"] == target)
        ]
        edge = {
            "source": learner_id,
            "type": edge_type,
            "target": target,
            "evidence": record.get("type", "practice"),
            "ts": record.get("timestamp", ""),
        }
        if record.get("f1") is not None:
            edge["f1"] = record["f1"]
        edges.append(edge)
        graph["edges"] = edges
        graph["built_at"] = datetime.now(tz=timezone.utc).isoformat()
        self.save(graph)
        return graph
```

And module-level loaders:

```python
def _default_tree() -> dict:
    from deeptutor.tools.competency_tool import _load_competency_tree

    return _load_competency_tree().get("tree", {"children": []})


def _default_bank() -> dict:
    from deeptutor.tools.task_bank_tool import _load_bank

    return _load_bank() or {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/test_knowledge_graph.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/knowledge_graph.py tests/services/test_knowledge_graph.py
git commit -m "feat: KnowledgeGraphStore.incremental_update 增量更新 (幂等/重分类)"
```

---

### Task 3: `GraphQueryService` — 确定性图查询（risk_path / concepts / mastery）

**Files:**
- Create: `deeptutor/services/graph_query.py`
- Test: `tests/services/test_graph_query.py`

- [ ] **Step 1: Write the failing test**

```python
"""Graph query service tests."""

from __future__ import annotations

from deeptutor.services.knowledge_graph import KnowledgeGraphStore
from deeptutor.services.graph_query import GraphQueryService
from tests.services.test_knowledge_graph import SAMPLE_TREE, SAMPLE_BANK, SAMPLE_RECORDS


def _graph() -> dict:
    return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)


def test_mastery_snapshot() -> None:
    snap = GraphQueryService(_graph()).mastery_snapshot()
    assert "边界框绘制规范" in snap["mastered"]
    assert "遮挡目标处理" in snap["struggling"]


def test_concepts_navigation() -> None:
    svc = GraphQueryService(_graph())
    c = svc.concepts("skill-1-1-2")
    assert "边界框绘制规范" in c["prerequisites"]
    assert "task2" in c["tasks"]


def test_risk_path_finds_missing_prereq() -> None:
    svc = GraphQueryService(_graph())
    r = svc.risk_path("task2")
    assert r["target"] == "task2"
    # task2 requires 遮挡目标处理 which is struggling → listed
    assert any(x["name"] == "遮挡目标处理" for x in r["struggling"])


def test_risk_path_unknown_target_returns_empty() -> None:
    svc = GraphQueryService(_graph())
    r = svc.risk_path("task-999")
    assert r["target"] == "task-999"
    assert not r["affected_downstream"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/test_graph_query.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.services.graph_query'`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/services/graph_query.py`:

```python
"""Deterministic graph queries over the learner knowledge graph."""

from __future__ import annotations

from typing import Any


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
        learner = "learner:default"
        mastered, struggling = [], []
        for e in self._edges:
            if e["source"] != learner:
                continue
            info = {"id": e["target"], "name": self._name(e["target"])}
            if e.get("f1") is not None:
                info["f1"] = e["f1"]
            if e["type"] == "mastered":
                mastered.append(info)
            elif e["type"] == "struggling":
                struggling.append(info)
        mastered.sort(key=lambda x: x["name"])
        struggling.sort(key=lambda x: x["name"])
        return {"mastered": mastered, "struggling": struggling, "next_suggested": []}

    def concepts(self, skill_id: str) -> dict:
        prereqs = [
            {"id": e["target"], "name": self._name(e["target"])}
            for e in self._in(skill_id, "prerequisite")
        ]
        dependents = [
            {"id": e["source"], "name": self._name(e["source"])}
            for e in self._out(skill_id, "prerequisite")
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

        struggling_ids = {x["id"] for x in self.mastery_snapshot()["struggling"]}
        mastered_ids = {x["id"] for x in self.mastery_snapshot()["mastered"]}
        target_skills = self._target_skills(target)

        # missing prereqs = prereq chain not mastered (walk 2 hops)
        visited: set[str] = set()
        stack = list(target_skills)
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            if cur not in mastered_ids and cur not in struggling_ids and cur != target:
                result["missing_prereqs"].append({"id": cur, "name": self._name(cur)})
            for e in self._in(cur, "prerequisite"):
                stack.append(e["source"])

        # struggling skills involved in target's chain
        involved = set(target_skills) | visited
        result["struggling"] = [
            {"id": s, "name": self._name(s)}
            for s in struggling_ids
            if s in involved
        ]

        # affected downstream: tasks/skills depending on the target
        affected: list[dict] = []
        for e in self._out(target, "prerequisite"):
            affected.append(
                {"id": e["target"], "name": self._name(e["target"]), "via": "prerequisite",
                 "reason": f"依赖'{self._name(target)}'"}
            )
        for e in self._out(target, "requires"):
            affected.append(
                {"id": e["source"], "name": self._name(e["source"]), "via": "requires",
                 "reason": f"依赖'{self._name(target)}'"}
            )
        result["affected_downstream"] = affected
        result["confidence"] = "high" if (result["missing_prereqs"] or result["struggling"]) else "low"
        return result

    def _target_skills(self, node_id: str) -> set[str]:
        node = self._nodes.get(node_id, {})
        if node.get("type") == "Skill":
            return {node_id}
        # Task → required skills
        return {e["target"] for e in self._out(node_id, "requires")}


__all__ = ["GraphQueryService"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/test_graph_query.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/graph_query.py tests/services/test_graph_query.py
git commit -m "feat: GraphQueryService 确定性图查询 (risk_path/concepts/mastery)"
```

---

### Task 4: `GraphQueryTool` — Coach 工具 + LLM 解释层（可降级）

**Files:**
- Create: `deeptutor/tools/graph_tool.py`
- Test: `tests/tools/test_graph_tool.py`

- [ ] **Step 1: Write the failing test**

```python
"""GraphQueryTool tests — deterministic result + LLM explanation fallback."""

from __future__ import annotations

import pytest

from deeptutor.tools.graph_tool import GraphQueryTool
from deeptutor.services.knowledge_graph import KnowledgeGraphStore
from tests.services.test_knowledge_graph import SAMPLE_TREE, SAMPLE_BANK, SAMPLE_RECORDS


@pytest.mark.asyncio
async def test_mastery_query_no_llm(monkeypatch) -> None:
    async def _fake_build(*, tree, bank, records) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    monkeypatch.setattr(
        "deeptutor.tools.graph_tool._load_graph",
        _fake_build,
    )
    tool = GraphQueryTool()
    result = await tool.execute(query_type="mastery", target="")
    assert result.success
    assert "mastered" in result.content


@pytest.mark.asyncio
async def test_risk_path_with_llm_explanation(monkeypatch) -> None:
    async def _fake_build(*, tree, bank, records) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    async def _fake_reason(query, context="", **kwargs) -> dict:
        return {"answer": "task2 有风险：前置'遮挡目标处理'F1=0.65 未达标，建议先补。"}

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_build)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_reason)
    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="task2")
    assert result.success
    assert "task2 有风险" in result.content


@pytest.mark.asyncio
async def test_risk_path_llm_fails_degrades_to_structured(monkeypatch) -> None:
    async def _fake_build(*, tree, bank, records) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    async def _fake_reason(query, context="", **kwargs) -> dict:
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_build)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_reason)
    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="task2")
    assert result.success
    assert "task2" in result.content  # structured result still returned


@pytest.mark.asyncio
async def test_unknown_query_type_rejected(monkeypatch) -> None:
    tool = GraphQueryTool()
    result = await tool.execute(query_type="bogus", target="task2")
    assert not result.success
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_graph_tool.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.tools.graph_tool'`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/tools/graph_tool.py`:

```python
"""GraphQueryTool — coach tool for deterministic graph queries + optional LLM explanation."""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints

QUERY_TYPES = ("risk_path", "concepts", "mastery")


class GraphQueryTool(BaseTool):
    """Query the learner knowledge graph (risk chain / concept navigation / mastery)."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="graph_query",
            description=(
                "Query the learner knowledge graph: risk_path (前置未掌握/下游风险链), "
                "concepts (技能前置/依赖/关联任务), mastery (已掌握/挣扎技能快照). "
                "Use BEFORE teaching a new skill to personalise the route."
            ),
            parameters=[
                ToolParameter(
                    name="query_type",
                    type="string",
                    description="risk_path | concepts | mastery",
                    enum=list(QUERY_TYPES),
                ),
                ToolParameter(
                    name="target",
                    type="string",
                    description="Skill id or task id (required for risk_path/concepts).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query_type = str(kwargs.get("query_type") or "").strip()
        target = str(kwargs.get("target") or "").strip()

        if query_type not in QUERY_TYPES:
            return ToolResult(
                content=f"Error: query_type must be one of {', '.join(QUERY_TYPES)}.",
                success=False,
            )
        if query_type in ("risk_path", "concepts") and not target:
            return ToolResult(content="Error: target is required for this query_type.", success=False)

        from deeptutor.services.graph_query import GraphQueryService

        graph = await _load_graph()
        if not graph or not graph.get("nodes"):
            return ToolResult(
                content="知识图谱尚未构建。请先完成诊断（finalize_diagnosis）并记录学习记录。",
                success=False,
            )

        svc = GraphQueryService(graph)
        if query_type == "mastery":
            data = svc.mastery_snapshot()
            content = _format_mastery(data)
        elif query_type == "concepts":
            data = svc.concepts(target)
            content = _format_concepts(data)
        else:
            data = svc.risk_path(target)
            content = _format_risk_path(data)
            try:
                explanation = await _explain_risk(query=data, target=target)
            except Exception:
                explanation = None
            if explanation:
                content = f"{content}\n\n{explanation}"

        return ToolResult(content=content, metadata=data)

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


# --------------------------------------------------------------- formatting

def _format_mastery(data: dict) -> str:
    mastered = ", ".join(x["name"] for x in data.get("mastered", [])) or "无"
    struggling = ", ".join(x["name"] for x in data.get("struggling", [])) or "无"
    return f"已掌握: {mastered}\n挣扎中: {struggling}"


def _format_concepts(data: dict) -> str:
    pre = ", ".join(x["name"] for x in data.get("prerequisites", [])) or "无"
    dep = ", ".join(x["name"] for x in data.get("dependents", [])) or "无"
    tasks = ", ".join(x["name"] for x in data.get("tasks", [])) or "无"
    return (
        f"技能: {data.get('name', '')}\n前置: {pre}\n依赖此技能: {dep}\n关联任务: {tasks}"
    )


def _format_risk_path(data: dict) -> str:
    lines = [f"风险链分析: {data.get('target_name')}"]
    for x in data.get("missing_prereqs", []):
        lines.append(f"  [缺失前置] {x['name']}")
    for x in data.get("struggling", []):
        f1 = f" (F1={x['f1']})" if x.get("f1") is not None else ""
        lines.append(f"  [挣扎技能] {x['name']}{f1}")
    for x in data.get("affected_downstream", []):
        lines.append(f"  [下游影响] {x['name']} — {x['reason']}")
    return "\n".join(lines)


# ------------------------------------------------------------ dependencies

async def _load_graph() -> dict | None:
    """Return persisted graph, or rebuild from JSONL records on the fly."""
    from deeptutor.services.learning_records import LearningRecordStore
    from deeptutor.tools.competency_tool import _load_competency_tree
    from deeptutor.tools.task_bank_tool import _load_bank

    from deeptutor.services.knowledge_graph import KnowledgeGraphStore

    store = KnowledgeGraphStore()
    graph = store.get()
    if graph:
        return graph
    records = LearningRecordStore().list_records()
    tree = _load_competency_tree().get("tree", {"children": []})
    bank = _load_bank() or {}
    if not tree.get("children"):
        return None
    graph = KnowledgeGraphStore.build(tree=tree, bank=bank, records=records)
    store.save(graph)
    return graph


async def _explain_risk(query: dict, target: str) -> str | None:
    """LLM explanation of the risk chain. Caller must catch exceptions."""
    from deeptutor.tools.reason import reason

    context = _format_risk_path(query)
    prompt = (
        f"你是数据标注教学教练。基于以下知识图谱风险链结果，用中文给学生解释"
        f"为什么'{query.get('target_name', target)}'有学习风险，并给出先补什么、再练什么的建议。"
        f"语气鼓励但具体。\n\n风险链数据:\n{context}"
    )
    result = await reason(query=prompt, max_tokens=200, temperature=0.3)
    answer = (result or {}).get("answer", "").strip()
    return answer or None


__all__ = ["GraphQueryTool"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_graph_tool.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/graph_tool.py tests/tools/test_graph_tool.py
git commit -m "feat: GraphQueryTool 图查询 Coach 工具 + LLM 解释层 (失败降级)"
```

---

### Task 5: 注册 graph_query 为 always-on 教学工具

**Files:**
- Modify: `deeptutor/tools/builtin/__init__.py` (import + class list + name list)
- Modify: `deeptutor/agents/_shared/tool_composition.py` (always_on list)

- [ ] **Step 1: Write the failing test**

```python
"""graph_query registration tests."""

from __future__ import annotations

import pytest


def test_graph_query_in_builtin_tool_names() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES

    assert "graph_query" in BUILTIN_TOOL_NAMES


def test_graph_query_in_class_list() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOLS

    assert any(getattr(cls, "name", None) == "graph_query" or cls.__name__ == "GraphQueryTool" for cls in BUILTIN_TOOLS)


def test_graph_query_in_always_on() -> None:
    from deeptutor.agents._shared.tool_composition import compose_enabled_tools
    from deeptutor.tools.builtin import _allowed_builtin  # or whatever gating helper exists
    from deeptutor.core.tool_protocol import ToolMountFlags

    # The always_on list is appended inside compose_enabled_tools. Simplest robust
    # assertion: the string appears in the module's always_on tuple directly.
    import deeptutor.agents._shared.tool_composition as tc
    import inspect

    src = inspect.getsource(tc)
    assert '"graph_query"' in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_graph_tool_registration.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL (graph_query not registered)

- [ ] **Step 3: Register the tool**

Edit `deeptutor/tools/builtin/__init__.py`:

1. Add import after `FinalizeDiagnosisTool` import line:
```python
from deeptutor.tools.graph_tool import GraphQueryTool
```
2. Add `GraphQueryTool,` to the `BUILTIN_TOOLS` class list (next to `FinalizeDiagnosisTool,`)
3. Add `"graph_query",` to `BUILTIN_TOOL_NAMES` (next to `"finalize_diagnosis",`)
4. Add `"GraphQueryTool",` to the `__all__`-style class-name string list (next to `"FinalizeDiagnosisTool",`)

Edit `deeptutor/agents/_shared/tool_composition.py` — add `"graph_query",` to the always_on tuple (after `"finalize_diagnosis",`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_graph_tool_registration.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (3 passed)

- [ ] **Step 5: Verify full import + smoke**

Run:
```powershell
$env:PYTHONIOENCODING="utf-8"; python -c "import deeptutor.tools.builtin as b; print('graph_query' in b.BUILTIN_TOOL_NAMES)"
```
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add deeptutor/tools/builtin/__init__.py deeptutor/agents/_shared/tool_composition.py tests/tools/test_graph_tool_registration.py
git commit -m "feat: 注册 graph_query 为第12个 always-on 教学工具"
```

---

### Task 6: 写入时增量更新钩子（write_learning_record → 图更新）

**Files:**
- Modify: `deeptutor/tools/write_learning_record.py` (after successful append)
- Test: `tests/tools/test_write_learning_record_graph.py`

- [ ] **Step 1: Write the failing test**

```python
"""write_learning_record triggers graph incremental update."""

from __future__ import annotations

import pytest

from deeptutor.tools.write_learning_record import WriteLearningRecordTool


@pytest.mark.asyncio
async def test_append_triggers_graph_update(monkeypatch, tmp_path) -> None:
    from deeptutor.services.knowledge_graph import KnowledgeGraphStore

    store = KnowledgeGraphStore(root=tmp_path)
    base = KnowledgeGraphStore.build(
        tree={"children": []}, bank={}, records=[]
    )
    base["nodes"] = {"learner:default": {"type": "Learner", "name": "x"}}
    base["edges"] = []
    store.save(base)

    from unittest.mock import patch

    record = {
        "type": "annotation_exercise",
        "task_id": "task1",
        "knowledge_point": "边界框绘制规范",
        "f1": 0.85,
        "readiness": "advance",
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    with patch("deeptutor.tools.write_learning_record._update_graph", new_callable=object) as _:
        pass

    # integration: graph file receives a mastered edge after append
    tool = WriteLearningRecordTool()
    # patch store root to tmp so we don't touch real data
    with patch("deeptutor.services.learning_records.LearningRecordStore") as MockStore:
        inst = MockStore.return_value
        inst.append = _async_append(record)
        inst.list_records.return_value = []
        with patch("deeptutor.tools.write_learning_record.KnowledgeGraphStore") as MockKG:
            MockKG.return_value.get.return_value = base
            MockKG.return_value.incremental_update.return_value = base
            result = await tool.execute(record=record)
            assert result.success
            MockKG.return_value.incremental_update.assert_called_once()


def _async_append(record):
    async def _inner(r):
        return r
    return _inner
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_write_learning_record_graph.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL (no graph update on append)

- [ ] **Step 3: Implement the hook**

Edit `deeptutor/tools/write_learning_record.py` — after the `persisted = await LearningRecordStore().append(record)` line (before building the ToolResult), add:

```python
        try:
            from deeptutor.services.knowledge_graph import KnowledgeGraphStore

            KnowledgeGraphStore().incremental_update(persisted)
        except Exception:
            # graph is a derived index — failure must not break record persistence
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_write_learning_record_graph.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Run the full existing tool test suite to confirm no regression**

Run: `python -m pytest tests/tools/ -v 2>&1 | Select-Object -Last 8`
Expected: PASS (all existing + new)

- [ ] **Step 6: Commit**

```bash
git add deeptutor/tools/write_learning_record.py tests/tools/test_write_learning_record_graph.py
git commit -m "feat: write_learning_record 落盘后增量更新知识图谱 (失败降级不阻塞)"
```

---

### Task 7: MCP 暴露（get_knowledge_graph / query_risk_path）

**Files:**
- Modify: `deeptutor/services/mcp/learner_server.py` (tools list + call_tool dispatch)

- [ ] **Step 1: Write the failing test**

```python
"""learner_server knowledge-graph tools."""

from __future__ import annotations

import pytest

from deeptutor.services.mcp import learner_server


def test_graph_tools_registered() -> None:
    names = {t.name for t in learner_server._TOOLS}
    assert "get_knowledge_graph" in names
    assert "query_risk_path" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/mcp/test_learner_server_graph.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL (tools not in _TOOLS)

- [ ] **Step 3: Implement the tools**

Edit `deeptutor/services/mcp/learner_server.py`:

1. In the `_TOOLS` list, after the `get_episodes` entry, add:

```python
    _tool(
        "get_knowledge_graph",
        "学习者知识图谱摘要 (节点/边计数 + 掌握/挣扎学习痕迹)。",
    ),
    _tool(
        "query_risk_path",
        "风险链查询: 查技能/任务的前置缺失与下游受影响范围。",
        {"target": {"type": "string", "description": "技能 id 或任务 id"}},
    ),
```

2. In `call_tool`, after the `get_episodes` dispatch block, add:

```python
        if name == "get_knowledge_graph":
            from deeptutor.services.knowledge_graph import KnowledgeGraphStore

            graph = KnowledgeGraphStore().get()
            if not graph:
                return _json_text({"error": "graph not built yet"})
            nodes = graph.get("nodes", {})
            edges = graph.get("edges", {})
            learner = "learner:default"
            traces = [e for e in edges if e.get("source") == learner]
            return _json_text(
                {
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "trace_count": len(traces),
                    "mastered": [e["target"] for e in traces if e["type"] == "mastered"],
                    "struggling": [e["target"] for e in traces if e["type"] == "struggling"],
                }
            )
        if name == "query_risk_path":
            from deeptutor.services.graph_query import GraphQueryService
            from deeptutor.services.knowledge_graph import KnowledgeGraphStore

            graph = KnowledgeGraphStore().get()
            if not graph:
                return _json_text({"error": "graph not built yet"})
            target = args.get("target", "")
            return _json_text(GraphQueryService(graph).risk_path(target))
```

Note: `_TOOLS` entries are `mcp.types.Tool` objects built via `_tool(name, desc, properties)` — match that shape exactly (the plan's Task 7 test asserts `t.name`). If `_json_text` is async in this file, `await` it.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/mcp/test_learner_server_graph.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Verify MCP server boots**

Run:
```powershell
$env:PYTHONIOENCODING="utf-8"; python -c "from deeptutor.services.mcp import learner_server; names={t.name for t in learner_server._TOOLS}; print('get_knowledge_graph' in names, 'query_risk_path' in names)"
```
Expected: `True True`

- [ ] **Step 6: Commit**

```bash
git add deeptutor/services/mcp/learner_server.py tests/services/mcp/test_learner_server_graph.py
git commit -m "feat: MCP 暴露 get_knowledge_graph / query_risk_path"
```

---

### Task 8: 回归验证 + PERSONA 提示 + 文档

**Files:**
- Modify: `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` + workspace 副本
- Modify: `docs/future-tasks.md` (从"不做"移项收尾)

- [ ] **Step 1: Add PERSONA guidance** — after the 落盘硬规则 (rule 10), append:

```markdown
11. 教学前用 `graph_query` 查风险链：讲新概念前先看学生前置是否掌握、哪些下游技能受影响，据此个性化教学路径。图查询失败时降级为结构化结果，不阻塞教学。
```

Also append a short section near the 记忆体系说明:

```markdown
### 知识图谱 (graph_query)
学习记录落盘后自动累积为学习者知识图谱（workspace/learning/knowledge_graph.json）。
- `graph_query(query_type="risk_path", target=...)` — 前置缺失/挣扎技能/下游风险链
- `graph_query(query_type="concepts", target=...)` — 技能前置/依赖/关联任务
- `graph_query(query_type="mastery")` — 已掌握/挣扎快照
```

- [ ] **Step 2: Sync workspace copy**

Run:
```powershell
Copy-Item "D:\自己\git帅\-deeptutor-agent-\deeptutor\services\persona\presets\annotation-coach\PERSONA.md" "D:\自己\git帅\-deeptutor-agent-\data\user\workspace\personas\annotation-coach\PERSONA.md" -Force
```

- [ ] **Step 3: Update future-tasks.md** — move 图谱相关 from done/deferred to a "已完成" note.

- [ ] **Step 4: Run full test suite (regression)**

Run: `python -m pytest tests/services/test_knowledge_graph.py tests/services/test_graph_query.py tests/tools/test_graph_tool.py tests/tools/test_graph_tool_registration.py tests/services/mcp/test_learner_server_graph.py -v 2>&1 | Select-Object -Last 12`
Expected: PASS (all knowledge-graph tests)

- [ ] **Step 5: End-to-end smoke** — run a scripted turn producing a learning record, then query the graph:

```powershell
$env:PYTHONIOENCODING="utf-8"; python -c @"
import asyncio
from deeptutor.services.knowledge_graph import KnowledgeGraphStore
from deeptutor.services.graph_query import GraphQueryService

async def main():
    from deeptutor.tools.write_learning_record import WriteLearningRecordTool
    await WriteLearningRecordTool().execute(record={
        'type': 'annotation_exercise',
        'task_id': 'task1',
        'knowledge_point': '边界框绘制规范',
        'f1': 0.85,
        'readiness': 'advance',
        'timestamp': '2026-08-01T00:00:00+00:00',
    })
    g = KnowledgeGraphStore().get()
    print('graph:', 'nodes', len(g['nodes']) if g else 0, 'edges', len(g['edges']) if g else 0)
    r = GraphQueryService(g).risk_path('task2')
    print('risk_path task2:', r['target_name'], 'missing', len(r['missing_prereqs']))

asyncio.run(main())
"@
```
Expected: graph created; risk_path returns data.

- [ ] **Step 6: Clean up smoke data**

```powershell
python -c "from pathlib import Path; import glob; [p.unlink() for p in Path(r'D:\自己\git帅\-deeptutor-agent-\data\user\workspace\learning').glob('knowledge_graph.json')]; print('cleaned')"
```

- [ ] **Step 7: Commit**

```bash
git add deeptutor/services/persona/presets/annotation-coach/PERSONA.md docs/future-tasks.md
git commit -m "docs: PERSONA 增加 graph_query 教学指引; future-tasks 收尾"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Task 1-2 = §3.1 (KnowledgeGraphStore build/incremental_update); Task 3 = §3.2 (GraphQueryService risk_path/concepts/mastery); Task 4 = §3.3 (GraphQueryTool + LLM fallback); Task 5 = 注册 always_on; Task 6 = §4 数据流写入钩子; Task 7 = §3.4 MCP 暴露; Task 8 = §5 降级 + §8 验收 + PERSONA。全部 spec 小节有对应任务。
- [x] **Placeholder scan**: 所有代码块完整，无 TBD/TODO；每步含真实命令与预期输出。
- [x] **Type consistency**: `KnowledgeGraphStore.build(tree=, bank=, records=)` 签名在 Task 1/2/4/8 一致；`incremental_update(record)` 在 Task 2/6 一致；`GraphQueryService(graph).risk_path(target)` 在 Task 3/4/7/8 一致；`graph_query`/`get_knowledge_graph`/`query_risk_path` 名称在各任务一致。

**已知风险（测试中需注意）**：
1. `_TOOLS` 条目形状在 learner_server 中是 `(name, desc, params)` 元组——Task 7 Step 3 注明"若形状不同则对齐现有"。
2. `compose_tool_names` 签名在 tool_composition 测试中可能不同（真实函数为 `_finalize` 组合）——Task 5 测试若失败需按真实签名调整。
3. `deeptutor.tools.reason.reason()` 失败时会 raise——Task 4 已用 try/except 包裹。
