from __future__ import annotations

from pathlib import Path

from deeptutor.multi_user.context import (
    reset_current_learning_profile,
    reset_current_user,
    set_current_learning_profile,
    set_current_user,
)
from deeptutor.multi_user.models import CurrentUser, UserScope
from deeptutor.services.learning_profiles.models import ProfileAccessContext
from deeptutor.services.learning_records import LearningRecordStore
from deeptutor.services.memory.paths import memory_root
from deeptutor.services.path_service import PathService


def _user(root: Path) -> CurrentUser:
    return CurrentUser(
        id="u_test",
        username="tester",
        role="user",
        scope=UserScope(kind="user", user_id="u_test", root=root),
    )


def _access(profile_id: str) -> ProfileAccessContext:
    return ProfileAccessContext(
        owner_user_id="u_test",
        profile_id=profile_id,
        mode="student",
        actor_user_id="u_test",
        read_only=False,
    )


def test_profile_scopes_session_memory_and_learning_paths(monkeypatch, tmp_path):
    from deeptutor.multi_user import paths as mu_paths

    user = _user(tmp_path / "account")
    monkeypatch.setattr(mu_paths, "_path_services", {})
    user_token = set_current_user(user)
    profile_token = set_current_learning_profile(_access("lp_" + "a" * 24))
    try:
        service = mu_paths.get_current_path_service()
        root = service.get_workspace_dir() / "learning_profiles" / ("lp_" + "a" * 24)
        assert service.get_chat_history_db() == root / "sessions" / "chat_history.db"
        assert memory_root() == root / "memory"
        assert LearningRecordStore().file == root / "learning" / "records.jsonl"
        assert service.get_knowledge_bases_root() == user.scope.root / "knowledge_bases"
        assert service.get_settings_dir() == user.scope.root / "user" / "settings"
    finally:
        reset_current_learning_profile(profile_token)
        reset_current_user(user_token)


def test_two_profiles_resolve_to_disjoint_private_paths(monkeypatch, tmp_path):
    from deeptutor.multi_user import paths as mu_paths

    monkeypatch.setattr(mu_paths, "_path_services", {})
    user_token = set_current_user(_user(tmp_path / "account"))
    try:
        first = set_current_learning_profile(_access("lp_" + "a" * 24))
        path_a = mu_paths.get_current_path_service().get_chat_history_db()
        reset_current_learning_profile(first)
        second = set_current_learning_profile(_access("lp_" + "b" * 24))
        path_b = mu_paths.get_current_path_service().get_chat_history_db()
        reset_current_learning_profile(second)
        assert path_a != path_b
        assert "lp_" + "a" * 24 in str(path_a)
        assert "lp_" + "b" * 24 in str(path_b)
    finally:
        reset_current_user(user_token)
