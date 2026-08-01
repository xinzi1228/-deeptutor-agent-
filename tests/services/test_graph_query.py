"""Graph query service tests."""

from __future__ import annotations

from deeptutor.services.graph_query import GraphQueryService
from deeptutor.services.knowledge_graph import KnowledgeGraphStore
from tests.services.test_knowledge_graph import SAMPLE_BANK, SAMPLE_RECORDS, SAMPLE_TREE


def _graph() -> dict:
    return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)


def test_mastery_snapshot() -> None:
    snap = GraphQueryService(_graph()).mastery_snapshot()
    mastered_ids = {x["id"] for x in snap["mastered"]}
    struggling_ids = {x["id"] for x in snap["struggling"]}
    assert "skill-1-1-1" in mastered_ids
    assert "skill-1-1-2" in struggling_ids


def test_concepts_navigation() -> None:
    svc = GraphQueryService(_graph())
    c = svc.concepts("skill-1-1-2")
    assert any(x["id"] == "skill-1-1-1" for x in c["prerequisites"])
    assert any(x["id"] == "task2" for x in c["tasks"])


def test_risk_path_finds_struggling_skill() -> None:
    svc = GraphQueryService(_graph())
    r = svc.risk_path("task2")
    assert r["target"] == "task2"
    # task2 requires 遮挡目标处理 (skill-1-1-2) which is struggling → listed
    assert any(x["id"] == "skill-1-1-2" for x in r["struggling"])


def test_risk_path_unknown_target_returns_empty() -> None:
    svc = GraphQueryService(_graph())
    r = svc.risk_path("task-999")
    assert r["target"] == "task-999"
    assert not r["affected_downstream"]


def test_risk_path_finds_missing_prereq() -> None:
    # build a graph where 遮挡目标处理 has no learning trace but requires 边界框绘制规范
    records = []  # no learning records → nothing mastered
    svc = GraphQueryService(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records))
    r = svc.risk_path("skill-1-1-2")
    # prerequisites of skill-1-1-2 that aren't mastered → missing
    assert any(x["id"] == "skill-1-1-1" for x in r["missing_prereqs"])
