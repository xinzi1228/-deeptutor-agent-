from __future__ import annotations

import json

import pytest

from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.coach_context import build_annotation_coach_context


def test_draft_attempt_and_idempotency_are_profile_local(tmp_path) -> None:
    first = AnnotationAttemptStore(tmp_path / "first")
    second = AnnotationAttemptStore(tmp_path / "second")

    first.save_draft("task-1", "teaching", {"annotations": [{"label": "车"}]})
    assert first.get_draft("task-1")["payload"]["annotations"][0]["label"] == "车"
    assert second.get_draft("task-1") is None

    created, is_new = first.append_attempt(
        task_id="task-1",
        task_type="bbox",
        mode="teaching",
        payload={"annotations": []},
        metrics={"f1": 0.8},
        report="不错",
        idempotency_key="browser:task-1:123456",
    )
    duplicate, is_duplicate_new = first.append_attempt(
        task_id="task-1",
        task_type="bbox",
        mode="teaching",
        payload={"annotations": [{"unexpected": True}]},
        metrics={"f1": 0},
        report="不应覆盖",
        idempotency_key="browser:task-1:123456",
    )
    assert is_new is True
    assert is_duplicate_new is False
    assert duplicate["id"] == created["id"]
    assert len(first.list_attempts()) == 1


def test_payload_size_is_bounded(tmp_path) -> None:
    store = AnnotationAttemptStore(tmp_path)
    with pytest.raises(ValueError, match="256KB"):
        store.save_draft("task", "teaching", {"value": "x" * 300_000})


def test_coach_context_is_compact_and_only_includes_confirmed_patterns(tmp_path) -> None:
    root = tmp_path / "profile"
    store = AnnotationAttemptStore(root)
    for index in range(8):
        store.append_attempt(
            task_id=f"task-{index}", task_type="bbox", mode="teaching",
            payload={"annotations": []}, metrics={"f1": index / 10}, report="",
            idempotency_key=f"attempt-key-{index}",
        )
    learning = root / "learning" / "records.jsonl"
    learning.parent.mkdir(parents=True)
    learning.write_text(
        "\n".join([
            json.dumps({"error_pattern": "框过松", "pattern_status": "confirmed"}, ensure_ascii=False),
            json.dumps({"error_pattern": "疑似漏标", "pattern_status": "unconfirmed"}, ensure_ascii=False),
        ]),
        encoding="utf-8",
    )
    (root / "memory").mkdir()
    (root / "memory" / "recent.md").write_text("喜欢先看例子，再讲规则", encoding="utf-8")

    context = build_annotation_coach_context(root)

    assert len(context["recent_attempts"]) == 5
    assert context["confirmed_weaknesses"] == [{"pattern": "框过松", "task_id": ""}]
    assert "先看例子" in context["memory_summary"]
