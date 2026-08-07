"""Tool-error result messaging for the tool dispatcher.

The dispatcher must surface tool failures as a readable Chinese message (with
the truncated exception reason) so the agentic loop keeps iterating instead of
crashing. Regression tests for E6.
"""

from __future__ import annotations

from typing import Any

import pytest

from deeptutor.core.agentic.tool_dispatch import execute_tool_call
from deeptutor.core.stream_bus import StreamBus


class _RaisingRegistry:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def execute(self, name: str, **kwargs: Any) -> None:
        raise self._exc


async def _run_tool(registry: _RaisingRegistry, *, factory: Any = None) -> dict[str, Any]:
    return await execute_tool_call(
        registry=registry,
        tool_name="exec",
        tool_args={},
        stream=StreamBus(),
        source="chat",
        stage="responding",
        retrieve_meta=None,
        unknown_error_message_factory=factory,
    )


@pytest.mark.asyncio
async def test_tool_error_returns_chinese_message_with_reason() -> None:
    result = await _run_tool(_RaisingRegistry(RuntimeError("boom boom detail")))

    assert result["success"] is False
    assert "执行失败" in result["result_text"]
    assert "boom boom detail" in result["result_text"]
    assert result["metadata"]["error"] == "boom boom detail"


@pytest.mark.asyncio
async def test_long_error_reason_truncated_to_300_chars_with_ellipsis() -> None:
    result = await _run_tool(_RaisingRegistry(RuntimeError("y" * 400)))

    assert result["success"] is False
    assert result["result_text"].endswith("…")
    assert ("y" * 300 + "…") in result["result_text"]
    assert ("y" * 301) not in result["result_text"]


@pytest.mark.asyncio
async def test_custom_factory_receives_tool_name_and_truncated_error() -> None:
    captured: dict[str, str] = {}

    def factory(tool_name: str, error: str) -> str:
        captured["tool_name"] = tool_name
        captured["error"] = error
        return "custom message"

    result = await _run_tool(_RaisingRegistry(RuntimeError("boom")), factory=factory)

    assert result["result_text"] == "custom message"
    assert result["success"] is False
    assert captured["tool_name"] == "exec"
    assert captured["error"] == "boom"


@pytest.mark.asyncio
async def test_custom_factory_receives_truncated_long_error() -> None:
    captured: dict[str, str] = {}

    def factory(tool_name: str, error: str) -> str:
        captured["error"] = error
        return error

    result = await _run_tool(_RaisingRegistry(RuntimeError("z" * 500)), factory=factory)

    assert result["result_text"] == ("z" * 300 + "…")
    assert len(captured["error"]) == 301
    assert captured["error"].endswith("…")
