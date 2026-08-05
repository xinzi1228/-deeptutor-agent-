import pytest

from deeptutor.tools.verify_output_tool import VerifyOutputTool, parse_verify_result


def test_parse_valid_pass():
    r = parse_verify_result(
        '{"fabrication_leak":false,"role_drift":false,"ai_label_missing":false,'
        '"evidence_missing":[],"pass":true,"revision_advice":""}'
    )
    assert r["pass"] is True
    assert r["fabrication_leak"] is False
    assert r["evidence_missing"] == []


def test_parse_detects_issues():
    r = parse_verify_result(
        '{"fabrication_leak":true,"role_drift":false,"ai_label_missing":true,'
        '"evidence_missing":["目标检测遮挡阈值50%无规范依据"],"pass":false,'
        '"revision_advice":"请标注来源或改为通用建议"}'
    )
    assert r["pass"] is False
    assert r["fabrication_leak"] is True
    assert r["evidence_missing"] == ["目标检测遮挡阈值50%无规范依据"]
    assert r["revision_advice"] == "请标注来源或改为通用建议"


def test_parse_invalid_json_defaults_pass():
    r = parse_verify_result("not-json")
    assert r["pass"] is True
    assert r["fabrication_leak"] is False
    assert r["evidence_missing"] == []


def test_parse_explicit_pass_false_wins():
    r = parse_verify_result('{"pass":false}')
    assert r["pass"] is False


def test_parse_evidence_capped():
    r = parse_verify_result('{"evidence_missing":["a","b","c","d","e","f","g"]}')
    assert len(r["evidence_missing"]) == 6


@pytest.mark.asyncio
async def test_execute_calls_llm_and_returns_verdict(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        return '{"fabrication_leak":false,"pass":true}'

    monkeypatch.setattr(llm_mod, "complete", fake_complete)
    tool = VerifyOutputTool()
    result = await tool.execute(draft_answer="依据 GB/T 41867，遮挡目标需标注。")
    assert result.success is True
    assert result.metadata["verify"]["pass"] is True


@pytest.mark.asyncio
async def test_execute_empty_draft_fails():
    tool = VerifyOutputTool()
    result = await tool.execute(draft_answer="   ")
    assert result.success is False


@pytest.mark.asyncio
async def test_execute_llm_error_defaults_pass(monkeypatch):
    import deeptutor.services.llm as llm_mod

    async def broken_complete(prompt, system_prompt=None, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm_mod, "complete", broken_complete)
    tool = VerifyOutputTool()
    result = await tool.execute(draft_answer="hello")
    assert result.success is True
    assert result.metadata["verify"]["pass"] is True
