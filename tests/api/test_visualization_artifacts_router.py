from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.api.routers.profile import (
    VisualizationRerenderRequest,
    profile_visualization_source,
    profile_visualizations,
    rerender_profile_visualization,
)
from deeptutor.services.visualization_artifacts import (
    VisualizationArtifactStore,
    freeze_dataset_snapshot,
    validate_visualization_request,
)


def _saved_chart(profile_root: Path) -> str:
    content = {
        "chart_type": "line",
        "labels": ["第一次", "第二次"],
        "datasets": [{"label": "F1", "data": [0.5, 0.8]}],
    }
    snapshot = freeze_dataset_snapshot(
        profile_root,
        dataset_id="learning_metrics:learning_f1_trend",
        version=2,
        query={"limit": 2},
        source="当前学习档案的学习记录",
        unit="比例（0-1）",
        source_updated_at="2026-08-15T08:00:00+00:00",
        content=content,
    )
    artifact = validate_visualization_request(
        {
            "kind": "chart",
            "title": "F1 趋势",
            "source": snapshot["source"],
            "source_ref": snapshot["snapshot_id"],
            "unit": snapshot["unit"],
            "source_updated_at": snapshot["source_updated_at"],
            "dataset_ref": snapshot["dataset_ref"],
            "content": content,
        },
        profile_id=profile_root.name,
        session_id="coach-session-1",
        message_id="turn-1",
    )
    VisualizationArtifactStore(profile_root).save(artifact)
    return artifact.id


@pytest.mark.asyncio
async def test_visualization_source_is_student_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_id = _saved_chart(tmp_path)
    monkeypatch.setattr(
        "deeptutor.multi_user.paths.get_current_learning_profile_root",
        lambda **_kwargs: tmp_path,
    )

    result = await profile_visualization_source(artifact_id)

    dataset_ref = result["source"]["dataset_ref"]
    assert dataset_ref["dataset_id"] == "learning_metrics:learning_f1_trend"
    assert dataset_ref["version"] == 2
    assert "sha256" not in dataset_ref


@pytest.mark.asyncio
async def test_visualization_rerender_and_session_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_id = _saved_chart(tmp_path)
    monkeypatch.setattr(
        "deeptutor.multi_user.paths.get_current_learning_profile_root",
        lambda **_kwargs: tmp_path,
    )

    rerendered = await rerender_profile_visualization(
        artifact_id, VisualizationRerenderRequest(chart_type="bar")
    )
    matching = await profile_visualizations(session_id="coach-session-1")
    missing = await profile_visualizations(session_id="other-session")

    assert rerendered["artifact"]["content"]["chart_type"] == "bar"
    assert [item["id"] for item in matching["artifacts"]] == [artifact_id]
    assert missing["artifacts"] == []
