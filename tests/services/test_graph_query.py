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


def test_risk_path_struggling_carries_f1() -> None:
    svc = GraphQueryService(_graph())
    r = svc.risk_path("task2")
    struggling = {x["id"]: x for x in r["struggling"]}
    assert struggling["skill-1-1-2"]["f1"] == 0.65
    # mastered skills are never f1-tagged in the struggling list
    assert all("f1" not in x for x in r["missing_prereqs"])


def test_risk_path_finds_missing_prereq() -> None:
    # build a graph where 遮挡目标处理 has no learning trace but requires 边界框绘制规范
    records = []  # no learning records → nothing mastered
    svc = GraphQueryService(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records))
    r = svc.risk_path("skill-1-1-2")
    # prerequisites of skill-1-1-2 that aren't mastered → missing
    assert any(x["id"] == "skill-1-1-1" for x in r["missing_prereqs"])


def test_risk_path_outputs_sorted_by_id() -> None:
    # SAMPLE records → single struggling skill; ordering contract must be stable
    svc = GraphQueryService(_graph())
    r = svc.risk_path("task2")
    assert [x["id"] for x in r["missing_prereqs"]] == sorted(
        x["id"] for x in r["missing_prereqs"]
    )
    assert [x["id"] for x in r["struggling"]] == sorted(
        x["id"] for x in r["struggling"]
    )

    # no records → nothing mastered/struggling → the whole prerequisite closure
    # is missing; the output must be id-sorted, not DFS/pop-order
    svc = GraphQueryService(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=[]))
    r = svc.risk_path("task2")
    assert [x["id"] for x in r["missing_prereqs"]] == ["skill-1-1-1", "skill-1-1-2"]

    # both skills struggling → struggling is built from set iteration (hash-random
    # order across PYTHONHASHSEED) so it must be re-sorted by id
    records = [
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.5,
            "readiness": "needs_review",
        },
        {
            "type": "annotation_exercise",
            "task_id": "task2",
            "knowledge_point": "遮挡目标处理",
            "f1": 0.6,
            "readiness": "needs_review",
        },
    ]
    svc = GraphQueryService(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records))
    r = svc.risk_path("task2")
    assert [x["id"] for x in r["struggling"]] == ["skill-1-1-1", "skill-1-1-2"]
