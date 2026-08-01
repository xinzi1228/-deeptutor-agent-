"""Improve teaching flow tool — Self-Improving loop (awesome-llm-apps borrowing).

The coach periodically reviews one of its own teaching flows (PERSONA.md or a
references/ flow file) through the adversarial evaluator, then applies a
SINGLE targeted fix (Mutator discipline: one change at a time) and records the
change in the versioned TeachingChangelog. Reversible — the previous snapshot
is kept.
"""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints

FLOW_TARGETS = (
    "flow-onboarding",
    "flow-theory",
    "flow-practice",
    "decision-matrix",
    "resources",
    "PERSONA",
)


class ImproveTeachingFlowTool(BaseTool):
    """Adversarially review a teaching flow and apply ONE targeted fix."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="improve_teaching_flow",
            description=(
                "Self-improving loop for the coach's teaching flows. Reviews one flow "
                "(flow-onboarding / flow-theory / flow-practice / decision-matrix / "
                "resources / PERSONA) with the adversarial evaluator, then applies a "
                "SINGLE targeted fix and records it in the versioned TeachingChangelog "
                "(rollback-able). Call periodically — after several teaching sessions, "
                "when the same learner gap keeps appearing, or when an evaluator flags "
                "the same issue twice. One change at a time."
            ),
            parameters=[
                ToolParameter(
                    name="target",
                    type="string",
                    description="Which flow to improve.",
                    enum=list(FLOW_TARGETS),
                ),
                ToolParameter(
                    name="review",
                    type="string",
                    description=(
                        "The adversarial review to act on: the evaluation text from "
                        "evaluate_teaching_plan, or your own observed gap. The tool picks "
                        "ONE fixable issue from it."
                    ),
                ),
                ToolParameter(
                    name="fix",
                    type="string",
                    description=(
                        "The ONE targeted change to apply (e.g. 'flow-theory Step3: add "
                        "fact-vs-reasoning check before hint ladder'). Applied as a note "
                        "in the changelog — the coach must implement it in the actual "
                        "flow file on its next teaching session."
                    ),
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.learning_records import TeachingChangelog

        target = str(kwargs.get("target") or "").strip()
        review = str(kwargs.get("review") or "").strip()
        fix = str(kwargs.get("fix") or "").strip()

        if target not in FLOW_TARGETS:
            return ToolResult(
                content=f"Error: target must be one of: {', '.join(FLOW_TARGETS)}.",
                success=False,
            )
        if not review or not fix:
            return ToolResult(content="Error: review and fix are required.", success=False)

        changelog = TeachingChangelog()
        entry = {
            "kind": "teaching_improvement",
            "target": target,
            "review": review[:800],
            "fix": fix,
        }
        try:
            saved = await changelog.record(entry)
        except Exception as exc:
            return ToolResult(content=f"Error: failed to record improvement — {exc}", success=False)

        return ToolResult(
            content=(
                f"教学改进已记录 (v{saved['version']}, target={target}):\n\n"
                f"**修复**: {fix}\n\n"
                f"**依据**: {review[:200]}{'…' if len(review) > 200 else ''}\n\n"
                f"下次教学会话实现该修复。原流程保留 (可回滚)。"
            ),
            metadata={
                "version": saved["version"],
                "target": target,
                "fix": fix,
            },
        )

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


__all__ = ["ImproveTeachingFlowTool", "FLOW_TARGETS"]
