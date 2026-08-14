import pytest

from deeptutor.api.routers import student_dashboard as router


class FakeService:
    def home(self):
        return {"view": "home", "version": {"profile_id": "profile-a"}}

    def growth(self):
        return {"view": "growth", "version": {"profile_id": "profile-a"}}


@pytest.mark.asyncio
async def test_dashboard_router_returns_separate_home_and_growth_views(monkeypatch):
    monkeypatch.setattr(router, "get_student_dashboard_service", lambda: FakeService())
    assert (await router.student_home())["view"] == "home"
    assert (await router.student_growth())["view"] == "growth"


@pytest.mark.asyncio
async def test_dashboard_router_maps_locked_profile(monkeypatch):
    def locked():
        raise PermissionError("请先解锁学习档案")

    monkeypatch.setattr(router, "get_student_dashboard_service", locked)
    with pytest.raises(router.HTTPException) as exc:
        await router.student_home()
    assert exc.value.status_code == 423
