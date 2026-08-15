"""Onboarding resume state machine tests.

Covers the fixed-order wizard, skip/resume/retest actions, stale degradation
when dependency config changes, legacy payload compatibility, and admin-only
API access. The state machine itself lives in
``deeptutor/services/onboarding`` (pure, I/O-free transitions); the router
tests exercise the wiring in ``capability_center``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from deeptutor.api.routers import capability_center
from deeptutor.services.onboarding import (
    ALL_STEP_KEYS,
    CORE_STEPS,
    OPTIONAL_STEPS,
    apply_action,
    current_step,
    default_state,
    is_terminal,
    legacy_int_to_key,
    mark_stale,
)


class FakeUser:
    is_admin = True


def test_fixed_wizard_order_matches_design() -> None:
    assert [key for key, _ in CORE_STEPS] == [
        "account_security",
        "llm",
        "embedding",
        "knowledge_base",
        "label_studio",
        "health_check",
    ]
    assert [key for key, _ in OPTIONAL_STEPS] == ["imagegen", "mcp", "skill"]


def test_default_state_starts_at_first_core_step() -> None:
    state = default_state()
    assert current_step(state) == "account_security"
    assert all(step["status"] == "not_started" for step in state["steps"].values())
    assert state["dismissed"] is False


def test_done_advances_resume_to_next_pending_step() -> None:
    state = default_state()
    state = apply_action(state, "account_security", "done")
    assert current_step(state) == "llm"
    state = apply_action(state, "llm", "done")
    state = apply_action(state, "embedding", "done")
    assert current_step(state) == "knowledge_base"


def test_skip_is_terminal_and_preserves_order() -> None:
    state = default_state()
    state = apply_action(state, "account_security", "skip")
    assert is_terminal("skipped")
    assert current_step(state) == "llm"


def test_retest_moves_step_back_to_running() -> None:
    state = default_state()
    state = apply_action(state, "account_security", "done", fingerprint="abc")
    state = apply_action(state, "account_security", "retest")
    assert state["steps"]["account_security"]["status"] == "running"
    assert state["steps"]["account_security"]["fingerprint"] == ""
    assert current_step(state) == "account_security"


def test_resume_marks_step_running_for_manual_continuation() -> None:
    state = default_state()
    state = apply_action(state, "knowledge_base", "resume")
    assert state["steps"]["knowledge_base"]["status"] == "running"


def test_dismiss_hides_wizard() -> None:
    state = default_state()
    state = apply_action(state, "account_security", "dismiss")
    assert state["dismissed"] is True


def test_unknown_step_or_action_rejected() -> None:
    state = default_state()
    with pytest.raises(ValueError):
        apply_action(state, "not-a-step", "done")
    with pytest.raises(ValueError):
        apply_action(state, "llm", "explode")


def test_passed_step_becomes_stale_when_dependency_changes() -> None:
    state = default_state()
    state = apply_action(state, "account_security", "done", fingerprint="sec-1")
    state = apply_action(state, "llm", "done", fingerprint="model-A")
    state = apply_action(state, "embedding", "done", fingerprint="emb-1")
    # llm's dependency changed → it must degrade to stale; embedding stays passed.
    stale = mark_stale(state, {"llm": "model-B", "embedding": "emb-1"})
    assert stale["steps"]["llm"]["status"] == "stale"
    assert stale["steps"]["embedding"]["status"] == "passed"
    # A stale step is not terminal → the wizard resumes there.
    assert current_step(stale) == "llm"


def test_stale_step_not_counted_as_completed() -> None:
    state = default_state()
    state = apply_action(state, "llm", "done", fingerprint="model-A")
    stale = mark_stale(state, {"llm": "model-B"})
    assert stale["steps"]["llm"]["status"] == "stale"
    assert stale["steps"]["llm"]["status"] not in {"passed", "skipped"}


def test_legacy_int_mapping_covers_core_steps() -> None:
    assert legacy_int_to_key(1) == "account_security"
    assert legacy_int_to_key(6) == "health_check"
    # Out-of-range legacy numbers clamp safely.
    assert legacy_int_to_key(99) == "health_check"
    assert legacy_int_to_key(0) == "account_security"


def test_default_state_has_all_core_and_optional_steps() -> None:
    state = default_state()
    assert set(state["steps"].keys()) == set(ALL_STEP_KEYS)
    for key in ALL_STEP_KEYS:
        assert "status" in state["steps"][key]


# ── Router wiring ─────────────────────────────────────────────────────────


def _admin_router_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(capability_center, "get_current_user", lambda: FakeUser())
    monkeypatch.setattr(
        capability_center, "_live_onboarding_fingerprints", lambda: {}
    )

    class FakePathService:
        def get_settings_file(self, name: str) -> Path:
            return tmp_path / f"{name}.json"

    monkeypatch.setattr(capability_center, "get_current_path_service", lambda: FakePathService())
    return tmp_path


def test_router_get_onboarding_requires_admin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(capability_center, "get_current_user", lambda: FakeUser())
    monkeypatch.setattr(
        capability_center, "_live_onboarding_fingerprints", lambda: {}
    )

    class FakePathService:
        def get_settings_file(self, name: str) -> Path:
            return tmp_path / f"{name}.json"

    monkeypatch.setattr(capability_center, "get_current_path_service", lambda: FakePathService())

    import asyncio

    result = asyncio.run(capability_center.get_onboarding())
    assert result["current_step"] == "account_security"
    assert "steps" in result


def test_router_get_onboarding_rejects_non_admin(tmp_path, monkeypatch) -> None:
    class NonAdmin:
        is_admin = False

    monkeypatch.setattr(capability_center, "get_current_user", lambda: NonAdmin())
    monkeypatch.setattr(
        capability_center, "_live_onboarding_fingerprints", lambda: {}
    )

    class FakePathService:
        def get_settings_file(self, name: str) -> Path:
            return tmp_path / f"{name}.json"

    monkeypatch.setattr(capability_center, "get_current_path_service", lambda: FakePathService())

    import asyncio

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(capability_center.get_onboarding())
    assert exc_info.value.status_code == 403


def test_router_put_onboarding_resumes_and_persists(tmp_path, monkeypatch) -> None:
    _admin_router_context(tmp_path, monkeypatch)
    import asyncio

    from deeptutor.services.onboarding import save_state

    path = tmp_path / "capability_center.json"
    save_state(path, default_state())

    update = capability_center.OnboardingUpdate(step_key="account_security", action="done")
    result = asyncio.run(capability_center.update_onboarding(update))
    assert result["current_step"] == "llm"
    assert result["completed"] == ["account_security"]

    # Reloading from disk keeps the resume point.
    reloaded = asyncio.run(capability_center.get_onboarding())
    assert reloaded["current_step"] == "llm"


def test_router_put_onboarding_legacy_payload_maps_to_core(tmp_path, monkeypatch) -> None:
    _admin_router_context(tmp_path, monkeypatch)
    import asyncio

    from deeptutor.services.onboarding import save_state

    path = tmp_path / "capability_center.json"
    save_state(path, default_state())

    update = capability_center.OnboardingUpdate(
        step=2, completed=[1, 2], skipped=[], dismissed=False
    )
    result = asyncio.run(capability_center.update_onboarding(update))
    # Legacy 1,2 → account_security, llm.
    assert result["completed"] == ["account_security", "llm"]
    assert result["current_step"] == "embedding"


def test_router_put_onboarding_rejects_unknown_step(tmp_path, monkeypatch) -> None:
    _admin_router_context(tmp_path, monkeypatch)
    import asyncio

    from fastapi import HTTPException

    from deeptutor.services.onboarding import save_state

    path = tmp_path / "capability_center.json"
    save_state(path, default_state())

    update = capability_center.OnboardingUpdate(step_key="nope", action="done")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(capability_center.update_onboarding(update))
    assert exc_info.value.status_code == 400
