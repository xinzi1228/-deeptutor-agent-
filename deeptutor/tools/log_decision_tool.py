"""Log coach decision tool — lumen-style decision audit trail.

Records WHY the coach recommended a task / judged readiness / chose a route,
so the learner (or a teacher auditing the system) can trace any decision back
to its evidence. Surfaces in the personal-centre "why" panel.
"""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints

READINESS_CHOICES = (
    "advance",
    "advance_with_caution",
    "review_first",
    "step_down",
    "diagnose_again",
    "more_practice",
)


class LogDecisionTool(BaseTool):
    """Record a coaching decision with its rationale for audit."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="log_decision",
            description=(
                "Record a coaching decision with its rationale for the audit trail. "
                "Call AFTER you recommend a task, judge readiness, or choose a route — "
                "capture WHAT you decided and WHY (evidence). Shown to the learner in the "
                "progress 'why' panel so every recommendation is traceable."
            ),
            parameters=[
                ToolParameter(
                    name="kind",
                    type="string",
                    description=(
                        "Decision kind: 'task_recommendation' | 'readiness_judgment' | 'route_choice' "
                        "| 'struggle_intervention'."
                    ),
                    enum=["task_recommendation", "readiness_judgment", "route_choice", "struggle_intervention"],
                ),
                ToolParameter(
                    name="target",
                    type="string",
                    description="The thing decided on, e.g. task_id='task4' or readiness='advance'.",
                ),
                ToolParameter(
                    name="rationale",
                    type="string",
                    description="One-sentence WHY — the evidence behind the decision.",
                ),
                ToolParameter(
                    name="evidence",
                    type="string",
                    description="Optional JSON list of evidence items (e.g. [{f1, error_pattern}]).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.learning_records import LearningRecordStore

        kind = str(kwargs.get("kind") or "").strip()
        target = str(kwargs.get("target") or "").strip()
        rationale = str(kwargs.get("rationale") or "").strip()
        evidence_raw = kwargs.get("evidence")

        if kind not in ("task_recommendation", "readiness_judgment", "route_choice", "struggle_intervention"):
            return ToolResult(
                content="Error: kind must be task_recommendation | readiness_judgment | route_choice | struggle_intervention.",
                success=False,
            )
        if not target or not rationale:
            return ToolResult(content="Error: target and rationale are required.", success=False)

        evidence: Any = None
        if evidence_raw:
            if isinstance(evidence_raw, str):
                try:
                    evidence = json.loads(evidence_raw)
                except json.JSONDecodeError:
                    evidence = evidence_raw
            else:
                evidence = evidence_raw

        decision = {
            "kind": kind,
            "target": target,
            "rationale": rationale,
            "evidence": evidence,
        }
        try:
            await LearningRecordStore().append_decision(decision)
        except Exception as exc:
            return ToolResult(content=f"Error: failed to log decision — {exc}", success=False)

        return ToolResult(
            content=f"Decision logged: {kind} → {target}. 理由: {rationale}",
            metadata={"kind": kind, "target": target},
        )

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


__all__ = ["LogDecisionTool", "READINESS_CHOICES"]
