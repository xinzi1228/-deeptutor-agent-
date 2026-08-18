"""Professional-mode preload gateway — POST /api/v1/label-studio/preload.

Batch-prepares every assigned professional task for the current learning
profile (idempotent, non-blocking on per-task failure). Mocks LabelStudioClient
so no Label Studio process is required.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from deeptutor.api.routers import label_studio_gateway as router_module
from deeptutor.multi_user.context import set_current_learning_profile, set_current_user
from deeptutor.multi_user.models import CurrentUser, UserScope
from deeptutor.services.label_studio_gateway import LabelStudioUnavailable
from deeptutor.services.learning_profiles.models import ProfileAccessContext

API = "/api/v1/label-studio"
PROFILE_ID = "lp_" + "a" * 24


def _write_task_bank(root: Path) -> None:
    workspace = root / "user" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    bank = {
        "task1": {"title": "街景车辆检测", "type": "bbox", "modal": "image", "labels": ["car"]},
        "task2": {"title": "停车场多车辆检测", "type": "bbox", "modal": "image", "labels": ["car"]},
        "task3": {"title": "文本分类", "type": "classification", "modal": "text", "labels": ["pos"]},
        "task4": {"title": "音频事件", "type": "audio_event", "modal": "audio", "labels": ["knock"]},
    }
    (workspace / "task_bank.json").write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")


class FakeLabelStudioClient:
    """Mimics LabelStudioClient.ensure_task idempotency against the persisted map."""

    def __init__(self) -> None:
        self.token = "test-token"
        self.token_source = "env"
        self.base_url = "http://127.0.0.1:8080"
        self.ensure_calls: list[str] = []
        self.fail_tasks: set[str] = set()

    async def health(self) -> bool:
        return True

    async def ensure_task(self, mapping, task_id, task, profile_root):
        if task_id in mapping.task_map:
            return mapping.project_id, mapping.task_map[task_id]
        if task_id in self.fail_tasks:
            raise LabelStudioUnavailable(f"mock failure for {task_id}")
        self.ensure_calls.append(task_id)
        if mapping.project_id is None:
            mapping.project_id = 7
        ls_task_id = 1000 + len(self.ensure_calls)
        mapping.task_map[task_id] = ls_task_id
        mapping.save(profile_root)
        return mapping.project_id, mapping.task_map[task_id]


def _client(tmp_path: Path, *, profile: bool = True, read_only: bool = False) -> TestClient:
    _write_task_bank(tmp_path)
    user = CurrentUser(
        id="u_preload",
        username="tester",
        role="user",
        scope=UserScope(kind="user", user_id="u_preload", root=tmp_path),
    )
    access = ProfileAccessContext(
        owner_user_id="u_preload",
        profile_id=PROFILE_ID,
        mode="teacher_view" if read_only else "student",
        actor_user_id="u_preload",
        read_only=read_only,
    )

    async def fake_auth():
        set_current_user(user)
        if profile:
            set_current_learning_profile(access)
        return None

    app = FastAPI()
    app.dependency_overrides[router_module.require_admin] = fake_auth
    app.include_router(
        router_module.router,
        prefix=API,
        dependencies=[Depends(fake_auth)],
    )
    return TestClient(app)


def test_preload_requires_unlocked_profile(tmp_path: Path) -> None:
    with _client(tmp_path, profile=False) as client:
        response = client.post(f"{API}/preload")
    assert response.status_code == 423


def test_preload_rejects_read_only_teacher_view(tmp_path: Path) -> None:
    with _client(tmp_path, read_only=True) as client:
        response = client.post(f"{API}/preload")
    assert response.status_code == 403


def test_preload_prepares_all_assigned_tasks(tmp_path: Path, monkeypatch) -> None:
    fake = FakeLabelStudioClient()
    monkeypatch.setattr(router_module, "LabelStudioClient", lambda: fake)
    with _client(tmp_path) as client:
        response = client.post(f"{API}/preload")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["prepared"] == 3
    assert body["total"] == 3
    assert set(body["task_urls"]) == {"task1", "task2", "task3"}
    assert all(url.startswith("/api/v1/label-studio/proxy/projects/") for url in body["task_urls"].values())
    assert len(fake.ensure_calls) == 3


def test_preload_is_idempotent_across_repeat_calls(tmp_path: Path, monkeypatch) -> None:
    fake = FakeLabelStudioClient()
    monkeypatch.setattr(router_module, "LabelStudioClient", lambda: fake)
    with _client(tmp_path) as client:
        first = client.post(f"{API}/preload").json()
        second = client.post(f"{API}/preload").json()
    assert first["ready"] is True
    assert second["ready"] is True
    assert second["prepared"] == 3
    # Only N real creations, not 2N: the persisted task_map short-circuits repeats.
    assert len(fake.ensure_calls) == 3
    assert second["task_urls"] == first["task_urls"]


def test_preload_partial_failure_is_not_ready(tmp_path: Path, monkeypatch) -> None:
    fake = FakeLabelStudioClient()
    fake.fail_tasks = {"task2"}
    monkeypatch.setattr(router_module, "LabelStudioClient", lambda: fake)
    with _client(tmp_path) as client:
        response = client.post(f"{API}/preload")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["prepared"] == 2
    assert body["total"] == 3
    assert set(body["task_urls"]) == {"task1", "task3"}


def test_rewrite_text_injects_app_settings_hostname() -> None:
    """LS HTML's window.APP_SETTINGS.hostname must point at the proxy URL.

    The LS frontend computes gateway = `${window.APP_SETTINGS.hostname}/api` and
    later runs `new URL(window.APP_SETTINGS.hostname)`. Django renders hostname
    as "" (empty), so the proxy must rewrite both double- and single-quoted empty
    literals to an absolute proxy URL — a bare path would make `new URL()` throw
    and crash the LS React app. Non-proxy callers (no proxy_base_url) must leave
    hostname untouched.
    """
    proxy_url = f"http://127.0.0.1:3782{router_module.PROXY_PREFIX}"
    assert f'hostname: "{proxy_url}"' in router_module._rewrite_text('    hostname: "",', proxy_url)
    assert f'hostname: "{proxy_url}"' in router_module._rewrite_text("    hostname: '',", proxy_url)
    # Without proxy_base_url the literal stays untouched (non-proxy rewrite path).
    assert 'hostname: ""' in router_module._rewrite_text('hostname: ""')
    assert "hostname: ''" in router_module._rewrite_text("hostname: ''")


def test_rewrite_text_rewrites_url_literals() -> None:
    rewritten = router_module._rewrite_text('"/static/app.css" "/api/current-user/whoami" "/projects/1"')
    assert f'"{router_module.PROXY_PREFIX}/static/app.css"' in rewritten
    assert f'"{router_module.PROXY_PREFIX}/api/current-user/whoami"' in rewritten
    assert f'"{router_module.PROXY_PREFIX}/projects/1"' in rewritten
    assert router_module.PROXY_PREFIX + router_module.PROXY_PREFIX not in rewritten


def test_status_reports_ready_count_after_preload(tmp_path: Path, monkeypatch) -> None:
    fake = FakeLabelStudioClient()
    monkeypatch.setattr(router_module, "LabelStudioClient", lambda: fake)
    with _client(tmp_path) as client:
        client.post(f"{API}/preload")
        response = client.get(f"{API}/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["ready_count"] == 3
    assert body["total_count"] == 3
    assert {row["id"] for row in body["prepared_tasks"]} == {"task1", "task2", "task3"}
