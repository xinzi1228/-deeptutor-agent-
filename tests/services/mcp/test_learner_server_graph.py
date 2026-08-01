"""learner_server knowledge-graph tools."""

from __future__ import annotations

from deeptutor.services.mcp import learner_server


def test_graph_tools_registered() -> None:
    names = {t.name for t in learner_server._TOOLS}
    assert "get_knowledge_graph" in names
    assert "query_risk_path" in names
