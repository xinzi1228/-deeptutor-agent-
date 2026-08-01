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


def test_build_latest_record_wins_same_target() -> None:
    records = [
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.82,
            "readiness": "advance",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.55,
            "readiness": "needs_review",
            "timestamp": "2026-01-02T00:00:00+00:00",
        },
    ]
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records)
    edges = [
        e
        for e in g["edges"]
        if e["source"] == "learner:default" and e["target"] == "skill-1-1-1"
    ]
    assert len(edges) == 1
    assert edges[0]["type"] == "struggling"
    assert edges[0]["ts"] == "2026-01-02T00:00:00+00:00"


def test_build_same_type_duplicate_keeps_latest() -> None:
    records = [
        {
            "type": "annotation_exercise",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.82,
            "readiness": "advance",
            "timestamp": "2026-01-01T00:00:00+00:00",
        },
        {
            "type": "annotation_exercise",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.95,
            "readiness": "advance",
            "timestamp": "2026-01-03T00:00:00+00:00",
        },
    ]
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records)
    edges = [
        e
        for e in g["edges"]
        if e["source"] == "learner:default" and e["target"] == "skill-1-1-1"
    ]
    assert len(edges) == 1
    assert edges[0]["type"] == "mastered"
    assert edges[0]["ts"] == "2026-01-03T00:00:00+00:00"


def test_build_latest_record_wins_by_list_order_without_timestamp() -> None:
    records = [
        {
            "type": "annotation_exercise",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.82,
            "readiness": "advance",
        },
        {
            "type": "annotation_exercise",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.55,
            "readiness": "needs_review",
        },
    ]
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records)
    edges = [
        e
        for e in g["edges"]
        if e["source"] == "learner:default" and e["target"] == "skill-1-1-1"
    ]
    assert len(edges) == 1
    assert edges[0]["type"] == "struggling"


def test_build_unparseable_f1_falls_back_to_readiness() -> None:
    records = [
        {
            "type": "annotation_exercise",
            "knowledge_point": "边界框绘制规范",
            "f1": "abc",
            "readiness": "advance",
        },
    ]
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records)
    edges = [
        e
        for e in g["edges"]
        if e["source"] == "learner:default" and e["target"] == "skill-1-1-1"
    ]
    assert len(edges) == 1
    assert edges[0]["type"] == "mastered"


def test_build_skips_record_without_classification() -> None:
    records = [
        {
            "type": "annotation_exercise",
            "knowledge_point": "边界框绘制规范",
            "f1": "abc",
        },
    ]
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=records)
    edges = [
        e
        for e in g["edges"]
        if e["source"] == "learner:default" and e["target"] == "skill-1-1-1"
    ]
    assert edges == []


def test_build_omits_belongs_to_when_no_group_found() -> None:
    bank = {
        "task3": {
            "title": "无知识点任务",
            "type": "bbox",
            "knowledge_points": ["不存在的能力点"],
        },
    }
    g = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=bank, records=[])
    assert "unknown" not in g["nodes"]
    assert not any(
        e["type"] == "belongs_to" for e in g["edges"] if e["source"] == "task3"
    )


def test_build_without_tree() -> None:
    g = KnowledgeGraphStore.build(tree=None, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)
    assert "learner:default" in g["nodes"]


def test_save_get_roundtrip(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    graph = KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)
    store.save(graph)
    assert store.get() == graph


def test_get_missing_returns_none(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    assert store.get() is None


def test_get_corrupt_returns_none(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    store._file.parent.mkdir(parents=True, exist_ok=True)
    store._file.write_bytes(b"not json")
    assert store.get() is None


# ------------------------------------------------------------- incremental


def test_incremental_update_no_duplicate(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    store.save(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS))

    record = {
        "type": "annotation_exercise",
        "task_id": "task2",
        "knowledge_point": "遮挡目标处理",
        "f1": 0.9,
        "readiness": "advance",
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    store.incremental_update(record)
    g1 = store.incremental_update(record)  # same record twice → idempotent
    edges = [(e["source"], e["type"], e["target"]) for e in g1["edges"]]
    mastered_targets = [(s, t) for (s, typ, t) in edges if typ == "mastered" and s == "learner:default"]
    assert mastered_targets.count(("learner:default", "skill-1-1-2")) == 1


def test_incremental_update_reclassifies_skill(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    store.save(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS))
    # 遮挡目标处理 was struggling (f1=0.65); now f1=0.9 → mastered, struggling must disappear
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
    edges = [(e["source"], e["type"], e["target"]) for e in g["edges"]]
    assert ("learner:default", "mastered", "skill-1-1-2") in edges
    assert ("learner:default", "struggling", "skill-1-1-2") not in edges


def test_incremental_update_no_graph_builds_from_records(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    # no graph file exists; record targets a skill — resolve via explicit ontology
    # explicit records=[] keeps the test deterministic (no real-workspace dependency)
    store.incremental_update(
        {
            "type": "theory_mastered",
            "knowledge_point": "遮挡目标处理",
            "readiness": "advance",
            "timestamp": "2026-08-03T00:00:00+00:00",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    g = store.get()
    assert g is not None
    edges = [(e["source"], e["type"], e["target"]) for e in g["edges"]]
    assert ("learner:default", "mastered", "skill-1-1-2") in edges


def test_incremental_update_skips_older_record(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    store.save(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=[]))
    # newer record first → mastered
    store.incremental_update(
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.9,
            "readiness": "advance",
            "timestamp": "2026-08-10T00:00:00+00:00",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    # then an OLDER record → must be skipped so the graph stays consistent
    # with a full rebuild (latest record wins)
    store.incremental_update(
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.65,
            "readiness": "needs_review",
            "timestamp": "2026-08-01T00:00:00+00:00",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    g = store.get()
    edges = [
        e
        for e in g["edges"]
        if e["source"] == "learner:default" and e["target"] == "skill-1-1-1"
    ]
    assert len(edges) == 1
    assert edges[0]["type"] == "mastered"
    assert edges[0]["ts"] == "2026-08-10T00:00:00+00:00"


def test_incremental_update_skips_older_record_without_timestamp_applies(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    store.save(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=[]))
    store.incremental_update(
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.9,
            "readiness": "advance",
            "timestamp": "2026-08-10T00:00:00+00:00",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    # a record without a timestamp is treated as newest → it replaces the edge
    store.incremental_update(
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.55,
            "readiness": "needs_review",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    g = store.get()
    edges = [
        e
        for e in g["edges"]
        if e["source"] == "learner:default" and e["target"] == "skill-1-1-1"
    ]
    assert len(edges) == 1
    assert edges[0]["type"] == "struggling"


def test_incremental_update_unclassifiable_returns_persisted_graph(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    g = store.incremental_update(
        {
            "type": "annotation_exercise",
            "knowledge_point": "边界框绘制规范",
            "f1": "abc",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    assert isinstance(g, dict)
    assert g.get("schema_version") == 1
    assert "learner:default" in g["nodes"]
    assert not any(
        e["source"] == "learner:default" and e["type"] in ("mastered", "struggling")
        for e in g["edges"]
    )
    assert store.get() == g


def test_incremental_update_does_not_regress_built_at(tmp_path) -> None:
    store = KnowledgeGraphStore(root=tmp_path)
    store.save(KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=[]))
    store.incremental_update(
        {
            "type": "annotation_exercise",
            "task_id": "task1",
            "knowledge_point": "边界框绘制规范",
            "f1": 0.9,
            "readiness": "advance",
            "timestamp": "2026-08-01T00:00:00+00:00",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    # newer built_at must survive an older record applied to a different target
    store.incremental_update(
        {
            "type": "annotation_exercise",
            "task_id": "task2",
            "knowledge_point": "遮挡目标处理",
            "f1": 0.65,
            "readiness": "needs_review",
            "timestamp": "2020-01-01T00:00:00+00:00",
        },
        tree=SAMPLE_TREE,
        bank=SAMPLE_BANK,
        records=[],
    )
    g = store.get()
    assert g["built_at"] == "2026-08-01T00:00:00+00:00"
