"""VerifyOutputTool — coach pre-output quality self-check.

The coach calls this BEFORE emitting a high-risk answer (grading conclusions,
standard citations, knowledge assertions). The LLM audits the draft and returns
a structured verdict; ``parse_verify_result`` validates it with a conservative
PASS fallback (never over-block). If issues are found, the coach must revise
per ``revision_advice`` and re-emit.
"""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

_FALLBACK: dict[str, Any] = {
    "fabrication_leak": False,
    "role_drift": False,
    "ai_label_missing": False,
    "evidence_missing": [],
    "pass": True,
    "revision_advice": "",
}


def parse_verify_result(raw: str) -> dict[str, Any]:
    """Parse and validate the LLM's audit verdict; conservative PASS fallback."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return dict(_FALLBACK)
    if not isinstance(data, dict):
        return dict(_FALLBACK)
    fabrication = bool(data.get("fabrication_leak"))
    role = bool(data.get("role_drift"))
    label = bool(data.get("ai_label_missing"))
    evidence = data.get("evidence_missing")
    if not isinstance(evidence, list):
        evidence = []
    evidence = [str(e) for e in evidence if str(e).strip()][:6]
    issues = fabrication or role or label or bool(evidence)
    # 显式 pass=false 优先；未显式给 pass 时按 issues 推断
    if "pass" in data:
        passed = bool(data.get("pass"))
    else:
        passed = not issues
    return {
        "fabrication_leak": fabrication,
        "role_drift": role,
        "ai_label_missing": label,
        "evidence_missing": evidence,
        "pass": passed,
        "revision_advice": str(data.get("revision_advice") or "").strip(),
    }


def _build_prompt(draft: str, claims: str) -> str:
    return (
        "You are a strict output-quality auditor for an annotation-coach tutor.\n"
        "Audit the draft answer below. Flag:\n"
        "- fabrication_leak: invented standards/specs/scores/sources not in the knowledge base\n"
        "- role_drift: answer leaves the annotation-coach role\n"
        "- ai_label_missing: lacks a required AI-generated content label\n"
        "- evidence_missing: knowledge assertions (standards like GB/T, grading conclusions) "
        "without a citation marker like 〔规范: 文档§章节〕\n"
        "Return ONLY JSON:\n"
        '{"fabrication_leak":false,"role_drift":false,"ai_label_missing":false,'
        '"evidence_missing":["<specific missing citation>"],"pass":true|false,'
        '"revision_advice":"<short fix instruction if not pass, else empty>"}\n\n'
        f"Optional claims to verify:\n{claims}\n\n"
        f"Draft answer:\n{draft}"
    )


class VerifyOutputTool(BaseTool):
    """Audit a draft answer for fabrication/role/evidence issues before emitting."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="verify_output",
            description=(
                "Audit a draft answer BEFORE emitting a high-risk response (grading "
                "conclusion, standard citation, knowledge assertion). Returns a verdict: "
                "pass=true to emit, or issues (fabrication_leak / role_drift / "
                "ai_label_missing / evidence_missing) + revision_advice to fix and re-emit."
            ),
            parameters=[
                ToolParameter(
                    name="draft_answer",
                    type="string",
                    description="The draft answer text to audit.",
                    required=True,
                ),
                ToolParameter(
                    name="claims",
                    type="string",
                    description="Optional key assertions to verify (one per line).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        draft = str(kwargs.get("draft_answer") or "").strip()
        if not draft:
            return ToolResult(content="Error: draft_answer is required.", success=False)
        claims = str(kwargs.get("claims") or "").strip()
        prompt = _build_prompt(draft, claims)
        try:
            from deeptutor.services.llm import complete

            raw = await complete(prompt, system_prompt="You are a strict output quality auditor.")
        except Exception:
            raw = ""
        verdict = parse_verify_result(raw)
        if verdict["pass"]:
            content = "Verify PASS: 未发现编造/越界/缺依据问题，可输出。"
        else:
            issues = []
            if verdict["fabrication_leak"]:
                issues.append("编造来源")
            if verdict["role_drift"]:
                issues.append("角色漂移")
            if verdict["ai_label_missing"]:
                issues.append("缺 AI 标识")
            for e in verdict["evidence_missing"]:
                issues.append(f"缺依据: {e}")
            content = f"Verify ISSUES: {'; '.join(issues)}。{verdict['revision_advice']}"
        return ToolResult(content=content, metadata={"verify": verdict})


__all__ = ["VerifyOutputTool", "parse_verify_result"]
