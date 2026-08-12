from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
from typing import Any

from deeptutor.services.file_io import atomic_write_json

from .store import LearningProfileStore

MIGRATION_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    root = path.parent if path.is_file() else path
    return [
        {
            "relative_path": item.name if path.is_file() else item.relative_to(root).as_posix(),
            "bytes": item.stat().st_size,
            "sha256": _sha256(item),
        }
        for item in files
    ]


class LearningProfileMigrator:
    """Copy legacy private learning data into a profile without deleting source."""

    def __init__(self, account_workspace: Path):
        self.account_workspace = Path(account_workspace)
        self.account_user_root = self.account_workspace.parent
        self.store = LearningProfileStore(self.account_workspace)

    def _sources(self) -> dict[str, tuple[Path, str]]:
        return {
            "sessions": (self.account_user_root / "chat_history.db", "sessions/chat_history.db"),
            "memory": (self.account_workspace / "memory", "memory"),
            "learning": (self.account_workspace / "learning", "learning"),
            "annotation": (self.account_workspace / "annotation", "annotation"),
        }

    def migrate(self, profile_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        target_root = self.store.ensure_profile_dirs(profile_id)
        marker = target_root / "migration-v1.json"
        if marker.exists() and not dry_run:
            import json

            try:
                existing = json.loads(marker.read_text(encoding="utf-8"))
                if existing.get("status") == "verified":
                    return {**existing, "idempotent": True}
            except (OSError, json.JSONDecodeError):
                pass

        operations: list[dict[str, Any]] = []
        conflicts: list[str] = []
        for name, (source, target_relative) in self._sources().items():
            source_files = _inventory(source)
            if not source_files:
                operations.append({"resource": name, "source_exists": False, "files": 0, "bytes": 0})
                continue
            destination = target_root / target_relative
            if source.is_file():
                if destination.exists() and _sha256(destination) != _sha256(source):
                    conflicts.append(target_relative)
                elif not dry_run and not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
            else:
                for source_file in sorted(item for item in source.rglob("*") if item.is_file()):
                    relative = source_file.relative_to(source)
                    target_file = destination / relative
                    if target_file.exists() and _sha256(target_file) != _sha256(source_file):
                        conflicts.append((Path(target_relative) / relative).as_posix())
                        continue
                    if not dry_run and not target_file.exists():
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_file, target_file)
            operations.append(
                {
                    "resource": name,
                    "source_exists": True,
                    "files": len(source_files),
                    "bytes": sum(item["bytes"] for item in source_files),
                    "source_inventory": source_files,
                }
            )

        verified = not conflicts
        if verified and not dry_run:
            for _name, (source, target_relative) in self._sources().items():
                if not source.exists():
                    continue
                destination = target_root / target_relative
                if _inventory(source) != _inventory(destination):
                    verified = False
                    conflicts.append(target_relative)

        report = {
            "schema_version": 1,
            "migration_version": MIGRATION_VERSION,
            "profile_id": profile_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mode": "dry_run" if dry_run else "copy_and_verify",
            "status": "verified" if verified else "conflict",
            "source_preserved": True,
            "operations": operations,
            "conflicts": sorted(set(conflicts)),
        }
        if not dry_run:
            atomic_write_json(marker, report)
        return report
