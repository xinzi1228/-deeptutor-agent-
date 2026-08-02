"""struggle_detect registration tests."""

from __future__ import annotations


def test_struggle_detect_in_builtin() -> None:
    from deeptutor.tools.builtin import BUILTIN_TOOL_NAMES

    assert "struggle_detect" in BUILTIN_TOOL_NAMES


def test_struggle_detect_in_configurable() -> None:
    from deeptutor.tools.builtin import CONFIGURABLE_BUILTIN_TOOL_NAMES

    assert "struggle_detect" in CONFIGURABLE_BUILTIN_TOOL_NAMES


def test_struggle_detect_in_always_on() -> None:
    import inspect

    import deeptutor.agents._shared.tool_composition as tc

    src = inspect.getsource(tc)
    assert '"struggle_detect"' in src
