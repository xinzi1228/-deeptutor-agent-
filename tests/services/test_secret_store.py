from pathlib import Path

from deeptutor.services.secrets import MemorySecretBackend, SecretStore


def test_secret_store_round_trip_without_exposing_value_in_reference():
    backend = MemorySecretBackend()
    store = SecretStore(backend)

    reference = store.put("model:llm:profile-a", "sk-super-secret")

    assert "sk-super-secret" not in reference
    assert store.get(reference) == "sk-super-secret"
    store.delete(reference)
    assert store.get(reference) == ""


def test_model_catalog_persists_secret_reference_and_returns_redacted_public_view(
    tmp_path: Path,
):
    from deeptutor.services.config.model_catalog import ModelCatalogService

    backend = MemorySecretBackend()
    service = ModelCatalogService(
        path=tmp_path / "model_catalog.json",
        secret_store=SecretStore(backend),
    )
    catalog = service.load()
    catalog["services"]["llm"] = {
        "active_profile_id": "profile-a",
        "active_model_id": "model-a",
        "profiles": [
            {
                "id": "profile-a",
                "name": "A",
                "binding": "openai",
                "base_url": "https://example.test/v1",
                "api_key": "sk-super-secret",
                "models": [{"id": "model-a", "name": "M", "model": "m"}],
            }
        ],
    }

    runtime = service.save(catalog)
    public = service.load_public()
    stored = (tmp_path / "model_catalog.json").read_text(encoding="utf-8")

    assert runtime["services"]["llm"]["profiles"][0]["api_key"] == "sk-super-secret"
    assert "sk-super-secret" not in stored
    public_profile = public["services"]["llm"]["profiles"][0]
    assert public_profile["api_key"] == ""
    assert public_profile["api_key_set"] is True
    assert "secret_ref" not in public_profile


def test_blank_public_key_preserves_existing_secret(tmp_path: Path):
    from deeptutor.services.config.model_catalog import ModelCatalogService

    service = ModelCatalogService(
        path=tmp_path / "model_catalog.json",
        secret_store=SecretStore(MemorySecretBackend()),
    )
    catalog = service.load()
    catalog["services"]["search"] = {
        "active_profile_id": "search-a",
        "profiles": [
            {
                "id": "search-a",
                "name": "Search",
                "provider": "brave",
                "base_url": "",
                "api_key": "first-secret",
                "models": [],
            }
        ],
    }
    service.save(catalog)

    public = service.load_public()
    public["services"]["search"]["profiles"][0]["name"] = "Renamed"
    runtime = service.save(public)

    profile = runtime["services"]["search"]["profiles"][0]
    assert profile["name"] == "Renamed"
    assert profile["api_key"] == "first-secret"


def test_materialize_catalog_uses_saved_secret_for_connection_test(tmp_path: Path):
    from deeptutor.services.config.model_catalog import ModelCatalogService

    service = ModelCatalogService(
        path=tmp_path / "model_catalog.json",
        secret_store=SecretStore(MemorySecretBackend()),
    )
    catalog = service.load()
    catalog["services"]["llm"] = {
        "active_profile_id": "profile-a",
        "active_model_id": "model-a",
        "profiles": [
            {
                "id": "profile-a",
                "name": "A",
                "binding": "openai",
                "base_url": "https://example.test/v1",
                "api_key": "saved-secret",
                "models": [{"id": "model-a", "name": "M", "model": "m"}],
            }
        ],
    }
    service.save(catalog)

    draft = service.load_public()
    resolved = service.materialize_catalog(draft)

    assert resolved["services"]["llm"]["profiles"][0]["api_key"] == "saved-secret"


def test_legacy_plaintext_migration_is_explicit_and_reported(tmp_path: Path):
    import json

    path = tmp_path / "model_catalog.json"
    path.write_text(
        json.dumps(
            {
                "services": {
                    "llm": {
                        "active_profile_id": "profile-a",
                        "active_model_id": None,
                        "profiles": [
                            {
                                "id": "profile-a",
                                "name": "A",
                                "api_key": "legacy-secret",
                                "models": [],
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    from deeptutor.services.config.model_catalog import ModelCatalogService

    service = ModelCatalogService(
        path=path,
        secret_store=SecretStore(MemorySecretBackend()),
    )

    before = service.secret_migration_status()
    after = service.migrate_plaintext_secrets()

    assert before.migration_required is True
    assert before.plaintext_count == 1
    assert after.migration_required is False
    assert after.reference_count == 1
    assert "legacy-secret" not in path.read_text(encoding="utf-8")
