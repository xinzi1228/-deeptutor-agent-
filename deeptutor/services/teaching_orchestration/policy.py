"""Pure intent classification and policy construction for teaching chat."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

from deeptutor.core.context import UnifiedContext

from .models import ProgressiveAnswer, TeachingIntent, TeachingRunPolicy

_NORMATIVE_RE = re.compile(r"标准|规范|阈值|安全要求|依据|国标|GB\s*/?\s*T", re.IGNORECASE)
_REPORT_RE = re.compile(r"报告|趋势|折线图|柱状图|雷达图|对比图|最近(?:一周|一月)|平均分|完成率")
_CORRECTION_RE = re.compile(r"订正|改错|重新标|重画|修订")
_SUBMISSION_RE = re.compile(r"为什么扣分|评分结果|提交结果|得分|哪里错")
_ANNOTATION_RE = re.compile(r"当前(?:题|任务)|这道题|卡住|怎么画|框选|边界框|漏标|错标|遮挡|贴边")
_DIAGNOSIS_RE = re.compile(r"诊断|测试.*水平|入门测验|测测我")
_CLARIFICATION_RE = re.compile(r"^(?:怎么办|怎么学|我不会|不懂|帮帮我|开始学习)[？?。！!]*$")

_RETRIEVAL_TOOLS = frozenset(
    {"rag", "kb_search", "read_source", "read_memory", "graph_query", "competency_map"}
)
_COMMON = frozenset({"ask_user", "route_input", "verify_output", "render_ui"})
_KNOWLEDGE = frozenset(
    {
        "rag",
        "kb_search",
        "read_source",
        "read_memory",
        "graph_query",
        "competency_map",
        "delegate_to_expert",
    }
)
_VISUAL = frozenset(
    {
        "read_learning_chart_data",
        "create_visualization",
        "generate_iou_demo",
        "imagegen",
        "render_learning_path",
    }
)
_ANNOTATION = frozenset(
    {"get_annotation_task", "annotation_check", "teaching_flow", "struggle_detect"}
)


def classify_teaching_intent(message: str) -> TeachingIntent:
    text = str(message or "").strip()
    if _NORMATIVE_RE.search(text):
        return TeachingIntent.NORMATIVE
    if _REPORT_RE.search(text):
        return TeachingIntent.REPORT
    if _CORRECTION_RE.search(text):
        return TeachingIntent.CORRECTION
    if _SUBMISSION_RE.search(text):
        return TeachingIntent.SUBMISSION_EXPLANATION
    if _ANNOTATION_RE.search(text):
        return TeachingIntent.ANNOTATION_HELP
    if _DIAGNOSIS_RE.search(text):
        return TeachingIntent.DIAGNOSIS
    if _CLARIFICATION_RE.search(text):
        return TeachingIntent.CLARIFICATION
    return TeachingIntent.THEORY


def _policy_shape(intent: TeachingIntent) -> tuple[frozenset[str], int, int, str | None, bool]:
    if intent is TeachingIntent.NORMATIVE:
        return _COMMON | _KNOWLEDGE, 2, 1, "approved", False
    if intent is TeachingIntent.REPORT:
        return _COMMON | _KNOWLEDGE | _VISUAL, 4, 1, None, False
    if intent in {
        TeachingIntent.ANNOTATION_HELP,
        TeachingIntent.SUBMISSION_EXPLANATION,
        TeachingIntent.CORRECTION,
    }:
        return _COMMON | _KNOWLEDGE | _ANNOTATION | _VISUAL, 4, 1, None, False
    if intent is TeachingIntent.DIAGNOSIS:
        return _COMMON | _KNOWLEDGE | frozenset({"finalize_diagnosis"}), 3, 1, None, True
    if intent is TeachingIntent.CLARIFICATION:
        return _COMMON | frozenset({"read_memory"}), 2, 1, None, False
    return _COMMON | _KNOWLEDGE | _VISUAL | frozenset({"web_fetch"}), 2, 1, None, False


def build_teaching_run_policy(
    context: UnifiedContext,
    mounted_tools: Iterable[str],
) -> TeachingRunPolicy:
    intent = classify_teaching_intent(context.user_message)
    allowlist, max_tools, max_retrieval, source_level, may_write = _policy_shape(intent)
    mounted = tuple(dict.fromkeys(str(name) for name in mounted_tools if str(name).strip()))
    allowed = tuple(name for name in mounted if name in allowlist)
    metadata = context.metadata or {}
    profile_id = str(metadata.get("learning_profile_id") or metadata.get("profile_id") or "")
    current_task_id = str(metadata.get("current_task_id") or "").strip() or None
    return TeachingRunPolicy(
        intent=intent,
        profile_id=profile_id,
        current_task_id=current_task_id,
        allowed_tools=allowed,
        max_tool_calls=max_tools,
        max_retrieval_calls=max_retrieval,
        soft_timeout_ms=15_000,
        hard_timeout_ms=30_000,
        may_write_learning_record=may_write,
        required_source_level=source_level,
    )


def render_policy_prompt(policy: TeachingRunPolicy) -> str:
    source_rule = (
        "涉及规范、阈值或安全要求时，只能依据已审核来源；没有可靠来源就明确说明无法核验。"
        if policy.required_source_level
        else "需要引用时使用已返回的真实来源，不得编造来源。"
    )
    return (
        "[服务端教学策略]\n"
        f"意图：{policy.intent.value}。工具总次数上限：{policy.max_tool_calls}；"
        f"检索上限：{policy.max_retrieval_calls}。\n"
        f"{source_rule}\n"
        "回答顺序：先给一句话结论，再给学生现在要做的动作，然后解释最多三个关键原因；"
        "详细内容、引用和可视化放在后面。不要声称你已经执行未发生的工具或写入。"
    )


def _clean_line(line: str) -> str:
    return re.sub(r"^[\s#>*\-\d.、]+", "", line).strip()


def _source_ids(sources: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    result: list[str] = []
    for source in sources:
        source_id = str(
            source.get("id") or source.get("citation_id") or source.get("source_id") or ""
        ).strip()
        if source_id and source_id not in result:
            result.append(source_id)
    return tuple(result)


def build_progressive_answer(
    text: str,
    *,
    policy: TeachingRunPolicy,
    sources: Iterable[Mapping[str, Any]] = (),
    artifact_ids: Iterable[str] = (),
) -> ProgressiveAnswer:
    body = str(text or "").strip()
    lines = [_clean_line(line) for line in body.splitlines() if _clean_line(line)]
    summary = (lines[0] if lines else "本次没有生成可用回答。")[:240]
    next_action = next(
        (line for line in lines[1:] if "下一步" in line or line.startswith("请") or "现在" in line),
        "",
    )
    reasons = tuple(
        line[:240] for line in lines[1:] if line != next_action and len(line) <= 240
    )[:3]
    citations = _source_ids(sources)
    uncertainty = None
    if policy.required_source_level and not citations:
        uncertainty = "当前回答没有可核验的已审核来源，不能把规范、阈值或安全要求当作确定事实。"
    return ProgressiveAnswer(
        summary=summary,
        next_action=next_action,
        reasons=reasons,
        details=({"title": "详细说明", "markdown": body or summary},),
        citations=citations,
        artifact_ids=tuple(dict.fromkeys(str(item) for item in artifact_ids if str(item).strip())),
        uncertainty=uncertainty,
    )


__all__ = [
    "_RETRIEVAL_TOOLS",
    "build_progressive_answer",
    "build_teaching_run_policy",
    "classify_teaching_intent",
    "render_policy_prompt",
]
