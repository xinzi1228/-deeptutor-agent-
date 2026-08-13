from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from deeptutor.services.file_io import atomic_write_json


@dataclass(slots=True)
class LabelStudioProfileMap:
    profile_id: str
    email_alias: str
    project_id: int | None = None
    task_map: dict[str, int] = field(default_factory=dict)
    schema_version: int = 1

    @classmethod
    def load(cls, profile_root: Path, profile_id: str) -> "LabelStudioProfileMap":
        path = Path(profile_root) / "annotation" / "label_studio_map.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("profile_id") == profile_id:
                    data["task_map"] = {str(k): int(v) for k, v in data.get("task_map", {}).items()}
                    return cls(**{key: value for key, value in data.items() if key in cls.__dataclass_fields__})
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        return cls(profile_id=profile_id, email_alias=f"profile-{profile_id}@deeptutor.invalid")

    def save(self, profile_root: Path) -> None:
        path = Path(profile_root) / "annotation" / "label_studio_map.json"
        atomic_write_json(path, asdict(self))

    def public_dict(self) -> dict[str, Any]:
        return {"project_id": self.project_id, "task_ids": list(self.task_map), "ready": bool(self.project_id)}
