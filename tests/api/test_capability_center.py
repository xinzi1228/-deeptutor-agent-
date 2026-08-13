from pydantic import ValidationError
import pytest

from deeptutor.api.routers import capability_center


def test_onboarding_update_rejects_out_of_range_steps() -> None:
    with pytest.raises(ValidationError):
        capability_center.OnboardingUpdate(step=0)
    with pytest.raises(ValidationError):
        capability_center.OnboardingUpdate(step=8)


@pytest.mark.asyncio
async def test_diagnostics_adds_schema_without_secret_fields(monkeypatch) -> None:
    async def fake_overview():
        return {
            "overall": "normal",
            "cards": [{"details": {"configured": True}}],
            "privacy": "脱敏",
        }

    monkeypatch.setattr(capability_center, "overview", fake_overview)
    report = await capability_center.diagnostics()
    serialized = str(report).lower()
    assert report["report_schema_version"] == 1
    assert "api_key" not in serialized
    assert "token" not in serialized
    assert "cookie" not in serialized


def test_card_explains_status_impact_and_repair_path() -> None:
    card = capability_center._card(
        "models", "模型能力", "limited", "未配置生图模型", "只能输出文字", "/settings/models"
    )
    assert card["status"] == "limited"
    assert card["impact"] == "只能输出文字"
    assert card["repair_href"] == "/settings/models"
