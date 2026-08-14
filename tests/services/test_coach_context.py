from __future__ import annotations

from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.annotation_scoring import AnnotationScoreStore
from deeptutor.services.coach_context import build_annotation_coach_context


def test_coach_context_includes_current_draft_step_memory_and_corrections(tmp_path) -> None:
    root = tmp_path / "profile"
    attempts = AnnotationAttemptStore(root)
    attempts.save_draft(
        "task-1",
        "teaching",
        {"predictions": [{"id": "box-1", "label": "car"}], "image_size": "1000x1000"},
    )
    attempts.set_current(
        task_id="task-1",
        mode="teaching",
        stage="editing",
        summary={"selected_object_id": "box-1", "current_label": "car", "tool": "select"},
    )
    scores = AnnotationScoreStore(root)
    scores.record(task_id="task-1", attempt_id="a1", metrics={"f1": 0.5}, rule_version="r1", reference_version="g1", score_hash="h1")
    scores.record(task_id="task-1", attempt_id="a2", metrics={"f1": 0.8}, rule_version="r1", reference_version="g1", score_hash="h2")
    (root / "memory").mkdir(parents=True)
    (root / "memory" / "recent.md").write_text("喜欢先看示例", encoding="utf-8")

    context = build_annotation_coach_context(root)

    assert context["saved_draft"]["annotation_count"] == 1
    assert context["annotation_projection"]["summary"]["selected_object_id"] == "box-1"
    assert context["recent_scores"][-1]["metric_delta"]["f1"] == 0.3
    assert "先看示例" in context["memory_summary"]
    assert "payload" not in str(context["saved_draft"])
