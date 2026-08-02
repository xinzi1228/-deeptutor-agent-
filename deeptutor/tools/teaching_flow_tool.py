"""TeachingFlowTool — coach tool to query/advance/reset the teaching flow engine."""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints


class TeachingFlowTool(BaseTool):
    """Query / advance / reset the task-level teaching flow state machine."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="teaching_flow",
            description=(
                "Query or advance the current teaching-flow step for the active task "
                "(select_task -> show_task -> waiting -> evaluate -> feedback -> record). "
                "Call to know where you are in the pipeline, to advance a step after it "
                "completes, or to reset for a new task. Returns the current step + next "
                "action hint so you can stay on protocol."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="'query' (default) returns current step; 'advance' marks a step done; 'reset' clears state.",
                    required=False,
                    enum=["query", "advance", "reset"],
                    default="query",
                ),
                ToolParameter(
                    name="step",
                    type="string",
                    description="Step to advance when action=advance (select_task/show_task/waiting/evaluate/feedback/record).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "query")
        step = kwargs.get("step")
        engine = _build_engine()

        try:
            if action == "advance":
                if not step:
                    return ToolResult(content="action=advance 需要指定 step。", success=False)
                state = engine.advance(step)
                return ToolResult(content=_format_state(state), metadata={"state": state})
            if action == "reset":
                state = engine.reset()
                return ToolResult(content=_format_state(state), metadata={"state": state})
            state = engine.get_state()
            return ToolResult(content=_format_state(state), metadata={"state": state})
        except ValueError as e:
            return ToolResult(content=f"teaching_flow 参数错误: {e}", success=False)

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


# ------------------------------------------------------------ dependencies

def _build_engine() -> Any:
    from deeptutor.services.teaching_flow import TeachingFlowEngine

    return TeachingFlowEngine()


def _format_state(state: dict) -> str:
    task = state.get("task_id") or "（未开始）"
    step = state.get("current_step") or "（完成）"
    blocked = state.get("blocked")
    lines = ["## 教学流程状态\n", f"当前任务: {task}", f"当前步骤: {step}"]
    if blocked:
        lines.append(f"阻塞: {blocked.get('reason', '')}")
        lines.append(f"建议: {blocked.get('next_action', '')}")
    return "\n".join(lines)


__all__ = ["TeachingFlowTool"]
