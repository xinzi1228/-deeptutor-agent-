from __future__ import annotations

import json
from pathlib import Path

from deeptutor.services.file_io import atomic_write_json

from .models import VisualizationArtifact


class VisualizationArtifactStore:
    def __init__(self, profile_root: Path):
        self.root = Path(profile_root) / "artifacts" / "visualizations"

    def save(self, artifact: VisualizationArtifact) -> Path:
        path = self.root / f"{artifact.id}.json"
        atomic_write_json(path, artifact.to_dict())
        return path

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
