from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from deeptutor.services.current_learning_task.store import CurrentLearningTaskStore
from deeptutor.services.learning_communication import (
    audit_learning_copy,
    build_learning_communication_summary,
    render_learning_report,
)
from deeptutor.services.learning_records import LearningRecordStore, LearningStats
from deeptutor.services.learning_workspace import LearningWorkspaceService

from .cache import DashboardCacheKey, StudentDashboardCache, dashboard_cache


def build_learning_report_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = build_learning_communication_summary(records)
    text = render_learning_report(summary)
    payload: dict[str, Any] = {
        "summary": summary.to_dict(),
        "text": text,
        "quality_warnings": audit_learning_copy(text, kind="report", summary=summary),
        "presentation": "plain",
        "cards": [],
    }
    from deeptutor.services.extension_marketplace import ExtensionMarketplaceService

    if ExtensionMarketplaceService().is_enabled("report-card-enhancer"):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        payload["presentation"] = "cards"
        payload["cards"] = [
            {
                "title": line.split("：", 1)[0],
                "content": line.split("：", 1)[1] if "：" in line else line,
            }
            for line in lines
        ]
    return payload


class StudentDashboardService:
    """Build versioned, rebuildable projections for the two student first screens."""

    def __init__(
        self,
        *,
        profile_id: str,
        profile_root: Path,
        profile_data_version: int = 1,
        store: LearningRecordStore | None = None,
        stats: LearningStats | None = None,
        workspace: LearningWorkspaceService | None = None,
        task_store: CurrentLearningTaskStore | None = None,
        cache: StudentDashboardCache | None = None,
        report_builder: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None,
    ) -> None:
        self.profile_id = str(profile_id)
        self.profile_root = Path(profile_root)
        self.profile_data_version = max(1, int(profile_data_version))
        self.store = store or LearningRecordStore()
        self.stats = stats or LearningStats(self.store)
        self.workspace = workspace or LearningWorkspaceService(root=self.store.file.parent)
        self.task_store = task_store or CurrentLearningTaskStore(self.profile_root)
        self.cache = cache or dashboard_cache
        self.report_builder = report_builder or build_learning_report_payload

    def home(self) -> dict[str, Any]:
        return self._get_or_build("home", self._build_home)

    def growth(self) -> dict[str, Any]:
        return self._get_or_build("growth", self._build_growth)

    def _get_or_build(
        self, view: str, builder: Callable[[Any], dict[str, Any]]
    ) -> dict[str, Any]:
        task = self.task_store.get()
        task_version = int(getattr(task, "version", 0) or 0)
        learning_data_version = self._learning_data_version()
        key = DashboardCacheKey(
            profile_id=self.profile_id,
            view=view,
            profile_data_version=self.profile_data_version,
            learning_data_version=learning_data_version,
            task_version=task_version,
        )

        def wrapped() -> dict[str, Any]:
            value = builder(task)
            value["version"] = {
                "profile_id": self.profile_id,
                "profile_data_version": self.profile_data_version,
                "learning_data_version": learning_data_version,
                "task_version": task_version,
            }
            value["generated_at"] = datetime.now(timezone.utc).isoformat()
            return value

        return self.cache.get_or_build(key, wrapped)

    def _build_home(self, task: Any) -> dict[str, Any]:
        records = self.store.list_records()
        return {
            "task": task.model_dump(mode="json") if task is not None else None,
            "overview": self.stats.overview(),
            "report": self.report_builder(records),
        }

    def _build_growth(self, _task: Any) -> dict[str, Any]:
        records = self.store.list_records()
        return {
            "overview": self.stats.overview(),
            "report": self.report_builder(records),
            "foresight": self.stats.foresight_stats(),
        }

    def _learning_data_version(self) -> str:
        digest = hashlib.sha256()
        digest.update(f"profile:{self.profile_data_version}".encode())
        candidates = (
            self.store.file,
            self.store.file.parent / "facts.jsonl",
            self.store.file.parent / "inbox.jsonl",
            self.store.file.parent / "extensions.json",
        )
        for path in candidates:
            digest.update(str(path.name).encode())
            try:
                digest.update(path.read_bytes())
            except OSError:
                digest.update(b"<missing>")
        assets = self.workspace.asset_versions()
        digest.update(json.dumps(assets, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        return digest.hexdigest()


def get_student_dashboard_service() -> StudentDashboardService:
    from deeptutor.multi_user.context import require_learning_profile_access
    from deeptutor.multi_user.paths import (
        get_current_learning_profile_root,
        get_current_path_service,
    )
    from deeptutor.services.learning_profiles.store import LearningProfileStore

    access = require_learning_profile_access()
    profile_root = get_current_learning_profile_root(require_unlocked=True)
    assert profile_root is not None
    account_workspace = get_current_path_service().get_workspace_dir()
    profile = LearningProfileStore(account_workspace).get(
        access.owner_user_id, access.profile_id
    )
    return StudentDashboardService(
        profile_id=access.profile_id,
        profile_root=profile_root,
        profile_data_version=profile.data_version if profile else 1,
    )


__all__ = [
    "StudentDashboardService",
    "build_learning_report_payload",
    "get_student_dashboard_service",
]
