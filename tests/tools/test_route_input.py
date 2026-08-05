import pytest

from deeptutor.tools.route_input_tool import (
    CATEGORIES,
    RouteInputTool,
    parse_route_result,
)


def test_categories_include_all_branches():
    assert {"task_start", "answer_submit", "question_confirm", "question_deep",
            "confuse", "off_topic", "greeting"} == set(CATEGORIES)


def test_parse_valid_result():
    r = parse_route_result(
        '{"category":"confuse","confidence":0.87,"clarify_options":["开始新练习","查看进度"],'
        '"short_reply_hint":"听起来你有点不确定？","flag_struggle":true}'
    )
    assert r["category"] == "confuse"
    assert r["confidence"] == pytest.approx(0.87)
    assert r["clarify_options"] == ["开始新练习", "查看进度"]
    assert r["flag_struggle"] is True


def test_parse_invalid_json_falls_back_to_confuse():
    r = parse_route_result("not-json")
    assert r["category"] == "confuse"
    assert r["confidence"] == 0.0
    assert r["clarify_options"] == []


def test_parse_unknown_category_falls_back():
    r = parse_route_result('{"category":"hacking"}')
    assert r["category"] == "confuse"


def test_parse_confidence_clamped_to_01():
    assert parse_route_result('{"category":"off_topic","confidence":5}')["confidence"] == 1.0
    assert parse_route_result('{"category":"off_topic","confidence":-2}')["confidence"] == 0.0


def test_parse_options_capped_and_deduped():
    r = parse_route_result('{"category":"confuse","clarify_options":["A","A","B","C","D","E"]}')
    assert r["clarify_options"] == ["A", "B", "C", "D"]


@pytest.mark.asyncio
async def test_execute_calls_llm_and_returns_route(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        return '{"category":"greeting","confidence":0.9}'

    monkeypatch.setattr(llm_mod, "complete", fake_complete)
    tool = RouteInputTool()
    result = await tool.execute(user_message="你好")
    assert result.success is True
    assert result.metadata["route"]["category"] == "greeting"


@pytest.mark.asyncio
async def test_execute_empty_message_fails():
    tool = RouteInputTool()
    result = await tool.execute(user_message="   ")
    assert result.success is False


@pytest.mark.asyncio
async def test_execute_llm_error_falls_back(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def broken_complete(prompt, system_prompt=None, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm_mod, "complete", broken_complete)
    tool = RouteInputTool()
    result = await tool.execute(user_message="hello")
    assert result.success is True
    assert result.metadata["route"]["category"] == "confuse"
