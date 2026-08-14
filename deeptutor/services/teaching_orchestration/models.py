"""Data contracts for one deterministic teaching turn."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class TeachingIntent(str, Enum):
    THEORY = "theory"
    CLARIFICATION = "clarification"
    ANNOTATION_HELP = "annotation_help"
    SUBMISSION_EXPLANATION = "submission_explanation"
    CORRECTION = "correction"
    REPORT = "report"
    NORMATIVE = "normative"
    DIAGNOSIS = "diagnosis"


@dataclass(frozen=True, slots=True)
class TeachingRunPolicy:
    """Immutable server-owned limits for a single chat turn."""

    intent: TeachingIntent
    profile_id: str
    current_task_id: str | None
    allowed_tools: tuple[str, ...]
    max_tool_calls: int
    max_retrieval_calls: int
    soft_timeout_ms: int
    hard_timeout_ms: int
    may_write_learning_record: bool
    required_source_level: str | None
    answer_contract: str = "progressive_v1"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["intent"] = self.intent.value
        payload["allowed_tools"] = list(self.allowed_tools)
        return payload


@dataclass(frozen=True, slots=True)
class ProgressiveAnswer:
    """Stable result metadata; the streamed markdown remains the display body."""

    summary: str
    next_action: str
    reasons: tuple[str, ...]
    details: tuple[dict[str, str], ...]
    citations: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    uncertainty: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "next_action": self.next_action,
            "reasons": list(self.reasons),
            "details": [dict(item) for item in self.details],
            "citations": list(self.citations),
            "artifact_ids": list(self.artifact_ids),
            "uncertainty": self.uncertainty,
        }
