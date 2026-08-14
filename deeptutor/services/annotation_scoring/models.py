from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AnnotationScoreResult:
    metrics: dict[str, Any]
    report: str
    rule_version: str
    reference_version: str
    score_hash: str

