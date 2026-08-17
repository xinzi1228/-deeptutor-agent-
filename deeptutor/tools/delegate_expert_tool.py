"""DelegateExpertTool — delegate a sub-task to a specialist expert.

The master agent hands a self-contained brief + task data to one specialist
expert cards. The expert runs as an isolated AgentLoop (≤5 rounds) with a
restricted per-expert tool whitelist (专人专事) — it NEVER inherits the
master's conversation history (context isolation — dispatching-parallel-agents
principle). If the pipeline cannot be constructed or fails, it falls back to a
single isolated LLM turn (system = expert card, user = brief) so the tool
always remains usable.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

# Upper bound for one delegated expert pipeline run. If the expert's isolated
# AgentLoop does not finish within this window, the tool degrades to a single
# isolated LLM turn (the ``complete()`` fallback) so the master is never left
# waiting forever on a stuck expert.
DELEGATE_TIMEOUT_SECONDS = 60

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
    "chart_designer",
    "diagram_designer",
    "illustration_designer",
    "textbook_analyst",
    "file-analyst",
)

# Every whitelist is a subset of the always-on tool set (ALWAYS_ON_TOOLS in
# deeptutor.agents._shared.tool_composition) and deliberately excludes the
# shared/system tools everywhere to prevent recursion / blocking / pollution:
# delegate_to_expert, ask_user, write_memory, web_fetch, github, cron.
# The one documented exception is file-analyst, which additionally reaches
# read-only workspace parsing builtins (read_file / exec) — registered tools
# that are not always-on but are safe (read-only / sandboxed).
EXPERT_TOOL_WHITELISTS: dict[str, tuple[str, ...]] = {
    "learning_planner": (
        "competency_map",
        "ability_radar",
        "get_annotation_task",
        "kb_search",
        "graph_query",
        "render_ui",
    ),
    "task_guide": (
        "get_annotation_task",
        "kb_search",
        "annotation_check",
        "render_ui",
    ),
    "grading_expert": (
        "annotation_check",
        "get_annotation_task",
        "kb_search",
        "graph_query",
        "log_decision",
        "render_ui",
    ),
    "struggle_detective": (
        "struggle_detect",
        "ability_radar",
        "get_annotation_task",
        "kb_search",
        "graph_query",
        "render_ui",
    ),
    "report_analyst": (
        "competency_map",
        "ability_radar",
        "graph_query",
        "kb_search",
        "log_decision",
        "render_ui",
    ),
    "session_steward": (
        "log_decision",
        "get_annotation_task",
        "graph_query",
        "render_ui",
    ),
    "chart_designer": ("read_learning_chart_data", "create_visualization"),
    "diagram_designer": ("create_visualization",),
    # Image generation remains a user-configured, user-toggleable capability.
    # This specialist only produces a safe prompt; the master invokes imagegen.
    "illustration_designer": (),
    # Admin-only content-governance worker. The tool itself enforces the
    # structured-textbook boundary and can only create review candidates.
    "textbook_analyst": ("textbook_candidate",),
    # 文件解析专家：只读工作区文件（read_file/exec 是安全的内置工具，非共享/系统工具）。
    "file-analyst": (
        "read_file",
        "exec",
        "kb_search",
    ),
}


def load_expert_card(expert_id: str) -> str:
    """Load an expert card markdown (frontmatter + body). Empty if missing."""
    md = EXPERTS_DIR / f"{expert_id}.md"
    if not md.exists():
        return ""
    return md.read_text(encoding="utf-8")


def _is_admin_actor() -> bool:
    """Resolve the active role lazily so tool-registry startup stays acyclic."""
    try:
        from deeptutor.multi_user.context import get_current_user

        return bool(get_current_user().is_admin)
    except Exception:
        return False


def _build_messages(expert_id: str, card: str, brief: str, task_data: str) -> tuple[str, str]:
    """Build the isolated persona/system + user prompt (shared by both paths)."""
    system = (
        f"{card}\n\n"
        "你现在只处理这一次委派任务，不进入完整对话。"
        "按你的专家规则输出结构化结论给总控。"
    )
    user = f"委派任务：{brief}\n\n"
    if task_data:
        user += f"任务数据：\n{task_data}\n\n"
    user += "请输出你的结论（简洁、可被总控直接采用）。"
    return system, user


class DelegateExpertTool(BaseTool):
    """Delegate a sub-task to a specialist expert with isolated context."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="delegate_to_expert",
            description=(
                "Delegate a focused sub-task to a specialist expert (11 experts: "
                "learning_planner / task_guide / grading_expert / struggle_detective / "
                "report_analyst / session_steward / chart_designer / diagram_designer / "
                "illustration_designer / textbook_analyst / file-analyst). The expert runs as an isolated "
                "AgentLoop (≤5 rounds) with a restricted tool whitelist (专人专事) and "
                "does NOT inherit the conversation history. Provide a SELF-CONTAINED "
                "brief + task_data. The expert returns its conclusion for the master "
                "to synthesize. 专家不直接写学习记录，结论由总控统一落盘。"
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
        if expert_id == "textbook_analyst" and not _is_admin_actor():
            return ToolResult(
                content="Error: 教材分析专家只面向管理员内容治理工作台。",
                success=False,
            )
        brief = str(kwargs.get("brief") or "").strip()
        if not brief:
            return ToolResult(content="Error: brief 必填（自包含任务描述）。", success=False)
        task_data = str(kwargs.get("task_data") or "").strip()
        card = load_expert_card(expert_id)
        if not card:
            return ToolResult(content=f"Error: 找不到专家卡 {expert_id}。", success=False)

        system, user = _build_messages(expert_id, card, brief, task_data)

        event_sink = kwargs.get("event_sink")

        async def _report(stage_text: str) -> None:
            if event_sink is None:
                return
            try:
                await event_sink("tool_log", f"专家 {expert_id} {stage_text}…")
            except Exception:
                logger.debug("delegate progress event_sink failed", exc_info=True)

        # Main path: isolated AgentLoop with a restricted per-expert tool
        # whitelist. Lazy imports avoid a circular import at module load.
        try:
            import uuid

            from deeptutor.agents.chat.agentic_pipeline import AgenticChatPipeline
            from deeptutor.core.context import UnifiedContext
            from deeptutor.core.stream import StreamEventType
            from deeptutor.core.stream_bus import StreamBus

            ctx = UnifiedContext(
                session_id=f"delegate-{expert_id}-{uuid.uuid4().hex[:8]}",
                user_message=user,
                conversation_history=[],  # 绝不继承总控历史（上下文隔离）
                enabled_tools=[],  # 杀掉用户开关层
                allowed_builtin_tools=list(EXPERT_TOOL_WHITELISTS[expert_id]),
                language="zh",
                persona_context=system,
                metadata={
                    "source": "delegate",
                    "expert": expert_id,
                    "_min_loop_rounds": 3,
                    "mcp_tools_filter": [],  # 封闭 deferred/MCP 白名单绕过（专人专事）
                },
            )
            await _report("分析中")
            pipeline = AgenticChatPipeline(
                language="zh", max_rounds=5, temperature=0.2, max_tokens=2000
            )
            bus = StreamBus()
            try:
                await asyncio.wait_for(
                    pipeline.run(ctx, bus), timeout=DELEGATE_TIMEOUT_SECONDS
                )
            finally:
                await bus.close()
            final = ""
            async for event in bus.subscribe():
                if event.type == StreamEventType.RESULT:
                    response = (event.metadata or {}).get("response")
                    if response:
                        final = str(response)
            if not final.strip():
                return ToolResult(
                    content=f"专家 {expert_id} 未产出结构化结论，请重新委派。",
                    success=False,
                )
            await _report("分析完成")
            content = f"专家 {expert_id} 结论：\n{final}"
            return ToolResult(
                content=content,
                metadata={"delegate": {"expert": expert_id, "result": final}},
            )
        except Exception as exc:
            # Fallback: single isolated complete() call so the tool always works.
            # A delegate timeout (asyncio.TimeoutError) also lands here: the
            # expert's isolated AgentLoop is stuck, so degrade to one LLM turn.
            if isinstance(exc, asyncio.TimeoutError):
                logger.warning(
                    "delegate_to_expert timed out after %.1fs (expert=%s); "
                    "falling back to a single complete() turn",
                    DELEGATE_TIMEOUT_SECONDS,
                    expert_id,
                )
            await _report("分析完成（降级）")
            from deeptutor.services.llm import complete

            try:
                raw = await complete(user, system_prompt=system)
            except Exception as e:
                return ToolResult(content=f"专家 {expert_id} 调用失败: {e}", success=False)
            content = f"专家 {expert_id} 结论：\n{raw}"
            return ToolResult(
                content=content,
                metadata={"delegate": {"expert": expert_id, "result": raw}},
            )


__all__ = [
    "DelegateExpertTool",
    "load_expert_card",
    "EXPERT_IDS",
    "EXPERT_TOOL_WHITELISTS",
]
