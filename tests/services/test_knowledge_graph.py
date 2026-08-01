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
