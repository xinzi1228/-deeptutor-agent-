from __future__ import annotations

import json

from deeptutor.services.learning_profiles.migration import LearningProfileMigrator
from deeptutor.services.learning_profiles.store import LearningProfileStore


def test_migration_copies_and_verifies_without_deleting_sources(tmp_path):
    workspace = tmp_path / "user" / "workspace"
    workspace.mkdir(parents=True)
    (workspace.parent / "chat_history.db").write_bytes(b"sqlite-test")
    (workspace / "learning").mkdir()
    (workspace / "learning" / "records.jsonl").write_text('{"type":"diagnosis"}\n', encoding="utf-8")
    (workspace / "memory" / "L3").mkdir(parents=True)
    (workspace / "memory" / "L3" / "recent.md").write_text("old memory", encoding="utf-8")
    profile = LearningProfileStore(workspace).create("u_one", "原有学习档案", "1234")

    report = LearningProfileMigrator(workspace).migrate(profile.id)
    root = workspace / "learning_profiles" / profile.id

    assert report["status"] == "verified"
    assert report["source_preserved"] is True
    assert (root / "sessions" / "chat_history.db").read_bytes() == b"sqlite-test"
    assert (root / "learning" / "records.jsonl").read_text(encoding="utf-8") == '{"type":"diagnosis"}\n'
    assert (root / "memory" / "L3" / "recent.md").read_text(encoding="utf-8") == "old memory"
    assert (workspace.parent / "chat_history.db").exists()
    assert (workspace / "learning" / "records.jsonl").exists()


def test_migration_is_idempotent(tmp_path):
    workspace = tmp_path / "user" / "workspace"
    workspace.mkdir(parents=True)
    (workspace.parent / "chat_history.db").write_bytes(b"db")
    profile = LearningProfileStore(workspace).create("u_one", "原有学习档案", "1234")
    migrator = LearningProfileMigrator(workspace)
    first = migrator.migrate(profile.id)
    second = migrator.migrate(profile.id)
    assert first["status"] == "verified"
    assert second["idempotent"] is True


def test_migration_reports_conflict_and_preserves_both(tmp_path):
    workspace = tmp_path / "user" / "workspace"
    workspace.mkdir(parents=True)
    (workspace.parent / "chat_history.db").write_bytes(b"legacy")
    profile = LearningProfileStore(workspace).create("u_one", "档案", "1234")
    target = workspace / "learning_profiles" / profile.id / "sessions" / "chat_history.db"
    target.write_bytes(b"new")
    report = LearningProfileMigrator(workspace).migrate(profile.id)
    assert report["status"] == "conflict"
    assert target.read_bytes() == b"new"
    assert (workspace.parent / "chat_history.db").read_bytes() == b"legacy"


def test_dry_run_does_not_copy_or_write_marker(tmp_path):
    workspace = tmp_path / "user" / "workspace"
    workspace.mkdir(parents=True)
    (workspace.parent / "chat_history.db").write_bytes(b"db")
    profile = LearningProfileStore(workspace).create("u_one", "档案", "1234")
    report = LearningProfileMigrator(workspace).migrate(profile.id, dry_run=True)
    root = workspace / "learning_profiles" / profile.id
    assert report["mode"] == "dry_run"
    assert not (root / "sessions" / "chat_history.db").exists()
    assert not (root / "migration-v1.json").exists()
