from __future__ import annotations

import json
from pathlib import Path

import pytest

from deeptutor.services.visualization_artifacts import (
    VisualizationArtifactStore,
    freeze_dataset_snapshot,
    load_verified_dataset_snapshot,
    validate_visualization_request,
)
from deeptutor.tools.delegate_expert_tool import (
    EXPERT_IDS,
    EXPERT_TOOL_WHITELISTS,
    load_expert_card,
)


def _dataset_ref() -> dict:
    return {
        "dataset_id": "learning_metrics:annotation_attempt_metrics",
        "version": 1,
        "query": {"limit": 12},
        "unit": "比例（0-1）",
        "sha256": "a" * 64,
    }


def test_chart_requires_real_source_and_unit() -> None:
    payload = {
        "kind": "chart", "title": "最近成绩", "description": "F1 趋势",
        "content": {"chart_type": "line", "labels": ["第1次"], "datasets": [{"label": "F1", "data": [0.8]}]},
    }
    with pytest.raises(ValueError, match="来源"):
        validate_visualization_request(payload)
    payload["source"] = "当前学习档案 annotation/attempts.jsonl"
    with pytest.raises(ValueError, match="单位"):
        validate_visualization_request(payload)
    payload["unit"] = "比例（0-1）"
    with pytest.raises(ValueError, match="dataset_ref"):
        validate_visualization_request(payload)


def test_chart_rejects_mismatched_or_non_numeric_data() -> None:
    base = {
        "kind": "chart", "title": "成绩", "source": "真实记录", "source_ref": "dataset_test", "unit": "比例（0-1）",
        "dataset_ref": _dataset_ref(),
        "content": {"chart_type": "bar", "labels": ["A", "B"], "datasets": [{"label": "得分", "data": [1]}]},
    }
    with pytest.raises(ValueError, match="长度"):
        validate_visualization_request(base)
    base["content"]["datasets"][0]["data"] = [1, "虚构"]
    with pytest.raises(ValueError, match="真实数值"):
        validate_visualization_request(base)


def test_valid_chart_and_safe_mermaid() -> None:
    chart = validate_visualization_request({
        "kind": "chart", "title": "成绩趋势", "source": "学习记录", "source_ref": "dataset_test", "unit": "比例（0-1）",
        "dataset_ref": _dataset_ref(),
        "source_updated_at": "2026-08-13",
        "content": {"chart_type": "line", "labels": ["1", "2"], "datasets": [{"label": "F1", "data": [60, 80]}]},
    }, profile_id="student-a", session_id="session-a", message_id="message-a")
    assert chart.render_protocol == "chartjs"
    assert chart.validation_status == "validated"
    assert chart.profile_id == "student-a"
    assert chart.session_id == "session-a"
    assert chart.message_id == "message-a"
    assert chart.dataset_ref["sha256"] == "a" * 64

    diagram = validate_visualization_request({
        "kind": "diagram", "title": "标注流程", "source": "课程手册",
        "content": {"mermaid": 'flowchart LR\nA["选题"] --> B["标注"]'},
    })
    assert diagram.render_protocol == "mermaid"
    with pytest.raises(ValueError, match="不安全"):
        validate_visualization_request({"kind": "diagram", "title": "坏图", "content": {"mermaid": "flowchart LR\nclick A javascript:alert(1)"}})


def test_dataset_snapshot_hash_is_verified_on_every_read(tmp_path: Path) -> None:
    snapshot = freeze_dataset_snapshot(
        tmp_path,
        dataset_id="learning_metrics:learning_f1_trend",
        version=3,
        query={"limit": 2},
        source="当前学习档案的学习记录",
        unit="比例（0-1）",
        source_updated_at="2026-08-14T08:00:00+00:00",
        content={
            "chart_type": "line",
            "labels": ["第一次", "第二次"],
            "datasets": [{"label": "F1", "data": [0.5, 0.8]}],
        },
    )
    loaded = load_verified_dataset_snapshot(tmp_path, snapshot["snapshot_id"])
    assert loaded["dataset_ref"]["sha256"] == snapshot["dataset_ref"]["sha256"]

    path = (
        tmp_path
        / "artifacts"
        / "visualization_datasets"
        / f"{snapshot['snapshot_id']}.json"
    )
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["content"]["datasets"][0]["data"][1] = 0.99
    path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="哈希"):
        load_verified_dataset_snapshot(tmp_path, snapshot["snapshot_id"])


def test_server_rerender_preserves_dataset_and_values(tmp_path: Path) -> None:
    snapshot = freeze_dataset_snapshot(
        tmp_path,
        dataset_id="learning_metrics:learning_f1_trend",
        version=1,
        query={"limit": 2},
        source="学习记录",
        unit="比例（0-1）",
        source_updated_at="2026-08-14T08:00:00+00:00",
        content={
            "chart_type": "line",
            "labels": ["1", "2"],
            "datasets": [{"label": "F1", "data": [0.5, 0.8]}],
        },
    )
    artifact = validate_visualization_request(
        {
            "kind": "chart",
            "title": "F1 趋势",
            "source": "学习记录",
            "source_ref": snapshot["snapshot_id"],
            "unit": "比例（0-1）",
            "dataset_ref": snapshot["dataset_ref"],
            "content": snapshot["content"],
        },
        profile_id="student-a",
        session_id="session-a",
        message_id="message-a",
    )
    store = VisualizationArtifactStore(tmp_path)
    store.save(artifact)

    rerendered = store.rerender_chart(artifact.id, "bar")

    assert rerendered["content"]["chart_type"] == "bar"
    assert rerendered["content"]["datasets"] == artifact.content["datasets"]
    assert rerendered["dataset_ref"]["sha256"] == artifact.dataset_ref["sha256"]
    assert [row["id"] for row in store.list(session_id="session-a")] == [artifact.id]
    assert store.list(session_id="another-session") == []
    assert [row["id"] for row in store.list(message_id="message-a")] == [artifact.id]


def test_visual_specialists_exist_and_are_isolated() -> None:
    for expert in ("chart_designer", "diagram_designer", "illustration_designer"):
        assert expert in EXPERT_IDS
        assert load_expert_card(expert)
    assert EXPERT_TOOL_WHITELISTS["chart_designer"] == (
        "read_learning_chart_data",
        "create_visualization",
    )
    assert EXPERT_TOOL_WHITELISTS["diagram_designer"] == ("create_visualization",)
    assert EXPERT_TOOL_WHITELISTS["illustration_designer"] == ()
