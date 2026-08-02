"""TeachingFlowTool — coach tool to query/advance/reset the teaching flow engine."""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints

VALID_ACTIONS = ("query", "advance", "reset", "start_task", "block")


class TeachingFlowTool(BaseTool):
    """Query / advance / reset / start / block the task-level teaching flow state machine."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="teaching_flow",
            description=(
                "Query or advance the current teaching-flow step for the active task "
                "(select_task -> show_task -> waiting -> evaluate -> feedback -> record). "
                "Call to know where you are in the pipeline, to advance a step after it "
                "completes, to reset for a new task, to start a task, or to block a step "
                "that cannot proceed. Returns the current step + next action hint so you "
                "can stay on protocol."
            ),
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description=(
                        "'query' (default) returns current step; 'advance' marks a step done; "
                        "'reset' clears state; 'start_task' begins a new task; 'block' marks a "
                        "step blocked with a reason."
                    ),
                    required=False,
                    enum=list(VALID_ACTIONS),
                    default="query",
                ),
                ToolParameter(
                    name="step",
                    type="string",
                    description="Step to advance or block (select_task/show_task/waiting/evaluate/feedback/record).",
                    required=False,
                ),
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="Task id to start when action=start_task.",
                    required=False,
                ),
                ToolParameter(
                    name="reason",
                    type="string",
                    description="Why the step is blocked when action=block.",
                    required=False,
                ),
                ToolParameter(
                    name="next_action",
                    type="string",
                    description="Suggested next action for the coach when action=block.",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "query")
        engine = _build_engine()

        try:
            if action not in VALID_ACTIONS:
                return ToolResult(
                    content=(
                        f"teaching_flow action 必须是 {'/'.join(VALID_ACTIONS)} 之一，"
                        f"收到: {action!r}。"
                    ),
                    success=False,
                )
            if action == "advance":
                step = kwargs.get("step")
                if not step:
                    return ToolResult(content="action=advance 需要指定 step。", success=False)
                state = engine.advance(step)
            elif action == "reset":
                state = engine.reset()
            elif action == "start_task":
                task_id = kwargs.get("task_id")
                if not task_id:
                    return ToolResult(content="action=start_task 需要指定 task_id。", success=False)
                state = engine.start_task(task_id)
            elif action == "block":
                step = kwargs.get("step")
                if not step:
                    return ToolResult(content="action=block 需要指定 step。", success=False)
                state = engine.block(
                    step,
                    reason=str(kwargs.get("reason") or ""),
                    next_action=str(kwargs.get("next_action") or ""),
                )
            else:  # query
                state = engine.get_state()
            return ToolResult(content=_render_state(engine, state), metadata={"state": state})
        except (ValueError, OSError) as e:
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


def _render_state(engine: Any, state: dict) -> str:
    hint = engine.next_step_hint() if not state.get("blocked") else None
    return _format_state(state, hint=hint)


def _format_state(state: dict, *, hint: str | None = None) -> str:
    task = state.get("task_id") or "（未开始）"
    step = state.get("current_step") or "（完成）"
    blocked = state.get("blocked")
    lines = ["## 教学流程状态", f"当前任务: {task}", f"当前步骤: {step}"]
    if blocked:
        lines.append(f"阻塞: {blocked.get('reason', '')}")
        lines.append(f"建议: {blocked.get('next_action', '')}")
    elif hint:
        lines.append(f"下一步: {hint}")
    return "\n".join(lines)


__all__ = ["TeachingFlowTool"]
