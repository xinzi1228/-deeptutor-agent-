from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from deeptutor.agents.chat.agentic_pipeline import AgenticChatPipeline
from deeptutor.tools.delegate_expert_tool import (
    EXPERT_IDS,
    DelegateExpertTool,
    load_expert_card,
)


def _llm_chunk(
    *,
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    usage: Any = None,
    finish_reason: str | None = None,
) -> SimpleNamespace:
    delta_fields: dict[str, Any] = {"content": content}
    if tool_calls is not None:
        delta_fields["tool_calls"] = [
            SimpleNamespace(
                index=tc.get("index", i),
                id=tc.get("id"),
                function=SimpleNamespace(
                    name=tc.get("name"),
                    arguments=tc.get("arguments"),
                ),
            )
            for i, tc in enumerate(tool_calls)
        ]
    else:
        delta_fields["tool_calls"] = None
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(**delta_fields),
                finish_reason=finish_reason,
            )
        ],
        usage=usage,
    )


async def _async_llm_stream(chunks: list[SimpleNamespace]):
    for chunk in chunks:
        yield chunk


class _ScriptedChatClient:
    def __init__(self, scripted: list[list[SimpleNamespace]]) -> None:
        self._script = list(scripted)
        self.call_count = 0
        self.calls: list[dict[str, Any]] = []

        class _Completions:
            def __init__(self, parent: _ScriptedChatClient) -> None:
                self.parent = parent

            async def create(self, **kwargs):
                self.parent.call_count += 1
                self.parent.calls.append(
                    {**kwargs, "messages": list(kwargs.get("messages") or [])}
                )
                if not self.parent._script:
                    raise RuntimeError("Scripted client exhausted")
                return _async_llm_stream(self.parent._script.pop(0))

        class _Chat:
            def __init__(self, parent: _ScriptedChatClient) -> None:
                self.completions = _Completions(parent)

        self.chat = _Chat(self)


class _Registry:
    def __init__(self) -> None:
        self.executed: list[dict[str, Any]] = []

    def deferred_tools(self):
        return []

    def build_prompt_text(self, _enabled, **_kwargs):
        return "- `kb_search` - Search the KB"

    def build_openai_schemas(self, _enabled):
        return [
            {
                "type": "function",
                "function": {
                    "name": "kb_search",
                    "description": "Search",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "annotation_check",
                    "description": "Check annotation",
                    "parameters": {
                        "type": "object",
                        "properties": {"task_id": {"type": "string"}},
                        "required": ["task_id"],
                    },
                },
            },
        ]

    async def execute(self, name: str, **kwargs):
        self.executed.append({"name": name, "kwargs": kwargs})
        return SimpleNamespace(
            content="tool answer",
            sources=[],
            metadata={"tool": name},
            success=True,
            terminate_turn=False,
            pause_for_user=None,
        )


@pytest.fixture(autouse=True)
def _fake_pipeline_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "deeptutor.agents.chat.agentic_pipeline.get_llm_config",
        lambda: SimpleNamespace(
            binding="openai",
            model="gpt-test",
            api_key="k",
            base_url="u",
            api_version=None,
            extra_headers={},
            reasoning_effort=None,
        ),
    )
    monkeypatch.setattr(
        "deeptutor.agents.chat.agentic_pipeline.get_tool_registry",
        lambda: _Registry(),
    )

    def _no_real_client(self):
        raise RuntimeError("tests must not call a real LLM client")

    monkeypatch.setattr(AgenticChatPipeline, "_build_openai_client", _no_real_client)


def test_expert_ids_include_teaching_and_visualization_specialists():
    assert set(EXPERT_IDS) == {
        "learning_planner", "task_guide", "grading_expert",
        "struggle_detective", "report_analyst", "session_steward",
        "chart_designer", "diagram_designer", "illustration_designer",
        "textbook_analyst", "file-analyst",
    }


def test_load_expert_card_grading():
    card = load_expert_card("grading_expert")
    assert "批改专家" in card
    assert "annotation_check" in card


def test_load_expert_card_missing_returns_empty():
    assert load_expert_card("nonexistent") == ""


@pytest.mark.asyncio
async def test_execute_delegates_to_llm(monkeypatch):
    import deeptutor.services.llm as llm_mod

    captured = {}

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        captured["system"] = system_prompt
        captured["user"] = prompt
        return "F1=0.83，建议 advance_with_caution。"

    monkeypatch.setattr(llm_mod, "complete", fake_complete)
    tool = DelegateExpertTool()
    result = await tool.execute(
        expert_id="grading_expert",
        brief="评测学生提交的 bbox 标注",
        task_data='{"f1": 0.83}',
    )
    assert result.success is True
    assert result.metadata["delegate"]["expert"] == "grading_expert"
    assert "F1=0.83" in result.content
    assert "批改专家" in captured["system"]  # 专家卡注入 system
    assert "评测学生提交的 bbox 标注" in captured["user"]


@pytest.mark.asyncio
async def test_execute_invalid_expert_fails():
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="hacker", brief="x")
    assert result.success is False


@pytest.mark.asyncio
async def test_textbook_expert_is_admin_only(monkeypatch):
    monkeypatch.setattr(
        "deeptutor.tools.delegate_expert_tool._is_admin_actor", lambda: False
    )
    result = await DelegateExpertTool().execute(
        expert_id="textbook_analyst", brief="提取教材候选"
    )
    assert result.success is False
    assert "只面向管理员" in result.content


@pytest.mark.asyncio
async def test_execute_empty_brief_fails():
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="   ")
    assert result.success is False


@pytest.mark.asyncio
async def test_execute_llm_error_fails(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def broken(prompt, system_prompt=None, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm_mod, "complete", broken)
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="x")
    assert result.success is False


@pytest.mark.asyncio
async def test_delegate_runs_pipeline(monkeypatch):
    client = _ScriptedChatClient(
        [
            [
                _llm_chunk(content="我来核对一下标注。"),
                _llm_chunk(
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "annotation_check",
                            "arguments": json.dumps({"task_id": "t-1"}),
                        }
                    ]
                ),
            ],
            [_llm_chunk(content="F1=0.83，建议 advance_with_caution。")],
        ]
    )
    monkeypatch.setattr(AgenticChatPipeline, "_build_openai_client", lambda self: client)
    monkeypatch.setattr(
        AgenticChatPipeline,
        "_compose_enabled_tools",
        lambda self, ctx: ["annotation_check"],
    )

    tool = DelegateExpertTool()
    result = await tool.execute(
        expert_id="grading_expert",
        brief="评测标注",
        task_data='{"f1": 0.83}',
    )

    assert result.success is True
    assert "F1=0.83" in result.content
    assert "grading_expert" in result.content
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_delegate_isolates_context(monkeypatch):
    from deeptutor.tools.delegate_expert_tool import EXPERT_TOOL_WHITELISTS

    captured: dict[str, Any] = {}

    async def fake_run(self, context, stream):
        captured["ctx"] = context

    monkeypatch.setattr(AgenticChatPipeline, "run", fake_run)

    tool = DelegateExpertTool()
    await tool.execute(expert_id="grading_expert", brief="评测标注", task_data='{"f1": 0.83}')

    ctx = captured["ctx"]
    assert ctx.conversation_history == []
    assert ctx.enabled_tools == []
    assert ctx.metadata["source"] == "delegate"
    assert ctx.metadata["expert"] == "grading_expert"
    assert ctx.metadata["_min_loop_rounds"] == 3
    assert ctx.metadata["mcp_tools_filter"] == []
    assert set(EXPERT_TOOL_WHITELISTS["grading_expert"]) == set(ctx.allowed_builtin_tools)
    banned = {"delegate_to_expert", "ask_user", "write_memory", "web_fetch", "github", "cron"}
    assert not banned.intersection(ctx.allowed_builtin_tools)
    assert "批改专家" in ctx.persona_context
    assert "你现在只处理这一次委派任务" in ctx.persona_context
    assert "评测标注" in ctx.user_message


def test_whitelist_per_expert():
    from deeptutor.agents._shared.tool_composition import ALWAYS_ON_TOOLS
    from deeptutor.tools.delegate_expert_tool import EXPERT_TOOL_WHITELISTS

    banned = {"delegate_to_expert", "ask_user", "write_memory", "web_fetch", "github", "cron"}
    always_on = set(ALWAYS_ON_TOOLS)
    assert len(ALWAYS_ON_TOOLS) >= 27
    assert set(EXPERT_TOOL_WHITELISTS) == set(EXPERT_IDS)
    # file-analyst is the documented exception: it reaches into the workspace
    # with read-only parsing builtins (read_file/exec) that are registered but
    # not always-on. Everything else must stay within the always-on surface.
    non_always_on_extras: dict[str, set[str]] = {
        "file-analyst": {"read_file", "exec"},
    }
    for expert_id, whitelist in EXPERT_TOOL_WHITELISTS.items():
        allowed = always_on | non_always_on_extras.get(expert_id, set())
        assert set(whitelist).issubset(allowed), f"{expert_id} 超出 always_on"
        assert not banned.intersection(whitelist), f"{expert_id} 含禁用工具"
        assert "write_learning_record" not in whitelist, (
            f"{expert_id} 不应直接写学习记录（学习记录只由总控落盘）"
        )
    log_decision_experts = {
        e for e, wl in EXPERT_TOOL_WHITELISTS.items() if "log_decision" in wl
    }
    assert log_decision_experts == {"grading_expert", "report_analyst", "session_steward"}


@pytest.mark.asyncio
async def test_fallback_to_complete(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        return "fallback 结论。"

    monkeypatch.setattr(llm_mod, "complete", fake_complete)

    def _boom(self, *args, **kwargs):
        raise RuntimeError("pipeline init failed")

    monkeypatch.setattr(AgenticChatPipeline, "__init__", _boom)

    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="评测标注")

    assert result.success is True
    assert "fallback 结论" in result.content
    assert result.metadata["delegate"]["expert"] == "grading_expert"


@pytest.mark.asyncio
async def test_delegate_times_out_falls_back(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def slow_run(self, context, stream):
        await asyncio.sleep(0.2)

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        return "timeout 后走 fallback 的结论。"

    monkeypatch.setattr(llm_mod, "complete", fake_complete)
    monkeypatch.setattr(AgenticChatPipeline, "run", slow_run)
    monkeypatch.setattr(
        "deeptutor.tools.delegate_expert_tool.DELEGATE_TIMEOUT_SECONDS", 0.05
    )

    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="评测标注")

    assert result.success is True
    assert "timeout 后走 fallback 的结论" in result.content
    assert result.metadata["delegate"]["expert"] == "grading_expert"


@pytest.mark.asyncio
async def test_delegate_emits_progress_via_event_sink(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_event_sink(event_type: str, message: str = "", **kwargs):
        calls.append((event_type, message))

    async def fake_run(self, context, stream):
        await asyncio.sleep(0.01)
        await stream.result({"response": "F1=0.83，建议 advance_with_caution。"})

    monkeypatch.setattr(AgenticChatPipeline, "run", fake_run)

    tool = DelegateExpertTool()
    result = await tool.execute(
        expert_id="grading_expert",
        brief="评测标注",
        task_data='{"f1": 0.83}',
        event_sink=fake_event_sink,
    )

    assert result.success is True
    assert len(calls) >= 2, f"expected >=2 progress calls, got {calls}"
    running_msgs = [m for _, m in calls if "分析中" in m or "运行" in m]
    done_msgs = [m for _, m in calls if "完成" in m]
    assert running_msgs, f"missing running progress: {calls}"
    assert done_msgs, f"missing done progress: {calls}"
    assert any("grading_expert" in m for _, m in calls)


@pytest.mark.asyncio
async def test_delegate_no_event_sink_still_works(monkeypatch):
    async def fake_run(self, context, stream):
        await asyncio.sleep(0.01)
        await stream.result({"response": "F1=0.83，建议 advance_with_caution。"})

    monkeypatch.setattr(AgenticChatPipeline, "run", fake_run)
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="评测标注")
    assert result.success is True
