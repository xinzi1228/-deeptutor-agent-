from __future__ import annotations

import json
from pathlib import Path
import re

from deeptutor.services.file_io import atomic_write_json

from .datasets import load_verified_dataset_snapshot
from .models import VisualizationArtifact

_CHART_TYPES = {"line", "bar", "pie", "doughnut", "radar", "scatter"}


class VisualizationArtifactStore:
    def __init__(self, profile_root: Path):
        self.profile_root = Path(profile_root)
        self.root = self.profile_root / "artifacts" / "visualizations"

    def save(self, artifact: VisualizationArtifact) -> Path:
        path = self.root / f"{artifact.id}.json"
        atomic_write_json(path, artifact.to_dict())
        return path

    def _path(self, artifact_id: str) -> Path:
        value = str(artifact_id or "").strip()
        if not re.fullmatch(r"viz_[a-f0-9]{32}", value):
            raise ValueError("作品编号不合法")
        return self.root / f"{value}.json"

    def get(self, artifact_id: str) -> dict | None:
        path = self._path(artifact_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def set_save_state(self, artifact_id: str, save_state: str) -> dict:
        if save_state == "session":
            save_state = "ephemeral"
        if save_state not in {"ephemeral", "saved", "learning_material"}:
            raise ValueError("不支持的作品保存状态")
        value = self.get(artifact_id)
        if value is None:
            raise FileNotFoundError("找不到该作品")
        value["save_state"] = save_state
        atomic_write_json(self._path(artifact_id), value)
        return value

    def rerender_chart(self, artifact_id: str, chart_type: str) -> dict:
        """Change presentation only; the frozen dataset and values stay intact."""

        next_type = str(chart_type or "").strip()
        if next_type not in _CHART_TYPES:
            raise ValueError("不支持的图表类型")
        value = self.get(artifact_id)
        if value is None:
            raise FileNotFoundError("找不到该作品")
        if value.get("kind") != "chart":
            raise ValueError("只有数字图表可以换图")
        dataset_ref = value.get("dataset_ref")
        if not isinstance(dataset_ref, dict) or not dataset_ref.get("sha256"):
            raise ValueError("旧版图表没有可信数据引用，不能换图")
        content = value.get("content")
        if not isinstance(content, dict):
            raise ValueError("图表内容格式不正确")
        source_ref = str(value.get("source_ref") or "")
        snapshot = load_verified_dataset_snapshot(self.profile_root, source_ref)
        if dataset_ref != snapshot.get("dataset_ref"):
            raise ValueError("作品的数据引用与可信快照不一致")
        snapshot_content = snapshot.get("content")
        if not isinstance(snapshot_content, dict):
            raise ValueError("可信数据快照内容格式不正确")
        if content.get("labels") != snapshot_content.get("labels"):
            raise ValueError("作品标签与可信数据快照不一致")
        if content.get("datasets") != snapshot_content.get("datasets"):
            raise ValueError("作品数值与可信数据快照不一致")
        next_content = dict(content)
        next_content["chart_type"] = next_type
        value["content"] = next_content
        value["render_revision"] = int(value.get("render_revision") or 0) + 1
        atomic_write_json(self._path(artifact_id), value)
        return value

    def delete(self, artifact_id: str) -> bool:
        path = self._path(artifact_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list(
        self,
        limit: int = 50,
        *,
        session_id: str | None = None,
        message_id: str | None = None,
    ) -> list[dict]:
        rows: list[dict] = []
        if not self.root.exists():
            return rows
        for path in sorted(self.root.glob("viz_*.json"), key=lambda item: item.stat().st_mtime)[-limit:]:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            if session_id is not None and value.get("session_id") != session_id:
                continue
            if message_id is not None and value.get("message_id") != message_id:
                continue
            rows.append(value)
        return rows
