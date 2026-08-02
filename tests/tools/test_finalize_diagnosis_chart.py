"""finalize_diagnosis emits progress chart metadata."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deeptutor.tools.finalize_diagnosis_tool import FinalizeDiagnosisTool


@pytest.mark.asyncio
async def test_finalize_emits_progress_chart(monkeypatch) -> None:
    def _fake_plan(*, force: bool = False) -> dict:
        return {"modules": [
            {"name": "标注基础", "concepts": ["a"], "tasks": ["task1"]},
            {"name": "进阶技能", "concepts": ["b"], "tasks": ["task2"]},
            {"name": "质量管控", "concepts": ["c"], "tasks": ["task3"]},
            {"name": "工具进阶", "concepts": ["d"], "tasks": ["task4"]},
        ]}

    monkeypatch.setattr("deeptutor.services.course_plan.rebuild", _fake_plan)

    store = MagicMock()
    store.save_brief.return_value = None
    monkeypatch.setattr("deeptutor.services.learning_records.LearningRecordStore", lambda: store)

    tool = FinalizeDiagnosisTool()
    result = await tool.execute(goal_type="job", teaching_mode="Standard")
    assert result.success
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "progress"
    assert chart["data"]["total"] == 4
