"""DelegateExpertTool — delegate a sub-task to a specialist expert.

The master agent hands a self-contained brief + task data to one of the six
expert cards. The expert runs as an isolated LLM turn (system = expert card,
user = brief), NEVER inheriting the master's full conversation history
(context isolation — dispatching-parallel-agents principle).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

EXPERTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "skills" / "builtin" / "annotation-coach-flows" / "references" / "experts"
)

EXPERT_IDS: tuple[str, ...] = (
    "learning_planner",
    "task_guide",
    "grading_expert",
    "struggle_detective",
    "report_analyst",
    "session_steward",
)


def load_expert_card(expert_id: str) -> str:
    """Load an expert card markdown (frontmatter + body). Empty if missing."""
    md = EXPERTS_DIR / f"{expert_id}.md"
    if not md.exists():
        return ""
    return md.read_text(encoding="utf-8")


class DelegateExpertTool(BaseTool):
    """Delegate a sub-task to a specialist expert with isolated context."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="delegate_to_expert",
            description=(
                "Delegate a focused sub-task to a specialist expert (6 experts: "
                "learning_planner / task_guide / grading_expert / struggle_detective / "
                "report_analyst / session_steward). Provide a SELF-CONTAINED brief and "
                "task_data — the expert does NOT see the conversation history. The expert "
                "returns its conclusion for the master to synthesize."
            ),
            parameters=[
                ToolParameter(
                    name="expert_id",
                    type="string",
                    description="Expert to delegate to.",
                    required=True,
                    enum=list(EXPERT_IDS),
                ),
                ToolParameter(
                    name="brief",
                    type="string",
                    description="Self-contained task description (no conversation context needed).",
                    required=True,
                ),
                ToolParameter(
                    name="task_data",
                    type="string",
                    description="Optional JSON data the expert needs (e.g. grading results).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        expert_id = str(kwargs.get("expert_id") or "").strip()
        if expert_id not in EXPERT_IDS:
            return ToolResult(
                content=f"Error: expert_id 必须是 {', '.join(EXPERT_IDS)} 之一。",
                success=False,
            )
        brief = str(kwargs.get("brief") or "").strip()
        if not brief:
            return ToolResult(content="Error: brief 必填（自包含任务描述）。", success=False)
        task_data = str(kwargs.get("task_data") or "").strip()
        card = load_expert_card(expert_id)
        if not card:
            return ToolResult(content=f"Error: 找不到专家卡 {expert_id}。", success=False)
        system = (
            f"{card}\n\n"
            "你现在只处理这一次委派任务，不进入完整对话。"
            "按你的专家规则输出结构化结论给总控。"
        )
        user = f"委派任务：{brief}\n\n"
        if task_data:
            user += f"任务数据：\n{task_data}\n\n"
        user += "请输出你的结论（简洁、可被总控直接采用）。"
        try:
            from deeptutor.services.llm import complete

            raw = await complete(user, system_prompt=system)
        except Exception as e:
            return ToolResult(content=f"专家 {expert_id} 调用失败: {e}", success=False)
        content = f"专家 {expert_id} 结论：\n{raw}"
        return ToolResult(
            content=content,
            metadata={"delegate": {"expert": expert_id, "result": raw}},
        )


__all__ = ["DelegateExpertTool", "load_expert_card", "EXPERT_IDS"]
