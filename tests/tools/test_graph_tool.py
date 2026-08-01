"""GraphQueryTool tests — deterministic result + LLM explanation fallback."""

from __future__ import annotations

import pytest

from deeptutor.services.knowledge_graph import KnowledgeGraphStore
from deeptutor.tools.graph_tool import GraphQueryTool
from tests.services.test_knowledge_graph import SAMPLE_BANK, SAMPLE_RECORDS, SAMPLE_TREE


@pytest.mark.asyncio
async def test_mastery_query_no_llm(monkeypatch) -> None:
    async def _fake_build(*, tree=None, bank=None, records=None) -> dict:
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
    async def _fake_build(*, tree=None, bank=None, records=None) -> dict:
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
    async def _fake_build(*, tree=None, bank=None, records=None) -> dict:
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
async def test_risk_path_low_confidence_skips_llm_explanation(monkeypatch) -> None:
    async def _fake_build(*, tree=None, bank=None, records=None) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    calls: list[str] = []

    async def _fake_reason(query, context="", **kwargs) -> dict:
        calls.append(query)
        return {"answer": "不应出现"}

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_build)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_reason)
    tool = GraphQueryTool()
    # task1 → 边界框绘制规范 mastered, no risk → confidence low → no LLM call
    result = await tool.execute(query_type="risk_path", target="task1")
    assert result.success
    assert "风险链分析" in result.content
    assert calls == []
    assert "不应出现" not in result.content


@pytest.mark.asyncio
async def test_load_graph_short_circuits_with_persisted_graph(monkeypatch) -> None:
    def _boom() -> None:
        raise AssertionError("tree/bank/records must not load when a graph is persisted")

    def _persisted_graph(_self) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_competency_tree", _boom)
    monkeypatch.setattr("deeptutor.tools.graph_tool._load_bank", _boom)
    monkeypatch.setattr("deeptutor.tools.graph_tool._list_records", _boom)
    monkeypatch.setattr(
        "deeptutor.services.knowledge_graph.KnowledgeGraphStore.get", _persisted_graph
    )
    tool = GraphQueryTool()
    result = await tool.execute(query_type="mastery", target="")
    assert result.success
    assert "已掌握" in result.content


@pytest.mark.asyncio
async def test_risk_path_formats_f1_from_struggling(monkeypatch) -> None:
    async def _fake_build(*, tree=None, bank=None, records=None) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    async def _fake_reason(query, context="", **kwargs) -> dict:
        return None

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_build)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_reason)
    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="task2")
    assert result.success
    assert "F1=0.65" in result.content


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
