import pytest

from deeptutor.tools.delegate_expert_tool import (
    EXPERT_IDS,
    DelegateExpertTool,
    load_expert_card,
)


def test_expert_ids_six():
    assert set(EXPERT_IDS) == {
        "learning_planner", "task_guide", "grading_expert",
        "struggle_detective", "report_analyst", "session_steward",
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
