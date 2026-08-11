"""Reliable, student-facing learning reports and reminders.

The functions in this module deliberately use only persisted learning records.
They provide a deterministic factual base for UI copy and scheduled reminders;
an LLM may polish that base later, but must not add facts to it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


DataStatus = Literal["sufficient", "partial", "empty"]


@dataclass(frozen=True)
class LearningCommunicationSummary:
    completed_count: int
    average_f1: float | None
    latest_f1: float | None
    trend: Literal["up", "down", "steady", "unknown"]
    strength: str | None
    priority_gap: str | None
    next_action: str
    data_status: DataStatus
    latest_task_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _exercise_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in records
        if not item.get("archived") and item.get("type") == "annotation_exercise"
    ]


def build_learning_communication_summary(
    records: list[dict[str, Any]],
) -> LearningCommunicationSummary:
    """Build a conservative summary from persisted records only.

    A single error never becomes a named long-term weakness.  ``priority_gap``
    is populated only from an explicitly confirmed pattern, matching the
    annotation-coach memory contract.
    """
    active = [item for item in records if not item.get("archived")]
    exercises = sorted(_exercise_records(active), key=lambda item: str(item.get("timestamp") or ""))
    f1_values = [value for item in exercises if (value := _number(item.get("f1"))) is not None]
    latest = exercises[-1] if exercises else None
    latest_f1 = _number(latest.get("f1")) if latest else None
    average_f1 = round(sum(f1_values) / len(f1_values), 3) if f1_values else None

    trend: Literal["up", "down", "steady", "unknown"] = "unknown"
    if len(f1_values) >= 2:
        delta = f1_values[-1] - f1_values[-2]
        trend = "up" if delta >= 0.03 else "down" if delta <= -0.03 else "steady"

    strength: str | None = None
    for item in reversed(active):
        points = [str(point) for point in item.get("knowledge_points") or [] if str(point).strip()]
        if item.get("type") == "annotation_exercise" and (_number(item.get("f1")) or 0) >= 0.7 and points:
            strength = points[0]
            break
        if item.get("type") == "theory_mastered" and item.get("readiness") in {"advance", "advance_with_caution"}:
            point = str(item.get("knowledge_point") or "").strip()
            if point:
                strength = point
                break

    priority_gap: str | None = None
    for item in reversed(active):
        pattern = str(item.get("error_pattern") or "").strip()
        if pattern and item.get("pattern_status") == "confirmed":
            priority_gap = pattern
            break

    if not active:
        status: DataStatus = "empty"
        action = "完成 1 道入门练习，先按“看图、选标签、检查边缘”做一遍。"
    elif len(exercises) < 2 or not f1_values:
        status = "partial"
        action = "完成下一道练习，先提交一次结果，让系统形成更可靠的学习判断。"
    elif priority_gap:
        status = "sufficient"
        action = f"完成 1 道针对“{priority_gap}”的加练，提交前重点检查这一项。"
    else:
        status = "sufficient"
        action = "完成下一道练习，提交前按“目标是否齐全、标签是否正确、边界是否贴合”检查一遍。"

    return LearningCommunicationSummary(
        completed_count=len(exercises),
        average_f1=average_f1,
        latest_f1=latest_f1,
        trend=trend,
        strength=strength,
        priority_gap=priority_gap,
        next_action=action,
        data_status=status,
        latest_task_id=str(latest.get("task_id")) if latest and latest.get("task_id") else None,
    )


def render_learning_report(summary: LearningCommunicationSummary) -> str:
    """Render a four-part report with an honest no-data fallback."""
    if summary.data_status == "empty":
        return "\n".join(
            [
                "本次成果：暂时还没有已提交的练习记录。",
                "当前判断：现在的数据不足，暂时不能判断你的掌握水平。",
                "关键改进点：先完成一次完整练习，建立第一份可靠记录。",
                f"下次行动：{summary.next_action}",
            ]
        )

    score = (
        f"平均 F1 为 {summary.average_f1 * 100:.0f}%"
        if summary.average_f1 is not None
        else "已有练习记录，但评分数据还不完整"
    )
    trend_text = {
        "up": "，最近一次比上一次更好",
        "down": "，最近一次需要再巩固",
        "steady": "，最近两次表现基本稳定",
        "unknown": "，还没有足够的可比记录",
    }[summary.trend]
    strength = f"“{summary.strength}”已经有可靠表现。" if summary.strength else "先继续积累练习证据，再判断稳定优势。"
    gap = (
        f"已确认需要优先处理“{summary.priority_gap}”。"
        if summary.priority_gap
        else "暂未发现已确认的稳定薄弱点，本次先巩固最近任务。"
    )
    return "\n".join(
        [
            f"本次成果：已完成 {summary.completed_count} 道练习；{strength}",
            f"当前判断：{score}{trend_text}。",
            f"关键改进点：{gap}",
            f"下次行动：{summary.next_action}",
        ]
    )


def render_learning_reminder(summary: LearningCommunicationSummary, message: str) -> str:
    """Render a two-sentence reminder suitable for chat and notifications."""
    subject = str(message or "学习提醒").strip()
    if summary.data_status == "empty":
        reason = f"你设定的提醒到了：{subject}。"
    elif summary.priority_gap:
        reason = f"你设定的提醒到了：{subject}；已确认“{summary.priority_gap}”值得优先复习。"
    elif summary.latest_task_id:
        reason = f"你设定的提醒到了：{subject}；可以从上次的 {summary.latest_task_id} 继续。"
    else:
        reason = f"你设定的提醒到了：{subject}。"
    return f"{reason}\n{summary.next_action}"


def audit_learning_copy(
    text: str,
    *,
    kind: Literal["report", "reminder"],
    summary: LearningCommunicationSummary,
) -> list[str]:
    """Return non-blocking quality warnings for generated student-facing copy."""
    warnings: list[str] = []
    compact = " ".join(str(text or "").split())
    if not compact:
        return ["文案为空"]
    if any(phrase in compact for phrase in ("继续加油", "表现不错", "再接再厉")):
        warnings.append("包含空泛鼓励")
    action_words = ("完成", "练习", "复习", "检查", "开始", "标注", "提交")
    if not any(word in compact for word in action_words):
        warnings.append("缺少明确下一步动作")
    if kind == "reminder":
        sentences = [part for part in compact.replace("！", "。").replace("？", "。").split("。") if part.strip()]
        if len(sentences) > 2:
            warnings.append("提醒超过两句")
    if kind == "report" and len(compact) > 360:
        warnings.append("报告过长")
    if summary.data_status == "empty" and any(word in compact for word in ("平均 F1", "提升", "下降", "薄弱点")):
        warnings.append("数据不足时出现确定性学习结论")
    return warnings


__all__ = [
    "LearningCommunicationSummary",
    "audit_learning_copy",
    "build_learning_communication_summary",
    "render_learning_reminder",
    "render_learning_report",
]
