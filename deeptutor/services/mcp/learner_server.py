"""Learner-state MCP server (EDUMCP-style interop).

Exposes the annotation-coach's learner state to external MCP clients over
stdio: progress, capability radar, F1 trend, skill tree, learning records,
diagnosis brief, plus the annotation task bank and IOU checker. Any MCP
client (Claude Code, Codex, Label Studio hooks, other agents) can read the
learner's state or append a practice record through a standard protocol.

Run it from a shell (stdio transport):

    python -m deeptutor.services.mcp.learner_server

An MCP client config example (Claude Code ``.mcp.json``):

    {"mcpServers": {"learner": {"command": "python", "args": [
      "-m", "deeptutor.services.mcp.learner_server"]}}}
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from deeptutor.services.learning_records import LearningRecordStore, validate_record

server = Server("learner-state")


def _json_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def _tool(name: str, description: str, properties: dict | None = None) -> Tool:
    return Tool(
        name=name,
        description=description,
        inputSchema={
            "type": "object",
            "properties": properties or {},
            "additionalProperties": False,
        },
    )


# ── tools ────────────────────────────────────────────────────────────────

_TOOLS = [
    _tool(
        "get_learner_overview",
        "学习进度总览：完成任务数/通过率/最新F1/教学模式/学习目标。",
    ),
    _tool(
        "get_learner_radar",
        "五维能力雷达：框精度/标签准确/完整性/一致性/知识掌握。",
    ),
    _tool(
        "get_f1_trend",
        "F1 成长曲线数据点（按任务排序）。",
    ),
    _tool(
        "get_skill_tree",
        "能力图谱树，含每个技能点的掌握状态。",
    ),
    _tool(
        "get_learning_records",
        "学习记录",
        {"limit": {"type": "integer", "description": "返回条数, 默认 10"}},
    ),
    _tool(
        "get_learner_brief",
        "最近一次诊断产生的学习路线 brief。",
    ),
    _tool(
        "get_course_plan",
        "确定性课程计划 (4 模块: 概念+任务+DAG)。缺省时从 brief 自动重建。",
        {"force": {"type": "boolean", "description": "True 强制重建"}},
    ),
    _tool(
        "get_decision_log",
        "最近的教练决策审计日志 (为什么推荐这个任务)。",
        {"limit": {"type": "integer", "description": "返回条数, 默认 20"}},
    ),
    _tool(
        "get_teaching_evaluations",
        "最近的对抗性教学方案评估结果。",
        {"limit": {"type": "integer", "description": "返回条数, 默认 10"}},
    ),
    _tool(
        "get_annotation_task",
        "获取标注练习任务",
        {"task_id": {"type": "string", "description": "task1-task9"}},
    ),
    _tool(
        "check_annotation",
        "评测标注结果 (IOU/F1) 返回教学反馈",
        {
            "predictions": {"type": "string", "description": "预测框 JSON 数组"},
            "ground_truth": {"type": "string", "description": "真值框 JSON 数组"},
            "task_type": {"type": "string", "description": "bbox 或 classification"},
        },
    ),
    _tool(
        "append_learning_record",
        "追加一条学习记录 (供外部标注工具/Agent 写入)",
        {"record": {"type": "string", "description": "synapse JSON 记录字符串"}},
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    args = arguments or {}
    stats = None
    try:
        if name == "get_learner_overview":
            return _json_text(_stats().overview())
        if name == "get_learner_radar":
            return _json_text(_stats().radar())
        if name == "get_f1_trend":
            return _json_text(_stats().f1_trend())
        if name == "get_skill_tree":
            return _json_text(_stats().skill_tree())
        if name == "get_learning_records":
            limit = int(args.get("limit") or 10)
            return _json_text(_store().list_records()[-limit:])
        if name == "get_learner_brief":
            brief = _store().get_brief()
            return _json_text(brief or {"error": "no brief yet"})
        if name == "get_course_plan":
            from deeptutor.services.course_plan import rebuild

            force = bool(args.get("force") or False)
            return _json_text(rebuild(force=force) or {"error": "build failed"})
        if name == "get_decision_log":
            limit = int(args.get("limit") or 20)
            return _json_text(_store().list_decisions(limit=limit))
        if name == "get_teaching_evaluations":
            limit = int(args.get("limit") or 10)
            return _json_text(_store().list_evaluations(limit=limit))
        if name == "get_annotation_task":
            from deeptutor.tools.task_bank_tool import GetAnnotationTaskTool

            result = await GetAnnotationTaskTool().execute(task_id=args.get("task_id", "task1"))
            return _json_text({"content": result.content, "success": result.success})
        if name == "check_annotation":
            from deeptutor.tools.annotation_check import AnnotationCheckTool

            result = await AnnotationCheckTool().execute(
                predictions=args.get("predictions", "[]"),
                ground_truth=args.get("ground_truth", "[]"),
                task_type=args.get("task_type", "bbox"),
            )
            return _json_text({"content": result.content, "success": result.success})
        if name == "append_learning_record":
            raw = args.get("record")
            record = json.loads(raw) if isinstance(raw, str) else raw
            error = validate_record(record)
            if error:
                return _json_text({"error": error, "success": False})
            persisted = await _store().append(record)
            return _json_text({"success": True, "record": persisted})
        return _json_text({"error": f"unknown tool: {name}"})
    except Exception as exc:  # never crash the server
        return _json_text({"error": str(exc), "success": False})


# ── resources ─────────────────────────────────────────────────────────────

_RESOURCES = [
    Resource(uri="learner://overview", name="学习进度总览", mimeType="application/json"),
    Resource(uri="learner://radar", name="五维能力雷达", mimeType="application/json"),
    Resource(uri="learner://records", name="学习记录", mimeType="application/json"),
    Resource(uri="learner://brief", name="诊断 brief", mimeType="application/json"),
    Resource(uri="learner://skill-tree", name="能力图谱", mimeType="application/json"),
    Resource(uri="learner://course-plan", name="课程计划", mimeType="application/json"),
    Resource(uri="learner://evaluations", name="教学方案评估", mimeType="application/json"),
]


@server.list_resources()
async def list_resources() -> list[Resource]:
    return _RESOURCES


@server.read_resource()
async def read_resource(uri: Any) -> list[Any]:
    from mcp.server.lowlevel.helper_types import ReadResourceContents

    key = str(uri)
    body: Any
    if key == "learner://overview":
        body = _stats().overview()
    elif key == "learner://radar":
        body = _stats().radar()
    elif key == "learner://records":
        body = _store().list_records()
    elif key == "learner://brief":
        body = _store().get_brief() or {"error": "no brief yet"}
    elif key == "learner://skill-tree":
        body = _stats().skill_tree()
    elif key == "learner://course-plan":
        from deeptutor.services.course_plan import rebuild

        body = rebuild(force=False) or {"error": "no plan yet"}
    elif key == "learner://evaluations":
        body = _store().list_evaluations(limit=10)
    else:
        raise ValueError(f"unknown resource: {key}")
    return [
        ReadResourceContents(
            content=json.dumps(body, ensure_ascii=False, indent=2),
            mime_type="application/json",
        )
    ]


def _stats():
    from deeptutor.services.learning_records import LearningStats

    return LearningStats(_store())


def _store() -> LearningRecordStore:
    return LearningRecordStore()


async def _run_stdio() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    import asyncio

    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
