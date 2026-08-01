"""graph_query registration tests."""

from __future__ import annotations


def test_graph_query_in_builtin_tool_names() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES

    assert "graph_query" in BUILTIN_TOOL_NAMES


def test_graph_query_in_class_list() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOL_TYPES

    assert any(getattr(cls, "name", None) == "graph_query" or cls.__name__ == "GraphQueryTool" for cls in BUILTIN_TOOL_TYPES)


def test_graph_query_in_always_on() -> None:
    import inspect

    import deeptutor.agents._shared.tool_composition as tc

    src = inspect.getsource(tc)
    assert '"graph_query"' in src
