"""GraphQueryTool tests — deterministic result + LLM explanation fallback."""

from __future__ import annotations

import pytest

from deeptutor.tools.graph_tool import GraphQueryTool
from deeptutor.services.knowledge_graph import KnowledgeGraphStore
from tests.services.test_knowledge_graph import SAMPLE_TREE, SAMPLE_BANK, SAMPLE_RECORDS


@pytest.mark.asyncio
async def test_mastery_query_no_llm(monkeypatch) -> None:
    async def _fake_build(*, tree, bank, records) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    monkeypatch.setattr(
        "deeptutor.tools.graph_tool._load_graph",
        _fake_build,
    )
    tool = GraphQueryTool()
    result = await tool.execute(query_type="mastery", target="")
    assert result.success
    assert "已掌握" in result.content


@pytest.mark.asyncio
async def test_risk_path_with_llm_explanation(monkeypatch) -> None:
    async def _fake_build(*, tree, bank, records) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    async def _fake_reason(query, context="", **kwargs) -> dict:
        return {"answer": "task2 有风险：前置'遮挡目标处理'F1=0.65 未达标，建议先补。"}

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_build)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_reason)
    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="task2")
    assert result.success
    assert "task2 有风险" in result.content


@pytest.mark.asyncio
async def test_risk_path_llm_fails_degrades_to_structured(monkeypatch) -> None:
    async def _fake_build(*, tree, bank, records) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    async def _fake_reason(query, context="", **kwargs) -> dict:
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_build)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_reason)
    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="task2")
    assert result.success
    assert "风险链分析" in result.content  # structured result still returned


@pytest.mark.asyncio
async def test_unknown_query_type_rejected(monkeypatch) -> None:
    tool = GraphQueryTool()
    result = await tool.execute(query_type="bogus", target="task2")
    assert not result.success


@pytest.mark.asyncio
async def test_risk_path_requires_target(monkeypatch) -> None:
    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="")
    assert not result.success
