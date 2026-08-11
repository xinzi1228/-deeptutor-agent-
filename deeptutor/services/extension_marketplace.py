"""Curated, per-learner extension marketplace.

Extensions are catalog entries maintained in code.  A learner can only install
or enable an approved entry; no URL, package, command, or MCP configuration is
accepted from the learner-facing API.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deeptutor.services.file_io import atomic_write_json
from deeptutor.services.learning_records import LearningRecordStore


CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "learning-path-diagram",
        "name": "学习路径图",
        "version": "1.0.0",
        "kind": "visualization",
        "description": "把你的学习计划、已完成任务和下一步整理成一张清晰的路径图。",
        "permissions": ["read_learning_records", "read_course_plan"],
        "tools": ["render_learning_path"],
        "approved": True,
    },
    {
        "id": "report-card-enhancer",
        "name": "报告卡片增强",
        "version": "1.0.0",
        "kind": "skill",
        "description": "将已保存的学习事实整理为更易读的学习小结。",
        "permissions": ["read_learning_records"],
        "tools": [],
        "approved": True,
    },
)


class ExtensionMarketplaceService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or LearningRecordStore().file.parent
        self.state_file = self.root / "extensions.json"

    def catalog(self) -> list[dict[str, Any]]:
        installed = self._state().get("installed", {})
        return [{**item, "installed": item["id"] in installed,
                 "enabled": bool(installed.get(item["id"], {}).get("enabled", False))}
                for item in CATALOG]

    def installed(self) -> list[dict[str, Any]]:
        return [item for item in self.catalog() if item["installed"]]

    def is_enabled(self, extension_id: str) -> bool:
        return any(item["id"] == extension_id and item["enabled"] for item in self.catalog())

    def install(self, extension_id: str) -> dict[str, Any]:
        entry = self._entry(extension_id)
        state = self._state()
        state.setdefault("installed", {})[extension_id] = {
            "enabled": True,
            "installed_at": datetime.now(tz=timezone.utc).isoformat(),
            "version": entry["version"],
        }
        self._save(state)
        return next(item for item in self.catalog() if item["id"] == extension_id)

    def set_enabled(self, extension_id: str, enabled: bool) -> dict[str, Any]:
        self._entry(extension_id)
        state = self._state()
        if extension_id not in state.get("installed", {}):
            raise ValueError("请先安装该扩展")
        state["installed"][extension_id]["enabled"] = enabled
        self._save(state)
        return next(item for item in self.catalog() if item["id"] == extension_id)

    def learning_path(self) -> dict[str, Any]:
        """Return a renderer-neutral diagram model (<= 9 nodes, short labels)."""
        if not self.is_enabled("learning-path-diagram"):
            raise PermissionError("学习路径图扩展尚未启用")
        from deeptutor.services.learning_workspace import LearningWorkspaceService

        workspace = LearningWorkspaceService()
        views = workspace.views()
        records = LearningRecordStore().list_records()
        completed = {str(row.get("task_id")) for row in records if row.get("task_id")}
        plan = {}
        try:
            from deeptutor.services.course_plan import CoursePlanStore
            plan = CoursePlanStore().get() or {}
        except Exception:
            pass
        modules = plan.get("modules", []) if isinstance(plan, dict) else []
        nodes: list[dict[str, str]] = [{"id": "start", "label": "当前学习", "status": "current"}]
        for index, module in enumerate(modules[:5], start=1):
            tasks = [str(task) for task in module.get("tasks", [])]
            status = "done" if tasks and all(task in completed for task in tasks) else "next"
            nodes.append({"id": f"module-{index}", "label": str(module.get("name") or f"模块 {index}")[:16], "status": status})
        if len(nodes) == 1:
            nodes.append({"id": "next", "label": "完成入门诊断", "status": "next"})
        if views.get("inbox") and len(nodes) < 8:
            nodes.append({"id": "inbox", "label": "整理学习疑问", "status": "attention"})
        if len(nodes) < 9:
            nodes.append({"id": "goal", "label": "岗位能力达成", "status": "goal"})
        edges = [{"from": nodes[index]["id"], "to": nodes[index + 1]["id"]}
                 for index in range(len(nodes) - 1)]
        return {"title": "我的学习路径", "nodes": nodes, "edges": edges,
                "notice": "状态同时用文字和图标表达，不只依赖颜色。"}

    def _entry(self, extension_id: str) -> dict[str, Any]:
        for item in CATALOG:
            if item["id"] == extension_id and item["approved"]:
                return item
        raise ValueError("扩展不存在或尚未审核")

    def _state(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {"installed": {}}
        except (OSError, json.JSONDecodeError):
            return {"installed": {}}

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.state_file, state)


__all__ = ["ExtensionMarketplaceService", "CATALOG"]
