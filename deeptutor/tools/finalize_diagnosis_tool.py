"""Finalize diagnosis tool — persist the Phase-0 brief + build the course plan.

After the coach completes the onboarding diagnosis (motivation captured, level
diagnosed, mode selected), this tool materialises the structured brief and the
deterministic course plan so the progress dashboard and next-session resume
have something to show. Regression found the coach rarely triggered brief/plan
build on its own — this gives it a single explicit action.
"""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints

MODE_CHOICES = ("Zero-Base", "Standard", "Advanced")
GOAL_CHOICES = ("job", "cert", "course", "interest")


class FinalizeDiagnosisTool(BaseTool):
    """Persist the diagnosis brief and build the course plan."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="finalize_diagnosis",
            description=(
                "Materialise the completed Phase-0 diagnosis: save the structured "
                "learning brief and build the deterministic 4-module course plan. "
                "Call AFTER you finish the onboarding diagnosis (level + teaching "
                "mode chosen) and BEFORE presenting the route. Do NOT skip — without "
                "it the progress dashboard has no course to show."
            ),
            parameters=[
                ToolParameter(
                    name="goal_type",
                    type="string",
                    description="Learner goal: job | cert | course | interest.",
                    enum=list(GOAL_CHOICES),
                ),
                ToolParameter(
                    name="teaching_mode",
                    type="string",
                    description="Diagnosed teaching mode.",
                    enum=list(MODE_CHOICES),
                ),
                ToolParameter(
                    name="diagnosed_level",
                    type="string",
                    description="Diagnosed level, e.g. zero_base / standard / advanced.",
                    required=False,
                ),
                ToolParameter(
                    name="mission",
                    type="string",
                    description="The learner's own words for why they are learning.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.services.course_plan import rebuild
        from deeptutor.services.learning_records import LearningRecordStore

        goal_type = str(kwargs.get("goal_type") or "interest").strip()
        teaching_mode = str(kwargs.get("teaching_mode") or "Standard").strip()
        diagnosed_level = str(kwargs.get("diagnosed_level") or "").strip()
        mission = str(kwargs.get("mission") or "").strip()

        if teaching_mode not in MODE_CHOICES:
            return ToolResult(
                content=f"Error: teaching_mode must be one of {', '.join(MODE_CHOICES)}.",
                success=False,
            )
        if goal_type not in GOAL_CHOICES:
            return ToolResult(
                content=f"Error: goal_type must be one of {', '.join(GOAL_CHOICES)}.",
                success=False,
            )

        store = LearningRecordStore()
        brief = {
            "goal": mission,
            "goal_type": goal_type,
            "diagnosed_level": diagnosed_level,
            "teaching_mode": teaching_mode,
        }
        try:
            store.save_brief(brief)
            plan = rebuild(force=True)
        except Exception as exc:
            return ToolResult(content=f"Error: failed to finalize diagnosis — {exc}", success=False)

        modules = [m.get("name") for m in (plan or {}).get("modules", [])]

        from deeptutor.tools.chart_cards import progress_chart

        chart = progress_chart(
            completed=0,
            total=len(modules),
            modules=[{"name": m.get("name", ""), "done": 0, "total": 1} for m in (plan or {}).get("modules", [])],
        )
        return ToolResult(
            content=(
                f"诊断已落盘 (mode={teaching_mode}, goal={goal_type}).\n"
                f"课程计划已生成: {', '.join(modules)}"
            ),
            metadata={
                "brief_saved": True,
                "teaching_mode": teaching_mode,
                "modules": modules,
                "chart": chart,
            },
        )

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


__all__ = ["FinalizeDiagnosisTool"]
