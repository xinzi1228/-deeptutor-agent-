"""Usability study data models for competition evidence.

An immutable ``StudyRun`` references an anonymous participant, a round (A/B),
a task version, consent scope, and an event file. Reports are generated
deterministically from these records; the generator rejects runs with invalid
participant ids, missing consent, unknown task versions, out-of-order events,
or hash mismatches.

Only anonymous identifiers (``S01``/``S02``/``T01``) are stored. Real names,
schools, faces and contact details never enter the evidence package.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

ParticipantRole = Literal["student", "teacher"]
StudyRound = Literal["A", "B"]
ConsentScope = Literal[
    "participate",
    "screen_record",
    "audio_record",
    "quote",
    "retention",
]
Severity = Literal["blocker", "critical", "moderate", "suggestion"]

VALID_PARTICIPANT_RE = r"^(S0[12]|T01)$"
KNOWN_TASK_VERSIONS = ("traffic-vehicle-1.0", "traffic-vehicle-1.1")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ConsentRecord(BaseModel):
    participant_id: str
    scope: ConsentScope
    granted: bool
    granted_at: str = Field(default_factory=utcnow)
    note: str = ""


class StudyRun(BaseModel):
    """One immutable test session for one participant in one round."""

    run_id: str = Field(default_factory=lambda: f"run-{uuid4().hex[:12]}")
    participant_id: str
    round: StudyRound
    scenario: str = "traffic-road-vehicle-pedestrian"
    task_version: str
    content_version: str = ""
    model_config_ref: str = ""
    label_studio_status: str = "n/a"
    device_conditions: str = ""
    consent: list[ConsentRecord] = Field(default_factory=list)
    events_file: str = ""
    created_at: str = Field(default_factory=utcnow)

    @field_validator("participant_id")
    @classmethod
    def _validate_participant(cls, value: str) -> str:
        import re

        if not re.fullmatch(VALID_PARTICIPANT_RE, value):
            raise ValueError(f"非法参与者编号：{value}")
        return value

    @field_validator("task_version")
    @classmethod
    def _validate_task_version(cls, value: str) -> str:
        if value not in KNOWN_TASK_VERSIONS:
            raise ValueError(f"未知任务版本：{value}")
        return value

    def has_consent(self, scope: ConsentScope) -> bool:
        return any(
            record.scope == scope and record.granted for record in self.consent
        )

    def consent_summary(self) -> dict[str, bool]:
        return {scope: self.has_consent(scope) for scope in CONSENT_SCOPE_ORDER}


CONSENT_SCOPE_ORDER: tuple[ConsentScope, ...] = (
    "participate",
    "screen_record",
    "audio_record",
    "quote",
    "retention",
)


class StudyEvent(BaseModel):
    """A timestamped event within one run."""

    run_id: str
    timestamp: str  # ISO-8601, monotonic across the run
    stage: str
    event_type: str  # e.g. start, completion, error, stuck, help, submit, retry
    value: float | int | str | None = None
    detail: str = ""

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"非法事件时间：{value}") from exc
        return value


class ManualCorrection(BaseModel):
    """A human rewrite of one metric in a report, with full provenance."""

    run_id: str
    metric_path: str
    original: Any
    corrected: Any
    reason: str
    operator: str
    corrected_at: str = Field(default_factory=utcnow)


class DeletionRequest(BaseModel):
    participant_id: str
    scope: ConsentScope = "retention"
    requested_at: str = Field(default_factory=utcnow)
    actioned_at: str = ""
    requested_by: str = ""
    summary: str = ""


class Issue(BaseModel):
    id: str = Field(default_factory=lambda: f"issue-{uuid4().hex[:8]}")
    severity: Severity
    summary: str
    evidence: str = ""
    fix_commit: str = ""
    retest_result: str = ""
    category: Literal["observed", "subjective", "inference"] = "observed"


class Quote(BaseModel):
    participant_id: str
    round: StudyRound
    text: str
    approved: bool = False
    context: str = ""


class EvidencePackage(BaseModel):
    """The exported, anonymised competition evidence bundle."""

    generated_at: str = Field(default_factory=utcnow)
    report_version: str = "1"
    participants: list[str] = Field(default_factory=list)
    runs_index: list[dict[str, Any]] = Field(default_factory=list)
    metrics_summary: dict[str, Any] = Field(default_factory=dict)
    quotes: list[Quote] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(exclude={"generated_at"}), sort_keys=True, ensure_ascii=False)
        return sha256_hex(payload)
