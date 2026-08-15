"""Extension marketplace whitelist + high-risk confirmation policy tests.

Covers task 4.3 policy:
  * Students can only install/enable extensions on their course-assigned
    whitelist; installing a new extension is an admin action.
  * Unverified extensions are disabled by default and only usable in dev mode;
    competition mode loads a fixed whitelist with locked versions and isolates
    dev-mode entries.
  * High-risk changes require explicit confirmation and write a versioned
    rollback record.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.services.extension_marketplace import (
    CATALOG,
    DEFAULT_POLICY,
    ExtensionMarketplaceService,
    is_competition_mode,
    load_extension_policy,
)


def _service(tmp_path: Path) -> ExtensionMarketplaceService:
    return ExtensionMarketplaceService(root=tmp_path)


def _write_policy(tmp_path: Path, *, mode: str, locked: dict | None = None) -> None:
    (tmp_path / "extension_policy.json").write_text(
        __import__("json").dumps({"version": 1, "mode": mode, "locked": locked or {}}),
        encoding="utf-8",
    )


# ── Policy file parsing ───────────────────────────────────────────────────


def test_default_policy_is_dev_mode_with_empty_lock(tmp_path: Path) -> None:
    policy = load_extension_policy(tmp_path / "missing.json")
    assert policy["mode"] == "dev"
    assert is_competition_mode(policy) is False


def test_competition_policy_parses_locked_whitelist(tmp_path: Path) -> None:
    _write_policy(tmp_path, mode="competition", locked={"learning-path-diagram": "1.0.0"})
    policy = load_extension_policy(tmp_path / "extension_policy.json")
    assert is_competition_mode(policy) is True
    assert policy["locked"]["learning-path-diagram"] == "1.0.0"


# ── Whitelist gating for students ────────────────────────────────────────


def test_student_cannot_install_unassigned_extension(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(PermissionError, match="未分配"):
        service.install("learning-path-diagram", actor_is_admin=False, assigned_ids=set())


def test_student_can_install_assigned_approved_extension(tmp_path: Path) -> None:
    service = _service(tmp_path)
    installed = service.install(
        "learning-path-diagram",
        actor_is_admin=False,
        assigned_ids={"learning-path-diagram"},
    )
    assert installed["installed"] is True
    assert installed["enabled"] is True


def test_student_cannot_enable_unassigned_extension(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(PermissionError, match="未分配"):
        service.set_enabled(
            "learning-path-diagram", True, actor_is_admin=False, assigned_ids=set()
        )


def test_admin_can_install_without_whitelist(tmp_path: Path) -> None:
    service = _service(tmp_path)
    installed = service.install("learning-path-diagram", actor_is_admin=True)
    assert installed["installed"] is True


# ── Unverified extensions ────────────────────────────────────────────────


def test_unverified_install_requires_confirmation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ValueError, match="二次确认"):
        service.install("experimental-vision-tagger", actor_is_admin=True)


def test_unverified_install_confirmed_but_default_disabled(tmp_path: Path) -> None:
    service = _service(tmp_path)
    installed = service.install(
        "experimental-vision-tagger", actor_is_admin=True, confirmed=True
    )
    # Unverified extensions are not enabled just by installing them.
    assert installed["installed"] is True
    assert installed["enabled"] is False


def test_unverified_enable_requires_confirmation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.install("experimental-vision-tagger", actor_is_admin=True, confirmed=True)
    with pytest.raises(ValueError, match="二次确认"):
        service.set_enabled("experimental-vision-tagger", True, actor_is_admin=True)


def test_unverified_student_install_forbidden(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(PermissionError, match="管理员"):
        service.install(
            "experimental-vision-tagger",
            actor_is_admin=False,
            assigned_ids={"experimental-vision-tagger"},
            confirmed=True,
        )


# ── Competition isolation ────────────────────────────────────────────────


def test_competition_mode_blocks_non_whitelisted_approved_extension(tmp_path: Path) -> None:
    _write_policy(tmp_path, mode="competition", locked={"report-card-enhancer": "1.0.0"})
    service = _service(tmp_path)
    # learning-path-diagram is approved but NOT on the locked whitelist.
    with pytest.raises(PermissionError, match="白名单"):
        service.install("learning-path-diagram", actor_is_admin=True)


def test_competition_mode_blocks_version_mismatch(tmp_path: Path) -> None:
    _write_policy(tmp_path, mode="competition", locked={"learning-path-diagram": "9.9.9"})
    service = _service(tmp_path)
    with pytest.raises(PermissionError, match="锁定版本"):
        service.install("learning-path-diagram", actor_is_admin=True)


def test_competition_mode_allows_locked_approved_extension(tmp_path: Path) -> None:
    _write_policy(tmp_path, mode="competition", locked={"learning-path-diagram": "1.0.0"})
    service = _service(tmp_path)
    installed = service.install("learning-path-diagram", actor_is_admin=True)
    assert installed["installed"] is True


# ── Version + rollback record ────────────────────────────────────────────


def test_high_risk_change_writes_journal_with_version(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.install("experimental-vision-tagger", actor_is_admin=True, confirmed=True)
    changes = service.change_log()
    assert len(changes) == 1
    record = changes[0]
    assert record["action"] == "install"
    assert record["version"] == "0.1.0"
    assert record["confirmed"] is True
    assert record["extension_id"] == "experimental-vision-tagger"


def test_rollback_snapshot_returns_latest_journal_entry(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.install("learning-path-diagram", actor_is_admin=True)
    service.set_enabled("learning-path-diagram", False, actor_is_admin=True)
    snapshot = service.rollback_snapshot("learning-path-diagram")
    assert snapshot is not None
    assert snapshot["action"] == "disable"
    assert snapshot["enabled_was"] is True


def test_no_journal_when_nothing_recorded(tmp_path: Path) -> None:
    service = _service(tmp_path)
    assert service.change_log() == []
    assert service.rollback_snapshot("learning-path-diagram") is None


# ── Catalog sanity ───────────────────────────────────────────────────────


def test_catalog_entries_carry_review_status() -> None:
    assert {item["id"] for item in CATALOG} >= {
        "learning-path-diagram",
        "report-card-enhancer",
        "experimental-vision-tagger",
    }
    statuses = {item["review_status"] for item in CATALOG}
    assert statuses <= {"approved", "unverified"}
    assert "unverified" in statuses


def test_default_policy_constant_shape() -> None:
    assert DEFAULT_POLICY["mode"] == "dev"
    assert DEFAULT_POLICY["locked"] == {}
