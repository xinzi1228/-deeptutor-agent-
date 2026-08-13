from __future__ import annotations

import pytest

from deeptutor.services.visualization_artifacts import validate_visualization_request
from deeptutor.tools.delegate_expert_tool import (
    EXPERT_IDS,
    EXPERT_TOOL_WHITELISTS,
    load_expert_card,
)


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
    payload["unit"] = "比例"
    with pytest.raises(ValueError, match="dataset_ref"):
        validate_visualization_request(payload)


def test_chart_rejects_mismatched_or_non_numeric_data() -> None:
    base = {
        "kind": "chart", "title": "成绩", "source": "真实记录", "source_ref": "dataset_test", "unit": "分",
        "content": {"chart_type": "bar", "labels": ["A", "B"], "datasets": [{"label": "得分", "data": [1]}]},
    }
    with pytest.raises(ValueError, match="长度"):
        validate_visualization_request(base)
    base["content"]["datasets"][0]["data"] = [1, "虚构"]
    with pytest.raises(ValueError, match="真实数值"):
        validate_visualization_request(base)


def test_valid_chart_and_safe_mermaid() -> None:
    chart = validate_visualization_request({
        "kind": "chart", "title": "成绩趋势", "source": "学习记录", "source_ref": "dataset_test", "unit": "%",
        "source_updated_at": "2026-08-13",
        "content": {"chart_type": "line", "labels": ["1", "2"], "datasets": [{"label": "F1", "data": [60, 80]}]},
    })
    assert chart.render_protocol == "chartjs"
    assert chart.validation_status == "validated"

    diagram = validate_visualization_request({
        "kind": "diagram", "title": "标注流程", "source": "课程手册",
        "content": {"mermaid": 'flowchart LR\nA["选题"] --> B["标注"]'},
    })
    assert diagram.render_protocol == "mermaid"
    with pytest.raises(ValueError, match="不安全"):
        validate_visualization_request({"kind": "diagram", "title": "坏图", "content": {"mermaid": "flowchart LR\nclick A javascript:alert(1)"}})


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
