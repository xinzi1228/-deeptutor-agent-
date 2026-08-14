from __future__ import annotations

from deeptutor.core.context import UnifiedContext
from deeptutor.services.teaching_orchestration.budgets import ToolBudget
from deeptutor.services.teaching_orchestration.models import TeachingIntent
from deeptutor.services.teaching_orchestration.policy import (
    build_progressive_answer,
    build_teaching_run_policy,
)

MOUNTED_TOOLS = [
    "ask_user",
    "kb_search",
    "rag",
    "read_source",
    "read_memory",
    "web_fetch",
    "get_annotation_task",
    "annotation_check",
    "read_learning_chart_data",
    "create_visualization",
    "write_learning_record",
    "log_decision",
]


def _context(message: str) -> UnifiedContext:
    return UnifiedContext(
        session_id="session-1",
        user_message=message,
        language="zh",
        metadata={"turn_id": "turn-1", "current_task_id": "road-001"},
    )


def test_normative_question_requires_approved_source_and_blocks_open_web() -> None:
    policy = build_teaching_run_policy(
        _context("国家标准对边界框贴边阈值是怎么规定的？"), MOUNTED_TOOLS
    )

    assert policy.intent is TeachingIntent.NORMATIVE
    assert policy.required_source_level == "approved"
    assert policy.max_retrieval_calls == 1
    assert "kb_search" in policy.allowed_tools
    assert "read_source" in policy.allowed_tools
    assert "web_fetch" not in policy.allowed_tools
    assert "write_learning_record" not in policy.allowed_tools


def test_annotation_help_can_read_task_but_cannot_mutate_learning_record() -> None:
    policy = build_teaching_run_policy(
        _context("我在当前这道遮挡题卡住了，这个框应该怎么画？"), MOUNTED_TOOLS
    )

    assert policy.intent is TeachingIntent.ANNOTATION_HELP
    assert policy.max_tool_calls == 4
    assert policy.max_retrieval_calls == 1
    assert "get_annotation_task" in policy.allowed_tools
    assert "annotation_check" in policy.allowed_tools
    assert "write_learning_record" not in policy.allowed_tools


def test_report_question_uses_server_dataset_tools() -> None:
    policy = build_teaching_run_policy(
        _context("给我看看最近一周漏标次数的折线图"), MOUNTED_TOOLS
    )

    assert policy.intent is TeachingIntent.REPORT
    assert "read_learning_chart_data" in policy.allowed_tools
    assert "create_visualization" in policy.allowed_tools


def test_budget_filters_disallowed_and_excess_retrieval_calls() -> None:
    policy = build_teaching_run_policy(_context("给我讲讲什么是漏标"), MOUNTED_TOOLS)
    budget = ToolBudget(policy, clock=lambda: 100.0)

    accepted, rejected = budget.admit_tool_calls(
        [
            {"id": "1", "name": "kb_search"},
            {"id": "2", "name": "rag"},
            {"id": "3", "name": "write_learning_record"},
        ]
    )

    assert [item["name"] for item in accepted] == ["kb_search"]
    assert {item.reason for item in rejected} == {
        "retrieval_budget_exhausted",
        "tool_not_allowed",
    }
    assert budget.snapshot().tool_calls == 1
    assert budget.snapshot().retrieval_calls == 1


def test_budget_exposes_soft_and_hard_deadlines() -> None:
    now = [10.0]
    policy = build_teaching_run_policy(_context("解释一下目标检测"), MOUNTED_TOOLS)
    budget = ToolBudget(policy, clock=lambda: now[0])

    now[0] += policy.soft_timeout_ms / 1000 + 0.01
    assert budget.soft_expired is True
    assert budget.hard_expired is False

    now[0] += (policy.hard_timeout_ms - policy.soft_timeout_ms) / 1000
    assert budget.hard_expired is True
    assert budget.remaining_hard_seconds == 0


def test_progressive_answer_marks_missing_normative_source() -> None:
    policy = build_teaching_run_policy(
        _context("规范要求遮挡目标必须保留多少比例？"), MOUNTED_TOOLS
    )
    answer = build_progressive_answer(
        "当前项目资料没有找到可核验的比例要求。",
        policy=policy,
        sources=[],
    )

    assert answer.summary == "当前项目资料没有找到可核验的比例要求。"
    assert answer.uncertainty is not None
    assert answer.citations == ()
    assert answer.to_dict()["details"]
