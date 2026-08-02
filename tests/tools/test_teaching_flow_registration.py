"""teaching_flow registration tests."""

from __future__ import annotations


def test_teaching_flow_in_builtin() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES

    assert "teaching_flow" in BUILTIN_TOOL_NAMES


def test_teaching_flow_in_configurable() -> None:
    from deeptutor.tools.builtin import CONFIGURABLE_BUILTIN_TOOL_NAMES

    assert "teaching_flow" in CONFIGURABLE_BUILTIN_TOOL_NAMES


def test_teaching_flow_in_always_on() -> None:
    import inspect

    import deeptutor.agents._shared.tool_composition as tc

    src = inspect.getsource(tc)
    assert '"teaching_flow"' in src
