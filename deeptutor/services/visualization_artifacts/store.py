from __future__ import annotations

import json
from pathlib import Path
import re

from deeptutor.services.file_io import atomic_write_json

from .models import VisualizationArtifact


class VisualizationArtifactStore:
    def __init__(self, profile_root: Path):
        self.root = Path(profile_root) / "artifacts" / "visualizations"

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
        if save_state not in {"session", "saved", "learning_material"}:
            raise ValueError("不支持的作品保存状态")
        value = self.get(artifact_id)
        if value is None:
            raise FileNotFoundError("找不到该作品")
        value["save_state"] = save_state
        atomic_write_json(self._path(artifact_id), value)
        return value

    def delete(self, artifact_id: str) -> bool:
        path = self._path(artifact_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list(self, limit: int = 50) -> list[dict]:
        rows: list[dict] = []
        if not self.root.exists():
            return rows
        for path in sorted(self.root.glob("viz_*.json"), key=lambda item: item.stat().st_mtime)[-limit:]:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                rows.append(value)
        return rows
