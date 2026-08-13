import pytest

from deeptutor.services.learning_communication import (
    audit_learning_copy,
    build_learning_communication_summary,
    render_learning_reminder,
    render_learning_report,
)


def test_empty_records_use_honest_report_and_two_sentence_reminder():
    summary = build_learning_communication_summary([])

    report = render_learning_report(summary)
    reminder = render_learning_reminder(summary, "今晚复习标注")

    assert summary.data_status == "empty"
    assert "数据不足" in report
    assert "平均 F1" not in report
    assert len([line for line in reminder.splitlines() if line]) == 2
    assert audit_learning_copy(reminder, kind="reminder", summary=summary) == []


def test_confirmed_pattern_is_the_only_named_priority_gap():
    records = [
        {"type": "annotation_exercise", "task_id": "task-1", "f1": 0.62, "error_pattern": "漏标", "pattern_status": "unconfirmed", "timestamp": "2026-08-01"},
        {"type": "annotation_exercise", "task_id": "task-2", "f1": 0.79, "knowledge_points": ["遮挡目标"], "error_pattern": "漏标", "pattern_status": "confirmed", "timestamp": "2026-08-02"},
    ]

    summary = build_learning_communication_summary(records)
    report = render_learning_report(summary)

    assert summary.priority_gap == "漏标"
    assert summary.strength == "遮挡目标"
    assert summary.trend == "up"
    assert "已确认需要优先处理“漏标”" in report
    assert "完成 1 道针对“漏标”的加练" in report


def test_copy_audit_flags_generic_or_overlong_reminder():
    summary = build_learning_communication_summary([])
    warnings = audit_learning_copy(
        "继续加油。你很棒。明天再说。",
        kind="reminder",
        summary=summary,
    )

    assert "包含空泛鼓励" in warnings
    assert "缺少明确下一步动作" in warnings
    assert "提醒超过两句" in warnings


def test_reminder_prompt_requires_factual_base_without_internal_ids():
    from deeptutor.services.cron.executor import _reminder_prompt
    from deeptutor.services.cron.service import CronJob, CronOwner, CronSchedule

    job = CronJob(
        id="private-job-id",
        name="复习",
        message="今晚复习遮挡标注",
        schedule=CronSchedule(kind="every", every_seconds=60),
        owner=CronOwner(kind="chat", session_id="session-1"),
    )
    prompt = _reminder_prompt(job, factual_reminder="现在先完成 1 道练习。")

    assert "only source of learner-specific facts" in prompt
    assert "现在先完成 1 道练习。" in prompt
    assert "private-job-id" not in prompt


@pytest.mark.asyncio
async def test_report_summary_endpoint_uses_record_backed_text(monkeypatch):
    from deeptutor.api.routers import profile

    monkeypatch.setattr(
        profile,
        "_all_records",
        lambda: [
            {
                "type": "annotation_exercise",
                "task_id": "task-1",
                "f1": 0.8,
                "knowledge_points": ["边界框"],
                "timestamp": "2026-08-01",
            }
        ],
    )

    result = await profile.report_summary()

    assert result["summary"]["completed_count"] == 1
    assert "已完成 1 道练习" in result["text"]
    assert result["quality_warnings"] == []


@pytest.mark.asyncio
async def test_report_card_extension_changes_presentation_only(monkeypatch):
    from deeptutor.api.routers import profile
    from deeptutor.services.extension_marketplace import ExtensionMarketplaceService

    monkeypatch.setattr(profile, "_all_records", lambda: [])
    monkeypatch.setattr(ExtensionMarketplaceService, "is_enabled", lambda self, value: value == "report-card-enhancer")

    result = await profile.report_summary()

    assert result["presentation"] == "cards"
    assert [card["title"] for card in result["cards"]] == [
        "本次成果", "当前判断", "关键改进点", "下次行动"
    ]
    assert "数据不足" in result["text"]
