"""Scoped learning-workspace state, rebuilds, and asset fingerprints."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Literal
import uuid

from deeptutor.services.file_io import atomic_write_json
from deeptutor.services.learning_records import LearningRecordStore

Resource = Literal["learning_record", "decision", "inbox_item", "course_asset", "derived_view"]
_READABLE: set[str] = {"learning_record", "decision", "inbox_item", "course_asset", "derived_view"}
_COACH_WRITABLE: set[str] = {"learning_record", "decision", "inbox_item"}


class LearningWorkspaceService:
    """All paths are derived from the current user's workspace, never input."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or LearningRecordStore().file.parent
        self.manifest_file = self.root / "workspace_manifest.json"

    def require_access(self, resource: Resource, action: Literal["read", "write"], *, actor: str = "coach") -> None:
        allowed = _READABLE if action == "read" else (_COACH_WRITABLE if actor == "coach" else _READABLE)
        if resource not in allowed:
            raise PermissionError(f"{actor} cannot {action} {resource}")

    def manifest(self) -> dict[str, Any]:
        current_task = self._current_task_summary()
        if not self.manifest_file.exists():
            return {"schema_version": 1, "last_rebuild": None, "assets": self.asset_versions(), "current_task": current_task}
        try:
            data = json.loads(self.manifest_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**data, "current_task": current_task}
            return {"schema_version": 1, "current_task": current_task}
        except (OSError, json.JSONDecodeError):
            return {"schema_version": 1, "last_rebuild": None, "assets": self.asset_versions(), "current_task": current_task}

    @staticmethod
    def _current_task_summary() -> dict[str, Any] | None:
        try:
            from deeptutor.multi_user.paths import get_current_learning_profile_root
            from deeptutor.services.current_learning_task.store import CurrentLearningTaskStore

            profile_root = get_current_learning_profile_root(require_unlocked=False)
            task = CurrentLearningTaskStore(profile_root).get() if profile_root else None
        except (ImportError, PermissionError, RuntimeError):
            task = None
        if task is None:
            return None
        return {
            "course_id": task.course_id,
            "task_id": task.task_id,
            "phase": task.phase,
            "mode": task.mode,
            "version": task.version,
        }

    def asset_versions(self) -> dict[str, dict[str, str | None]]:
        from deeptutor.services.path_service import get_path_service
        workspace = get_path_service().get_workspace_dir()
        candidates = {
            "task_bank": workspace / "task_bank.json",
            "competency_tree": workspace / "competency_tree.json",
        }
        out: dict[str, dict[str, str | None]] = {}
        for name, path in candidates.items():
            try:
                raw = path.read_bytes()
                out[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()}
            except OSError:
                out[name] = {"sha256": None, "updated_at": None}
        return out

    def rebuild(self, *, rebuild_course: bool = False, confirmed: bool = False) -> dict[str, Any]:
        if rebuild_course and not confirmed:
            raise ValueError("重建课程计划需要 confirmed=true")
        from deeptutor.services.knowledge_graph import KnowledgeGraphStore, _load_bank, _load_competency_tree
        records = LearningRecordStore().list_records()
        graph_store = KnowledgeGraphStore(root=self.root)
        graph = graph_store.build(tree=_load_competency_tree(), bank=_load_bank(), records=records)
        graph_store.save(graph)
        result: dict[str, Any] = {"knowledge_graph": "rebuilt", "course_plan": "preserved", "records": len(records)}
        if rebuild_course:
            from deeptutor.services.course_plan import CoursePlanStore, build_course_plan
            store = LearningRecordStore()
            CoursePlanStore().save(build_course_plan(brief=store.get_brief()))
            result["course_plan"] = "rebuilt"
        manifest = {"schema_version": 1, "last_rebuild": {"at": datetime.now(tz=timezone.utc).isoformat(), "result": result}, "assets": self.asset_versions()}
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.manifest_file, manifest)
        return result

    @property
    def inbox_file(self) -> Path:
        return self.root / "inbox.jsonl"

    def list_inbox(self, *, status: str | None = "open") -> list[dict[str, Any]]:
        self.require_access("inbox_item", "read")
        if not self.inbox_file.exists(): return []
        rows = []
        for line in self.inbox_file.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if isinstance(item, dict) and (status is None or item.get("status") == status): rows.append(item)
            except json.JSONDecodeError: continue
        return rows

    def add_inbox(self, raw_text: str, *, source: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        self.require_access("inbox_item", "write")
        text = raw_text.strip()
        if not text: raise ValueError("问题内容不能为空")
        recent = self.list_inbox(status="open")[-10:]
        if any(item.get("raw_text") == text and item.get("source") == source for item in recent):
            return {**next(item for item in recent if item.get("raw_text") == text and item.get("source") == source), "deduplicated": True}
        item = {"id": f"inbox_{uuid.uuid4().hex[:12]}", "created_at": datetime.now(tz=timezone.utc).isoformat(), "status": "open", "source": source, "raw_text": text, "context": context or {}, "suggested_type": None, "resolved_to": [], "audit": {"actor": "coach", "operation": "create"}}
        self.root.mkdir(parents=True, exist_ok=True)
        with self.inbox_file.open("a", encoding="utf-8") as handle: handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def views(self) -> dict[str, Any]:
        records = LearningRecordStore().list_records()
        mastered = LearningRecordStore().facts().get("facts", [])
        errors = []
        for record in reversed(records):
            pattern = str(record.get("error_pattern") or "").strip()
            if pattern and record.get("pattern_status") == "confirmed" and pattern not in errors: errors.append(pattern)
        completed = {str(record.get("task_id")) for record in records if record.get("task_id")}
        next_tasks: list[str] = []
        try:
            from deeptutor.services.course_plan import CoursePlanStore
            for module in (CoursePlanStore().get() or {}).get("modules", []):
                for task_id in module.get("tasks", []):
                    if task_id not in completed: next_tasks.append(task_id)
        except Exception: pass
        return {"inbox": self.list_inbox(), "mastered": mastered, "confirmed_errors": errors, "next_tasks": next_tasks[:3], "relations": {"inbox_to_task": [{"inbox_id": i["id"], "task_id": i.get("context", {}).get("task_id")} for i in self.list_inbox() if i.get("context", {}).get("task_id")]}}

    def organize_inbox(self, item_id: str, *, resolved_to: list[str]) -> dict[str, Any]:
        rows = self.list_inbox(status=None)
        found = False
        for item in rows:
            if item.get("id") == item_id:
                item["status"] = "organized"; item["resolved_to"] = resolved_to; item["organized_at"] = datetime.now(tz=timezone.utc).isoformat(); found = True
        if not found: raise ValueError("未找到待整理问题")
        from deeptutor.services.file_io import atomic_write_text
        atomic_write_text(self.inbox_file, "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n")
        return next(item for item in rows if item.get("id") == item_id)


__all__ = ["LearningWorkspaceService"]
