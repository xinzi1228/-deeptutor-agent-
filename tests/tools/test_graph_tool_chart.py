"""graph_query risk_path emits graph chart metadata."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_risk_path_emits_graph_chart(monkeypatch) -> None:
    from deeptutor.services.knowledge_graph import KnowledgeGraphStore
    from deeptutor.tools.graph_tool import GraphQueryTool
    from tests.services.test_knowledge_graph import SAMPLE_BANK, SAMPLE_RECORDS, SAMPLE_TREE

    async def _fake_load(*, tree=None, bank=None, records=None) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    async def _fake_explain(query, target) -> str:
        return None

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_load)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_explain)

    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="task2")
    assert result.success
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "graph"
    assert "nodes" in chart["data"]
    assert "edges" in chart["data"]
    # target node should be marked
    assert any(n["id"] == "task2" for n in chart["data"]["nodes"])
