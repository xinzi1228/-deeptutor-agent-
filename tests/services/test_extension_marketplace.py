import pytest

from deeptutor.services.extension_marketplace import ExtensionMarketplaceService


def test_catalog_is_curated_and_install_is_per_workspace(tmp_path):
    service = ExtensionMarketplaceService(root=tmp_path)

    catalog = service.catalog()
    assert {item["id"] for item in catalog} == {
        "learning-path-diagram",
        "report-card-enhancer",
    }
    assert all(item["approved"] for item in catalog)
    assert not any(item["installed"] for item in catalog)

    installed = service.install("learning-path-diagram")
    assert installed["installed"] is True
    assert installed["enabled"] is True
    assert service.is_enabled("learning-path-diagram") is True

    disabled = service.set_enabled("learning-path-diagram", False)
    assert disabled["enabled"] is False
    assert service.is_enabled("learning-path-diagram") is False


def test_unknown_extension_is_rejected(tmp_path):
    service = ExtensionMarketplaceService(root=tmp_path)

    with pytest.raises(ValueError, match="不存在或尚未审核"):
        service.install("https://untrusted.example/mcp")


def test_learning_path_requires_the_extension_to_be_enabled(tmp_path):
    service = ExtensionMarketplaceService(root=tmp_path)

    with pytest.raises(PermissionError, match="尚未启用"):
        service.learning_path()
