"""Curated, per-learner extension marketplace.

Extensions are catalog entries maintained in code.  A learner can only install
or enable an approved entry that an admin has assigned to their grant
whitelist; no URL, package, command, or MCP configuration is accepted from the
learner-facing API.

Policy rules (task 4.3):
  * Every entry carries a ``review_status`` (``approved`` / ``unverified``).
  * Students can only install / enable extensions on their course-assigned
    whitelist; installing a brand-new extension is an admin action.
  * Unverified extensions are disabled by default and only usable in dev mode;
    competition mode loads a fixed whitelist with locked versions and isolates
    dev-mode entries completely.
  * High-risk changes (installing an unverified entry, enabling it, or any
    install outside a locked competition whitelist) require explicit
    ``confirmed=True`` and record a version + rollback snapshot.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
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
        "review_status": "approved",
    },
    {
        "id": "report-card-enhancer",
        "name": "报告卡片增强",
        "version": "1.0.0",
        "kind": "skill",
        "description": "将已保存的学习事实整理为更易读的学习小结。",
        "permissions": ["read_learning_records"],
        "tools": [],
        "review_status": "approved",
    },
    {
        "id": "experimental-vision-tagger",
        "name": "实验性视觉打标",
        "version": "0.1.0",
        "kind": "skill",
        "description": "未经审核的实验性扩展；仅开发模式可用，默认禁用。",
        "permissions": ["read_learning_records"],
        "tools": [],
        "review_status": "unverified",
    },
)

COMPETITION_POLICY_FILENAME = "extension_policy.json"
DEFAULT_POLICY: dict[str, Any] = {
    "version": 1,
    "mode": "dev",  # "dev" | "competition"
    "locked": {},  # extension_id -> version string; competition whitelist
}


def load_extension_policy(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_POLICY)
    if not isinstance(raw, dict):
        return dict(DEFAULT_POLICY)
    return {
        "version": 1,
        "mode": str(raw.get("mode") or "dev"),
        "locked": raw.get("locked") if isinstance(raw.get("locked"), dict) else {},
    }


def is_competition_mode(policy: dict[str, Any]) -> bool:
    return str(policy.get("mode") or "dev").lower() == "competition"


class ExtensionMarketplaceService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or LearningRecordStore().file.parent
        self.state_file = self.root / "extensions.json"
        self.changes_file = self.root / "extensions_changes.jsonl"
        self.policy_file = self.root / COMPETITION_POLICY_FILENAME

    # ── read helpers ────────────────────────────────────────────────────

    def policy(self) -> dict[str, Any]:
        return load_extension_policy(self.policy_file)

    def catalog(self) -> list[dict[str, Any]]:
        installed = self._state().get("installed", {})
        return [
            {**item, "installed": item["id"] in installed,
             "enabled": bool(installed.get(item["id"], {}).get("enabled", False))}
            for item in CATALOG
        ]

    def installed(self) -> list[dict[str, Any]]:
        return [item for item in self.catalog() if item["installed"]]

    def is_enabled(self, extension_id: str) -> bool:
        return any(item["id"] == extension_id and item["enabled"] for item in self.catalog())

    # ── policy-aware install / enable ───────────────────────────────────

    def install(
        self,
        extension_id: str,
        *,
        actor_is_admin: bool = True,
        assigned_ids: set[str] | None = None,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        entry = self._entry(extension_id)
        policy = self.policy()
        competition = is_competition_mode(policy)

        if competition:
            locked_version = (policy.get("locked") or {}).get(extension_id)
            if not locked_version or str(locked_version) != str(entry["version"]):
                raise PermissionError("竞赛配置仅加载固定白名单与锁定版本")
        elif entry["review_status"] != "approved":
            # Dev mode may import unverified extensions but only with an
            # explicit confirmation; they default disabled.
            if not confirmed:
                raise ValueError("未审核扩展属于高风险变更，需要二次确认")
            if not actor_is_admin:
                raise PermissionError("未审核扩展仅允许管理员安装")

        if not actor_is_admin and not (assigned_ids and extension_id in assigned_ids):
            raise PermissionError("扩展未分配给你，不能安装")

        state = self._state()
        state.setdefault("installed", {})[extension_id] = {
            "enabled": entry["review_status"] == "approved",
            "installed_at": datetime.now(tz=timezone.utc).isoformat(),
            "version": entry["version"],
        }
        self._save(state)
        self._record_change(
            extension_id,
            action="install",
            version=entry["version"],
            from_version=None,
            confirmed=confirmed,
            policy_mode=policy.get("mode"),
        )
        return next(item for item in self.catalog() if item["id"] == extension_id)

    def set_enabled(
        self,
        extension_id: str,
        enabled: bool,
        *,
        actor_is_admin: bool = True,
        assigned_ids: set[str] | None = None,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        entry = self._entry(extension_id)
        policy = self.policy()
        competition = is_competition_mode(policy)

        if competition:
            locked_version = (policy.get("locked") or {}).get(extension_id)
            if not locked_version or str(locked_version) != str(entry["version"]):
                raise PermissionError("竞赛配置仅加载固定白名单与锁定版本")

        if not actor_is_admin and not (assigned_ids and extension_id in assigned_ids):
            raise PermissionError("扩展未分配给你，不能启用或停用")

        if enabled and entry["review_status"] != "approved" and not confirmed:
            raise ValueError("启用未审核扩展属于高风险变更，需要二次确认")

        state = self._state()
        if extension_id not in state.get("installed", {}):
            raise ValueError("请先安装该扩展")
        previous_enabled = bool(state["installed"][extension_id].get("enabled"))
        state["installed"][extension_id]["enabled"] = enabled
        state["installed"][extension_id]["version"] = entry["version"]
        self._save(state)
        self._record_change(
            extension_id,
            action="enable" if enabled else "disable",
            version=entry["version"],
            from_version=None,
            confirmed=confirmed,
            policy_mode=policy.get("mode"),
            enabled_was=previous_enabled,
        )
        return next(item for item in self.catalog() if item["id"] == extension_id)

    # ── change journal (version + rollback record) ─────────────────────

    def _record_change(
        self,
        extension_id: str,
        *,
        action: str,
        version: str,
        from_version: str | None,
        confirmed: bool,
        policy_mode: Any,
        enabled_was: bool | None = None,
    ) -> None:
        record = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "extension_id": extension_id,
            "action": action,
            "version": version,
            "from_version": from_version,
            "confirmed": confirmed,
            "policy_mode": str(policy_mode),
        }
        if enabled_was is not None:
            record["enabled_was"] = enabled_was
        self.changes_file.parent.mkdir(parents=True, exist_ok=True)
        with self.changes_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def change_log(self, limit: int = 20) -> list[dict[str, Any]]:
        try:
            rows = [
                json.loads(line)
                for line in self.changes_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError):
            return []
        return rows[-limit:]

    def rollback_snapshot(self, extension_id: str) -> dict[str, Any] | None:
        """Latest journal entry for the extension = a versioned rollback record."""
        entries = [row for row in self.change_log(1000) if row.get("extension_id") == extension_id]
        return entries[-1] if entries else None

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
            if item["id"] == extension_id:
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


__all__ = [
    "CATALOG",
    "COMPETITION_POLICY_FILENAME",
    "DEFAULT_POLICY",
    "ExtensionMarketplaceService",
    "is_competition_mode",
    "load_extension_policy",
]
