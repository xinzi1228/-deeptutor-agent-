"""LLM batch dedup for learning records (TencentDB-Agent-Memory borrow).

The four actions store/skip/update/merge decide how new records relate to
existing ones. LLM failures must never lose records — every fallback keeps
the new record via ``store``.
"""

from __future__ import annotations

import json

from deeptutor.services.learning_records_dedup import (
    apply_decision,
    build_candidates,
    merge_anchor_group,
    parse_decisions,
)


def _record(**overrides) -> dict:
    base = {
        "type": "annotation_exercise",
        "task_id": "task1",
        "knowledge_point": "边界框绘制规范",
        "f1": 0.85,
        "readiness": "advance",
        "confidence": 0.8,
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_build_candidates_clusters_by_anchor():
    records = [
        _record(task_id="task1", knowledge_point="边界框绘制规范"),
        _record(task_id="task1", knowledge_point="边界框绘制规范", f1=0.9),
        _record(task_id="task2", knowledge_point="NLP 命名实体"),
    ]
    groups = build_candidates(records)
    assert any(len(g) > 1 for g in groups)
    assert sum(len(g) for g in groups) == 3


def test_parse_decisions_valid():
    raw = json.dumps([
        {"record_id": "r1", "action": "store", "target_ids": []},
        {"record_id": "r2", "action": "merge", "target_ids": ["old1"],
         "merged_content": "合并后", "merged_type": "annotation_exercise",
         "merged_confidence": 0.9},
    ])
    decisions = parse_decisions(raw, new_ids=["r1", "r2"])
    assert decisions["r1"]["action"] == "store"
    assert decisions["r2"]["action"] == "merge"
    assert decisions["r2"]["target_ids"] == ["old1"]
    assert decisions["r2"]["merged_confidence"] == 0.9


def test_parse_decisions_invalid_action_defaults_store():
    raw = json.dumps([{"record_id": "r1", "action": "delete"}])
    decisions = parse_decisions(raw, new_ids=["r1"])
    assert decisions["r1"]["action"] == "store"


def test_parse_decisions_missing_record_defaults_store():
    decisions = parse_decisions("not-json", new_ids=["r1", "r2"])
    assert decisions["r1"]["action"] == "store"
    assert decisions["r2"]["action"] == "store"


def test_apply_store_adds_record():
    records = [_record(timestamp="2026-08-01T00:00:00+00:00")]
    new = _record(f1=0.7, timestamp="2026-08-02T00:00:00+00:00")
    out = apply_decision(records, new, {"action": "store", "target_ids": []})
    assert len(out) == 2
    assert not out[-1].get("archived")


def test_apply_merge_archives_targets_and_lifts_confidence():
    old = _record(confidence=0.7, timestamp="2026-08-01T00:00:00+00:00")
    new = _record(confidence=0.8, timestamp="2026-08-02T00:00:00+00:00")
    records = [old]
    out = apply_decision(
        records,
        new,
        {
            "action": "merge",
            "target_ids": ["2026-08-01T00:00:00+00:00"],
            "merged_content": "合并后的边界框规范记忆",
            "merged_confidence": 0.9,
        },
    )
    merged = [r for r in out if r.get("timestamp") == "2026-08-02T00:00:00+00:00"][0]
    assert merged["confidence"] == 0.9
    assert merged.get("merged_from") == ["2026-08-01T00:00:00+00:00"]
    assert any(r.get("archived") for r in out)


def test_apply_skip_keeps_new_unstored():
    records = [_record(timestamp="2026-08-01T00:00:00+00:00")]
    new = _record(f1=0.6, timestamp="2026-08-02T00:00:00+00:00")
    out = apply_decision(records, new, {"action": "skip", "target_ids": []})
    assert len(out) == 1


def test_apply_update_archives_target():
    old = _record(confidence=0.6, timestamp="2026-08-01T00:00:00+00:00")
    new = _record(confidence=0.9, timestamp="2026-08-02T00:00:00+00:00")
    out = apply_decision(
        records=[old],
        new_record=new,
        decision={"action": "update", "target_ids": ["2026-08-01T00:00:00+00:00"], "merged_confidence": 0.95},
    )
    updated = [r for r in out if r.get("timestamp") == "2026-08-02T00:00:00+00:00"][0]
    assert updated["confidence"] == 0.95
    assert updated.get("updated_from") == ["2026-08-01T00:00:00+00:00"]


def test_parse_decisions_robust_against_malformed():
    raw = json.dumps([
        {"record_id": "r1", "action": "store", "target_ids": 5},           # int target_ids
        {"record_id": "r2", "action": "merge", "merged_type": ["x"]},      # list merged_type
    ])
    decisions = parse_decisions(raw, new_ids=["r1", "r2"])
    assert decisions["r1"]["action"] == "store"
    assert decisions["r1"]["target_ids"] == []  # int target_ids 不报错
    assert decisions["r2"]["action"] == "merge"  # 非法 merged_type 字段被置空，条目保留
    assert decisions["r2"]["merged_type"] is None  # list 不参与 in 判断


def test_parse_decisions_string_target_ids_not_char_split():
    raw = json.dumps([{"record_id": "r1", "action": "update",
                       "target_ids": "old1,old2"}])
    decisions = parse_decisions(raw, new_ids=["r1"])
    assert decisions["r1"]["target_ids"] == []  # 字符串不拆分


def test_apply_decision_invalid_action_defaults_store():
    records = [_record(timestamp="2026-08-01T00:00:00+00:00")]
    new = _record(f1=0.7, timestamp="2026-08-02T00:00:00+00:00")
    out = apply_decision(records, new, {"action": "delete", "target_ids": ["2026-08-01T00:00:00+00:00"]})
    # invalid action → store：不归档目标、追加新记录
    assert not any(r.get("archived") for r in out)
    assert len(out) == 2


def test_parse_decisions_strips_markdown_fence():
    raw = "```json\n" + json.dumps([{"record_id": "r1", "action": "store"}]) + "\n```"
    decisions = parse_decisions(raw, new_ids=["r1"])
    assert decisions["r1"]["action"] == "store"


def test_merge_anchor_group_converges_in_place():
    old = _record(
        confidence=0.7,
        timestamp="2026-08-01T00:00:00+00:00",
        knowledge_points=["边界框绘制规范"],
        pattern_evidence=["ep1", "ep2"],
    )
    latest = _record(
        confidence=0.9,
        timestamp="2026-08-02T00:00:00+00:00",
        knowledge_points=["边界框绘制规范", "标签类别"],
        pattern_evidence=["ep2", "ep3"],
    )
    records = [old, latest]

    out = merge_anchor_group(records, [old, latest])

    # 原地收敛：不追加副本
    assert len(out) == 2
    canonical = [r for r in out if not r.get("archived")]
    assert len(canonical) == 1
    assert canonical[0] is latest  # 最新记录即 canonical，原地更新
    assert old.get("archived") is True
    assert canonical[0]["confidence"] == 0.9  # 取组内置信度最大值
    assert canonical[0]["merged_from"] == ["2026-08-01T00:00:00+00:00"]
    assert set(canonical[0]["knowledge_points"]) == {"边界框绘制规范", "标签类别"}
    assert canonical[0]["pattern_evidence"] == ["ep1", "ep2", "ep3"]


def _tmp_store(tmp_path):
    import deeptutor.services.learning_records as lr_mod

    store = lr_mod.LearningRecordStore()
    store._root = tmp_path
    store._file = tmp_path / "records.jsonl"
    return store


def test_reflect_anchor_merge_path(tmp_path):
    store = _tmp_store(tmp_path)
    store._write_all([
        _record(confidence=0.7, timestamp="2026-08-01T00:00:00+00:00"),
        _record(confidence=0.9, timestamp="2026-08-02T00:00:00+00:00"),
    ])

    result = store.reflect()
    assert result["dedup_mode"] == "anchor-merge"
    assert result["records_archived"] >= 1
    assert result["active_records"] == 1  # 去重收敛：同一锚点只留 1 条活跃记录
    records = store._read_records()
    merged = [r for r in records if r.get("merged_from")]
    assert merged, "expected a merged record"
    assert merged[0]["confidence"] == 0.9  # 最新记录置信度提升
    active = [r for r in records if not r.get("archived")]
    assert len(active) == 1

    # 再次 reflect 不新增重复：活跃数保持 1
    result2 = store.reflect()
    assert result2["active_records"] == 1
    records2 = store._read_records()
    assert len([r for r in records2 if not r.get("archived")]) == 1


def test_reflect_falls_back_on_dedup_failure(monkeypatch, tmp_path):
    def _boom(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(
        "deeptutor.services.learning_records_dedup.build_candidates", _boom
    )
    store = _tmp_store(tmp_path)
    store._write_all([
        _record(f1=0.7, timestamp="2026-08-01T00:00:00+00:00"),
        _record(f1=0.9, timestamp="2026-08-02T00:00:00+00:00"),
    ])

    result = store.reflect()
    assert "clusters_merged" in result  # 回退到规则式
    assert result.get("dedup_mode") != "anchor-merge"
    records = store._read_records()
    assert len(records) >= 1  # 不丢记录
