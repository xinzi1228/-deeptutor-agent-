"""write_learning_record triggers graph incremental update."""

from __future__ import annotations

import pytest


class _FakeAppender:
    """Stand-in for LearningRecordStore — persists nothing, echoes the record."""

    def __init__(self, record: dict) -> None:
        self._record = record

    async def append(self, record: dict) -> dict:
        self._record = record
        return self._record


@pytest.mark.asyncio
async def test_append_triggers_graph_update(monkeypatch) -> None:
    from deeptutor.tools.write_learning_record import WriteLearningRecordTool

    called = []

    class FakeStore:
        def incremental_update(self, record):
            called.append(record)
            return {}

    monkeypatch.setattr(
        "deeptutor.services.knowledge_graph.KnowledgeGraphStore",
        lambda: FakeStore(),
    )

    record = {
        "type": "annotation_exercise",
        "task_id": "task1",
        "knowledge_point": "边界框绘制规范",
        "f1": 0.85,
        "readiness": "advance",
        "timestamp": "2026-08-01T00:00:00+00:00",
    }
    monkeypatch.setattr(
        "deeptutor.services.learning_records.LearningRecordStore",
        lambda: _FakeAppender(record),
    )

    tool = WriteLearningRecordTool()
    result = await tool.execute(record=record)
    assert result.success
    assert len(called) == 1
    assert called[0]["knowledge_point"] == "边界框绘制规范"


@pytest.mark.asyncio
async def test_graph_update_failure_does_not_block_persist(monkeypatch) -> None:
    from deeptutor.tools.write_learning_record import WriteLearningRecordTool

    class Boom:
        def incremental_update(self, record):
            raise RuntimeError("graph boom")

    record = {
        "type": "theory_mastered",
        "knowledge_point": "边界框绘制规范",
        "readiness": "advance",
        "timestamp": "2026-08-01T00:00:00+00:00",
    }

    monkeypatch.setattr(
        "deeptutor.services.knowledge_graph.KnowledgeGraphStore",
        lambda: Boom(),
    )
    monkeypatch.setattr(
        "deeptutor.services.learning_records.LearningRecordStore",
        lambda: _FakeAppender(record),
    )

    tool = WriteLearningRecordTool()
    result = await tool.execute(record=record)
    assert result.success  # record still saved even though graph update failed
