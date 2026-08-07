"""Dangling tool-call patching for interrupted turns.

When a user stops a turn mid-loop, ``conversation_history`` can carry an
assistant message with ``tool_calls`` but no matching ``role=tool`` result.
``_patch_dangling_tool_calls`` inserts a synthetic "call interrupted"
placeholder so the next turn's messages stay well-formed for the LLM.
"""

from __future__ import annotations

from deeptutor.agents.chat.agentic_pipeline import AgenticChatPipeline
from deeptutor.core.context import UnifiedContext


def _pipeline() -> AgenticChatPipeline:
    return AgenticChatPipeline(language="en")


def _assistant_with_call(call_id: str = "call_1", name: str = "web_fetch") -> dict:
    return {
        "role": "assistant",
        "content": "Let me look that up",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": "{}"},
            }
        ],
    }


def test_dangling_tool_call_patched() -> None:
    pipeline = _pipeline()
    context = UnifiedContext(
        session_id="s1",
        user_message="next question",
        conversation_history=[
            {"role": "user", "content": "do it"},
            _assistant_with_call("call_1"),
        ],
    )

    messages = pipeline._build_loop_messages(
        context=context,
        enabled_tools=[],
    )

    assistant_idx = next(i for i, m in enumerate(messages) if m.get("tool_calls"))
    assert messages[assistant_idx + 1]["role"] == "tool"
    synthetic = messages[assistant_idx + 1]
    assert synthetic["tool_call_id"] == "call_1"
    assert synthetic["name"] == "web_fetch"
    assert "被中断" in str(synthetic["content"])


def test_complete_pair_covered_via_raw_history() -> None:
    """A full [assistant(tool_calls), tool] pair in raw history stays untouched.

    ``_build_loop_messages`` only carries ``user``/``assistant`` history items
    into the loop list, so the patch must learn covered ids from the raw
    history — otherwise a completed tool result would be mislabelled as
    interrupted.
    """
    pipeline = _pipeline()
    context = UnifiedContext(
        session_id="s1",
        user_message="next question",
        conversation_history=[
            {"role": "user", "content": "do it"},
            _assistant_with_call("call_1"),
            {"role": "tool", "tool_call_id": "call_1", "name": "web_fetch", "content": "ok"},
        ],
    )

    messages = pipeline._build_loop_messages(
        context=context,
        enabled_tools=[],
    )

    assert any(m.get("tool_calls") for m in messages)
    assert all("被中断" not in str(m.get("content", "")) for m in messages)


def test_complete_tool_calls_untouched() -> None:
    pipeline = _pipeline()
    messages = [
        _assistant_with_call("call_1"),
        {"role": "tool", "tool_call_id": "call_1", "name": "web_fetch", "content": "ok"},
    ]

    patched = pipeline._patch_dangling_tool_calls(messages)

    assert patched == messages
    assert all("被中断" not in str(m.get("content", "")) for m in patched)


def test_no_tool_calls_untouched() -> None:
    pipeline = _pipeline()
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        "bare-string-history-item",
    ]

    patched = pipeline._patch_dangling_tool_calls(messages)

    assert patched == messages
