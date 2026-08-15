from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from deeptutor.api.routers import learning_profiles as router_module
from deeptutor.multi_user.context import reset_current_user, set_current_user
from deeptutor.multi_user.models import CurrentUser, UserScope


def _client(tmp_path, monkeypatch, *, role: str = "user") -> TestClient:
    user = CurrentUser(
        id="u_test",
        username="tester",
        role=role,
        scope=UserScope(kind="user", user_id="u_test", root=tmp_path),
    )

    async def fake_auth():
        set_current_user(user)
        return None

    monkeypatch.setattr(router_module, "get_current_path_service", lambda: _Paths(tmp_path))
    app = FastAPI()
    app.dependency_overrides[router_module.require_auth] = fake_auth
    app.dependency_overrides[router_module.require_admin] = fake_auth
    app.include_router(router_module.router, prefix="/api/v1/learning-profiles")
    return TestClient(app)


class _Paths:
    def __init__(self, root):
        self.root = root

    def get_workspace_dir(self):
        return self.root / "workspace"


def test_profile_create_unlock_active_and_lock(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        created = client.post("/api/v1/learning-profiles", json={"name": "小明", "pin": "1234"})
        assert created.status_code == 201
        profile_id = created.json()["id"]
        assert "pin_hash" not in created.json()

        unlocked = client.post(
            f"/api/v1/learning-profiles/{profile_id}/unlock", json={"pin": "1234"}
        )
        assert unlocked.status_code == 200
        assert unlocked.cookies.get(router_module.COOKIE_NAME)

        listed = client.get("/api/v1/learning-profiles")
        assert listed.status_code == 200
        assert listed.json()["profiles"][0]["id"] == profile_id

        locked = client.post("/api/v1/learning-profiles/lock")
        assert locked.status_code == 200
        assert locked.json() == {"ok": True}


def test_cross_account_profile_is_not_visible(tmp_path, monkeypatch):
    store = router_module.LearningProfileStore(tmp_path / "workspace")
    foreign = store.create("u_other", "别人", "1234")
    with _client(tmp_path, monkeypatch) as client:
        response = client.post(
            f"/api/v1/learning-profiles/{foreign.id}/unlock", json={"pin": "1234"}
        )
    assert response.status_code == 404


def test_wrong_pin_does_not_set_grant_cookie(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        profile_id = client.post(
            "/api/v1/learning-profiles", json={"name": "小明", "pin": "1234"}
        ).json()["id"]
        response = client.post(
            f"/api/v1/learning-profiles/{profile_id}/unlock", json={"pin": "9999"}
        )
    assert response.status_code == 401
    assert response.cookies.get(router_module.COOKIE_NAME) is None


def test_impersonation_requires_reason_and_explicit_scope(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch, role="admin") as client:
        profile_id = client.post(
            "/api/v1/learning-profiles", json={"name": "小明", "pin": "1234"}
        ).json()["id"]
        missing = client.post(f"/api/v1/learning-profiles/{profile_id}/impersonate", json={})
        forbidden = client.post(
            f"/api/v1/learning-profiles/{profile_id}/impersonate",
            json={"reason": "课堂辅导", "scopes": ["annotation.submit"]},
        )
    assert missing.status_code == 422
    assert forbidden.status_code == 422


def test_impersonation_returns_scoped_auditable_grant(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch, role="admin") as client:
        profile_id = client.post(
            "/api/v1/learning-profiles", json={"name": "小明", "pin": "1234"}
        ).json()["id"]
        response = client.post(
            f"/api/v1/learning-profiles/{profile_id}/impersonate",
            json={
                "reason": "课堂辅导",
                "scopes": ["inbox.organize", "teacher_feedback.append"],
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["expires_in"] == 30 * 60
    assert body["impersonation_id"].startswith("imp_")
    assert body["scopes"] == ["inbox.organize", "teacher_feedback.append"]
    assert response.cookies.get(router_module.COOKIE_NAME)
