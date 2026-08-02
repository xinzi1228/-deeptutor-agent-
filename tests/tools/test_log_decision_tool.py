"""LogDecisionTool — kind validation + audit-trail recording."""

from __future__ import annotations

import pytest


class _FakeStore:
    """In-memory append_decision stand-in so tests never touch real files."""

    def __init__(self) -> None:
        self.decisions: list[dict] = []

    async def append_decision(self, decision: dict) -> dict:
        self.decisions.append(decision)
        return decision


def _patch_store(monkeypatch: pytest.MonkeyPatch) -> _FakeStore:
    from deeptutor.tools.log_decision_tool import LogDecisionTool

    store = _FakeStore()
    monkeypatch.setattr("deeptutor.services.learning_records.LearningRecordStore", lambda: store)
    return store


def test_definition_enum_includes_struggle_intervention() -> None:
    from deeptutor.tools.log_decision_tool import LogDecisionTool

    params = LogDecisionTool().get_definition().parameters
    kind_param = next(p for p in params if p.name == "kind")
    assert "struggle_intervention" in kind_param.enum
    assert "struggle_intervention" in kind_param.description


@pytest.mark.asyncio
async def test_log_decision_accepts_struggle_intervention(monkeypatch) -> None:
    from deeptutor.tools.log_decision_tool import LogDecisionTool

    store = _patch_store(monkeypatch)

    result = await LogDecisionTool().execute(
        kind="struggle_intervention",
        target="task1",
        rationale="反复漏标已确认，介入降难度重练",
    )

    assert result.success
    assert "struggle_intervention" in result.content
    assert result.metadata == {"kind": "struggle_intervention", "target": "task1"}
    assert len(store.decisions) == 1
    assert store.decisions[0]["kind"] == "struggle_intervention"
    assert store.decisions[0]["target"] == "task1"
    assert store.decisions[0]["rationale"] == "反复漏标已确认，介入降难度重练"


@pytest.mark.asyncio
async def test_log_decision_rejects_bogus_kind(monkeypatch) -> None:
    from deeptutor.tools.log_decision_tool import LogDecisionTool

    store = _patch_store(monkeypatch)

    result = await LogDecisionTool().execute(kind="bogus_kind", target="task1", rationale="x")

    assert not result.success
    assert "Error: kind must be" in result.content
    assert "struggle_intervention" in result.content
    assert store.decisions == []


@pytest.mark.asyncio
async def test_log_decision_rejects_missing_target_or_rationale(monkeypatch) -> None:
    from deeptutor.tools.log_decision_tool import LogDecisionTool

    store = _patch_store(monkeypatch)

    result = await LogDecisionTool().execute(kind="route_choice", target="", rationale="x")
    assert not result.success
    assert "target and rationale are required" in result.content
    assert store.decisions == []
