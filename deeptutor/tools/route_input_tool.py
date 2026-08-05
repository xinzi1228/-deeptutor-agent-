"""RouteInputTool — classify user input intent and branch coach behaviour.

The coach calls this BEFORE answering: it returns a structured category so the
coach can branch (confuse -> ask_user clarify; off_topic -> short reply + pull
back; question_confirm -> answer directly; etc.). The LLM's JSON output is
parsed and validated by ``parse_route_result`` (a pure function, unit-testable
without an LLM).
"""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

CATEGORIES = (
    "task_start",
    "answer_submit",
    "question_confirm",
    "question_deep",
    "confuse",
    "off_topic",
    "greeting",
)

_FALLBACK: dict[str, Any] = {
    "category": "confuse",
    "confidence": 0.0,
    "clarify_options": [],
    "short_reply_hint": "",
    "flag_struggle": False,
    "requires_confirmation": False,
}


def parse_route_result(raw: str) -> dict[str, Any]:
    """Parse and validate the LLM's JSON classification; fall back to confuse."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return dict(_FALLBACK)
    if not isinstance(data, dict):
        return dict(_FALLBACK)
    category = str(data.get("category") or "").strip()
    if category not in CATEGORIES:
        category = _FALLBACK["category"]
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    confidence = max(0.0, min(1.0, float(confidence)))
    options = data.get("clarify_options")
    if not isinstance(options, list):
        options = []
    seen: list[str] = []
    for o in options:
        s = str(o).strip()
        if s and s not in seen:
            seen.append(s)
        if len(seen) >= 4:
            break
    return {
        "category": category,
        "confidence": confidence,
        "clarify_options": seen,
        "short_reply_hint": str(data.get("short_reply_hint") or "").strip(),
        "flag_struggle": bool(data.get("flag_struggle")),
        "requires_confirmation": bool(data.get("requires_confirmation")),
    }


def _build_prompt(message: str, recent_context: str) -> str:
    return (
        "Classify the student's latest message for an annotation-coach tutor.\n"
        "Choose EXACTLY ONE category:\n"
        "- task_start: wants to start/continue annotation practice\n"
        "- answer_submit: submitting annotation result / answer\n"
        "- question_confirm: one-line confirm-style question (e.g. \"X is right?\")\n"
        "- question_deep: asking about a knowledge point or standard\n"
        "- confuse: incomplete / vague input that needs clarification\n"
        "- off_topic: unrelated to annotation teaching\n"
        "- greeting: small talk / hello\n"
        "Return ONLY JSON:\n"
        '{"category":"<one of the above>","confidence":0.0-1.0,'
        '"clarify_options":["option1","option2"],"short_reply_hint":"<for off_topic/confuse, 1 short line>",'
        '"flag_struggle":false,"requires_confirmation":false}\n'
        "For confuse, give 2-4 clarify_options as candidate choices.\n\n"
        f"Recent context:\n{recent_context}\n\n"
        f"Student message:\n{message}"
    )


class RouteInputTool(BaseTool):
    """Classify user input intent to route the coach's response."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="route_input",
            description=(
                "Classify the user's input intent BEFORE responding. Returns a structured "
                "category: task_start / answer_submit / question_confirm / question_deep / "
                "confuse / off_topic / greeting. For confuse it also returns candidate "
                "clarify_options to present via ask_user. For off_topic it returns a short "
                "reply hint to pull the learner back to annotation practice."
            ),
            parameters=[
                ToolParameter(
                    name="user_message",
                    type="string",
                    description="The user's latest message.",
                    required=True,
                ),
                ToolParameter(
                    name="recent_context",
                    type="string",
                    description="Optional recent 1-2 turns of context (max ~2000 chars).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        message = str(kwargs.get("user_message") or "").strip()
        if not message:
            return ToolResult(content="Error: user_message is required.", success=False)
        recent_context = str(kwargs.get("recent_context") or "")[:2000]
        prompt = _build_prompt(message, recent_context)
        try:
            from deeptutor.services.llm import complete

            raw = await complete(prompt, system_prompt="You are a teaching-assistant intent router.")
        except Exception:
            raw = ""
        route = parse_route_result(raw)
        content = (
            f"Input routed as: {route['category']} "
            f"(confidence={route['confidence']:.2f})."
        )
        return ToolResult(content=content, metadata={"route": route})


__all__ = ["RouteInputTool", "parse_route_result", "CATEGORIES"]
