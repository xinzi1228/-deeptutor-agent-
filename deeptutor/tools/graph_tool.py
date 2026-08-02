"""GraphQueryTool — coach tool for deterministic graph queries + optional LLM explanation."""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints

QUERY_TYPES = ("risk_path", "concepts", "mastery")


class GraphQueryTool(BaseTool):
    """Query the learner knowledge graph (risk chain / concept navigation / mastery)."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="graph_query",
            description=(
                "Query the learner knowledge graph: risk_path (前置未掌握/下游风险链), "
                "concepts (技能前置/依赖/关联任务), mastery (已掌握/挣扎技能快照). "
                "Use BEFORE teaching a new skill to personalise the route."
            ),
            parameters=[
                ToolParameter(
                    name="query_type",
                    type="string",
                    description="risk_path | concepts | mastery",
                    enum=list(QUERY_TYPES),
                ),
                ToolParameter(
                    name="target",
                    type="string",
                    description="Skill id or task id (required for risk_path/concepts).",
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        query_type = str(kwargs.get("query_type") or "").strip()
        target = str(kwargs.get("target") or "").strip()

        if query_type not in QUERY_TYPES:
            return ToolResult(
                content=f"Error: query_type must be one of {', '.join(QUERY_TYPES)}.",
                success=False,
            )
        if query_type in ("risk_path", "concepts") and not target:
            return ToolResult(content="Error: target is required for this query_type.", success=False)

        from deeptutor.services.graph_query import GraphQueryService

        graph = await _load_graph()
        if not graph or not graph.get("nodes"):
            return ToolResult(
                content="知识图谱尚未构建。请先完成诊断（finalize_diagnosis）并记录学习记录。",
                success=False,
            )

        svc = GraphQueryService(graph)
        if query_type == "mastery":
            data = svc.mastery_snapshot()
            content = _format_mastery(data)
        elif query_type == "concepts":
            data = svc.concepts(target)
            content = _format_concepts(data)
        else:
            data = svc.risk_path(target)
            content = _format_risk_path(data)

            # chart: skill/task dependency graph with risk markers
            from deeptutor.tools.chart_cards import graph_chart

            nodes: list[dict] = [{"id": data["target"], "label": data["target_name"], "status": "target"}]
            edges: list[dict] = []
            for p in data.get("missing_prereqs", []):
                nodes.append({"id": p["id"], "label": p["name"], "status": "missing"})
                edges.append({"source": data["target"], "target": p["id"]})
            for s in data.get("struggling", []):
                nodes.append({"id": s["id"], "label": s["name"], "status": "struggling"})
            for d in data.get("affected_downstream", []):
                nodes.append({"id": d["id"], "label": d["name"], "status": "affected"})
                edges.append({"source": data["target"], "target": d["id"]})
            data["chart"] = graph_chart(nodes=nodes, edges=edges)

            if data.get("confidence") == "high":
                try:
                    explanation = await _explain_risk(query=data, target=target)
                except Exception:
                    explanation = None
                if explanation:
                    content = f"{content}\n\n{explanation}"

        return ToolResult(content=content, metadata=data)

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


# --------------------------------------------------------------- formatting

def _format_mastery(data: dict) -> str:
    mastered = ", ".join(x["name"] for x in data.get("mastered", [])) or "无"
    struggling = ", ".join(x["name"] for x in data.get("struggling", [])) or "无"
    return f"已掌握: {mastered}\n挣扎中: {struggling}"


def _format_concepts(data: dict) -> str:
    pre = ", ".join(x["name"] for x in data.get("prerequisites", [])) or "无"
    dep = ", ".join(x["name"] for x in data.get("dependents", [])) or "无"
    tasks = ", ".join(x["name"] for x in data.get("tasks", [])) or "无"
    return (
        f"技能: {data.get('name', '')}\n前置: {pre}\n依赖此技能: {dep}\n关联任务: {tasks}"
    )


def _format_risk_path(data: dict) -> str:
    lines = [f"风险链分析: {data.get('target_name')}"]
    for x in data.get("missing_prereqs", []):
        lines.append(f"  [缺失前置] {x['name']}")
    for x in data.get("struggling", []):
        f1 = f" (F1={x['f1']})" if x.get("f1") is not None else ""
        lines.append(f"  [挣扎技能] {x['name']}{f1}")
    for x in data.get("affected_downstream", []):
        lines.append(f"  [下游影响] {x['name']} — {x['reason']}")
    return "\n".join(lines)


# ------------------------------------------------------------ dependencies

def _load_competency_tree() -> dict:
    from deeptutor.tools.competency_tool import _load_competency_tree as _load

    return _load()


def _load_bank() -> dict:
    from deeptutor.tools.task_bank_tool import _load_bank as _load

    return _load() or {}


def _list_records() -> list[dict]:
    from deeptutor.services.learning_records import LearningRecordStore

    return LearningRecordStore().list_records()


async def _load_graph(
    *, tree: dict | None = None, bank: dict | None = None, records: list[dict] | None = None
) -> dict | None:
    """Return persisted graph, or rebuild from JSONL records on the fly.

    The tree/bank/records inputs are only loaded (from args or lazy loaders)
    when no graph is persisted — the common per-turn path is a single
    ``store.get()``.
    """
    from deeptutor.services.knowledge_graph import KnowledgeGraphStore

    store = KnowledgeGraphStore()
    graph = store.get()
    if graph:
        return graph
    if tree is None:
        tree = _load_competency_tree()
    if bank is None:
        bank = _load_bank() or {}
    if records is None:
        records = _list_records()
    if isinstance(tree, dict) and "tree" in tree:
        tree = tree["tree"]
    if not tree.get("children"):
        return None
    graph = KnowledgeGraphStore.build(tree=tree, bank=bank, records=records)
    store.save(graph)
    return graph


async def _explain_risk(query: dict, target: str) -> str | None:
    """LLM explanation of the risk chain. Caller must catch exceptions."""
    from deeptutor.tools.reason import reason

    context = _format_risk_path(query)
    prompt = (
        f"你是数据标注教学教练。基于以下知识图谱风险链结果，用中文给学生解释"
        f"为什么'{query.get('target_name', target)}'有学习风险，并给出先补什么、再练什么的建议。"
        f"语气鼓励但具体。只依据以下风险链数据，不得虚构 F1 数值或前置技能。\n\n风险链数据:\n{context}"
    )
    result = await reason(query=prompt, max_tokens=200, temperature=0.3)
    answer = (result or {}).get("answer", "").strip()
    return answer or None


__all__ = ["GraphQueryTool"]
