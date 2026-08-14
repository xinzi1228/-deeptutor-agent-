from __future__ import annotations

import json
from pathlib import Path
import re
from typing import TypeVar

from pydantic import BaseModel

from deeptutor.services.file_io import atomic_write_json

from .models import (
    ContentRevision,
    HistoricalImpact,
    PublishedContent,
    ReviewDecision,
    SourceRecord,
    StandardConflict,
)

ModelT = TypeVar("ModelT", bound=BaseModel)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,180}$")


class ContentGovernanceStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def save_source(self, source: SourceRecord) -> SourceRecord:
        return self._save("sources", source.id, source)

    def get_source(self, source_id: str) -> SourceRecord | None:
        return self._get("sources", source_id, SourceRecord)

    def list_sources(self) -> list[SourceRecord]:
        return self._list("sources", SourceRecord)

    def save_revision(self, revision: ContentRevision) -> ContentRevision:
        return self._save("revisions", revision.id, revision)

    def get_revision(self, revision_id: str) -> ContentRevision | None:
        return self._get("revisions", revision_id, ContentRevision)

    def list_revisions(self, *, status: str | None = None) -> list[ContentRevision]:
        rows = self._list("revisions", ContentRevision)
        return [row for row in rows if status is None or row.status == status]

    def save_decision(self, decision: ReviewDecision) -> ReviewDecision:
        return self._save("decisions", decision.id, decision)

    def list_decisions(self) -> list[ReviewDecision]:
        return self._list("decisions", ReviewDecision)

    def save_conflict(self, conflict: StandardConflict) -> StandardConflict:
        return self._save("conflicts", conflict.id, conflict)

    def get_conflict(self, conflict_id: str) -> StandardConflict | None:
        return self._get("conflicts", conflict_id, StandardConflict)

    def list_conflicts(self) -> list[StandardConflict]:
        return self._list("conflicts", StandardConflict)

    def save_impact(self, impact: HistoricalImpact) -> HistoricalImpact:
        return self._save("impacts", impact.id, impact)

    def list_impacts(self) -> list[HistoricalImpact]:
        return self._list("impacts", HistoricalImpact)

    def save_published(self, published: PublishedContent) -> PublishedContent:
        content_id = self._safe_id(published.content_id)
        path = self.root / "published" / content_id / f"v{published.version}.json"
        atomic_write_json(path, published.model_dump(mode="json"))
        return published

    def list_published(self, content_id: str) -> list[PublishedContent]:
        directory = self.root / "published" / self._safe_id(content_id)
        if not directory.exists():
            return []
        rows: list[PublishedContent] = []
        for path in sorted(directory.glob("v*.json")):
            value = self._read_json(path)
            if value is not None:
                rows.append(PublishedContent.model_validate(value))
        return sorted(rows, key=lambda row: row.version)

    def _save(self, category: str, object_id: str, value: ModelT) -> ModelT:
        path = self.root / category / f"{self._safe_id(object_id)}.json"
        atomic_write_json(path, value.model_dump(mode="json"))
        return value

    def _get(self, category: str, object_id: str, model: type[ModelT]) -> ModelT | None:
        path = self.root / category / f"{self._safe_id(object_id)}.json"
        value = self._read_json(path)
        return model.model_validate(value) if value is not None else None

    def _list(self, category: str, model: type[ModelT]) -> list[ModelT]:
        directory = self.root / category
        if not directory.exists():
            return []
        rows: list[ModelT] = []
        for path in sorted(directory.glob("*.json")):
            value = self._read_json(path)
            if value is not None:
                rows.append(model.model_validate(value))
        return rows

    @staticmethod
    def _safe_id(value: str) -> str:
        if not _SAFE_ID.fullmatch(str(value or "")):
            raise ValueError("内容治理对象编号不合法")
        return str(value)

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None


__all__ = ["ContentGovernanceStore"]
