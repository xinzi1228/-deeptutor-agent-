from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any
from uuid import uuid4

from deeptutor.services.path_service import get_path_service
from deeptutor.services.secrets import SecretMigrationStatus, SecretStore

from .embedding_endpoint import normalize_embedding_endpoint_for_display

# Fallback only — frozen at admin scope at import time. Production code should
# enter through ``get_model_catalog_service()`` so the path is resolved from the
# current user's PathService on every call.
CATALOG_PATH = get_path_service().get_settings_file("model_catalog")


def _service_shell() -> dict[str, Any]:
    return {
        "active_profile_id": None,
        "active_model_id": None,
        "profiles": [],
    }


def _search_shell() -> dict[str, Any]:
    return {
        "active_profile_id": None,
        "profiles": [],
    }


def _default_catalog() -> dict[str, Any]:
    return {
        "version": 1,
        "services": {
            "llm": _service_shell(),
            "embedding": _service_shell(),
            "search": _search_shell(),
            "tts": _service_shell(),
            "stt": _service_shell(),
            "imagegen": _service_shell(),
            "videogen": _service_shell(),
        },
    }


class ModelCatalogService:
    _instances: dict[str, "ModelCatalogService"] = {}

    def __init__(
        self,
        path: Path | None = None,
        secret_store: SecretStore | None = None,
    ):
        self.path = path or CATALOG_PATH
        self.secret_store = secret_store or SecretStore.for_catalog(self.path)
        self._lock = threading.RLock()

    @classmethod
    def get_instance(cls, path: Path | None = None) -> "ModelCatalogService":
        resolved = (path or get_path_service().get_settings_file("model_catalog")).resolve()
        key = str(resolved)
        if key not in cls._instances:
            cls._instances[key] = cls(resolved)
        return cls._instances[key]

    def load(self) -> dict[str, Any]:
        loaded = self._read_existing_catalog()
        if loaded:
            catalog = _default_catalog()
            catalog.update({k: v for k, v in loaded.items() if k != "services"})
            catalog["services"].update(loaded.get("services", {}))
            merged_defaults = catalog != loaded
            before = deepcopy(catalog)
            self._normalize(catalog)
            if merged_defaults or catalog != before:
                if not self._has_plaintext_secrets(catalog):
                    return self.save(catalog)
                # Keep legacy credentials untouched until the administrator
                # explicitly runs the migration action. The normalized view is
                # still safe to use in memory and public responses are redacted.
                return catalog
            return self._resolve_secrets(catalog)

        catalog = _default_catalog()
        self._normalize(catalog)
        self.save(catalog)
        return catalog

    def load_public(self) -> dict[str, Any]:
        """Return catalog metadata without revealing credentials or references."""

        public = deepcopy(self.load())
        for service in public.get("services", {}).values():
            for profile in service.get("profiles", []):
                profile["api_key_set"] = bool(profile.get("api_key"))
                profile["api_key"] = ""
                profile.pop("secret_ref", None)
                profile.pop("clear_api_key", None)
        return public

    def materialize_catalog(self, catalog: dict[str, Any]) -> dict[str, Any]:
        """Hydrate a redacted UI draft for connection tests without persisting it."""

        materialized = deepcopy(catalog)
        existing = self.load()
        existing_profiles = self._profile_index(existing)
        for service_name, service in materialized.get("services", {}).items():
            for profile in service.get("profiles", []):
                if profile.get("api_key"):
                    continue
                saved = existing_profiles.get((service_name, str(profile.get("id") or "")))
                if saved:
                    profile["api_key"] = saved.get("api_key", "")
                profile.pop("api_key_set", None)
        self._normalize(materialized)
        return materialized

    def secret_migration_status(self) -> SecretMigrationStatus:
        raw = self._read_existing_catalog()
        profiles = [
            profile
            for service in raw.get("services", {}).values()
            for profile in service.get("profiles", [])
        ]
        return SecretMigrationStatus(
            backend=self.secret_store.backend_name,
            plaintext_count=sum(bool(profile.get("api_key")) for profile in profiles),
            reference_count=sum(bool(profile.get("secret_ref")) for profile in profiles),
            configured_count=sum(
                bool(profile.get("api_key") or profile.get("secret_ref"))
                for profile in profiles
            ),
        )

    def migrate_plaintext_secrets(self) -> SecretMigrationStatus:
        """Move legacy plaintext keys after an explicit administrator action."""

        raw = self._read_existing_catalog()
        if raw and self._has_plaintext_secrets(raw):
            self.save(raw)
        return self.secret_migration_status()

    def _read_existing_catalog(self) -> dict[str, Any]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def save(self, catalog: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            normalized = deepcopy(catalog)
            self._normalize(normalized)
            stored = self._prepare_for_storage(normalized)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            temp_path = Path(temp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    json.dump(stored, handle, indent=2, ensure_ascii=False)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.path)
            finally:
                temp_path.unlink(missing_ok=True)
            return self._resolve_secrets(stored)

    def update(self, mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        with self._lock:
            catalog = self.load()
            mutator(catalog)
            return self.save(catalog)

    def apply(self, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
        current = self.save(catalog or self.load())
        return {"catalog_path": str(self.path), "services": list(current.get("services", {}))}

    def _normalize(self, catalog: dict[str, Any]) -> bool:
        services = catalog.setdefault("services", {})
        changed = False
        services.setdefault("llm", _service_shell())
        services.setdefault("embedding", _service_shell())
        services.setdefault("search", _search_shell())
        services.setdefault("tts", _service_shell())
        services.setdefault("stt", _service_shell())
        services.setdefault("imagegen", _service_shell())
        services.setdefault("videogen", _service_shell())
        for service_name in ("llm", "embedding", "search", "tts", "stt", "imagegen", "videogen"):
            service = services[service_name]
            profiles = service.setdefault("profiles", [])
            for profile in profiles:
                profile.setdefault("id", f"{service_name}-profile-{uuid4().hex[:8]}")
                profile.setdefault("name", "Untitled Profile")
                profile.setdefault("api_version", "")
                profile.setdefault("base_url", "")
                profile.setdefault("api_key", "")
                if service_name == "search":
                    profile.setdefault("provider", "brave")
                    profile.setdefault("proxy", "")
                    profile["models"] = []
                else:
                    profile.setdefault("binding", "openai")
                    profile.setdefault("extra_headers", {})
                    if service_name == "embedding":
                        before = str(profile.get("base_url") or "")
                        after = normalize_embedding_endpoint_for_display(
                            profile.get("binding"),
                            before,
                        )
                        if after != before:
                            profile["base_url"] = after
                            changed = True
                    models = profile.setdefault("models", [])
                    for model in models:
                        model.setdefault("id", f"{service_name}-model-{uuid4().hex[:8]}")
                        model.setdefault("name", model.get("model") or "Untitled Model")
                        model.setdefault("model", "")
                        if service_name == "embedding":
                            # Empty default → test_runner auto-fills from the
                            # actual API response on first connection test.
                            model.setdefault("dimension", "")
                            # CSV of supported dims discovered during the last
                            # successful "Test connection" — drives the UI
                            # dropdown. Empty when the model is not in any
                            # adapter's MODELS_INFO map.
                            model.setdefault("supported_dimensions", "")
                        elif service_name == "tts":
                            # Provider/model-specific free-form voice string
                            # (e.g. "alloy", "autumn", "model:voice").
                            model.setdefault("voice", "")
                            model.setdefault("response_format", "mp3")
                        elif service_name == "imagegen":
                            # Generation knobs; empty → provider default.
                            model.setdefault("size", "")
                            model.setdefault("quality", "")
                            model.setdefault("style", "")
                            model.setdefault("response_format", "")
                        elif service_name == "videogen":
                            model.setdefault("aspect_ratio", "")
                            model.setdefault("duration", "")
                            model.setdefault("resolution", "")
            profile_ids = {profile.get("id") for profile in profiles}
            if profiles and service.get("active_profile_id") not in profile_ids:
                service["active_profile_id"] = profiles[0]["id"]
                changed = True
            if service_name in {"llm", "embedding", "tts", "stt", "imagegen", "videogen"}:
                active_profile = self.get_active_profile(catalog, service_name)
                models = (active_profile or {}).get("models") or []
                model_ids = {model.get("id") for model in models}
                if models and service.get("active_model_id") not in model_ids:
                    service["active_model_id"] = models[0]["id"]
                    changed = True
        return changed

    def _prepare_for_storage(self, catalog: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(catalog)
        existing = self._read_existing_catalog()
        existing_profiles = self._profile_index(existing)
        for service_name, service in stored.get("services", {}).items():
            for profile in service.get("profiles", []):
                profile_id = str(profile.get("id") or "")
                previous = existing_profiles.get((service_name, profile_id), {})
                incoming = str(profile.get("api_key") or "").strip()
                clear = bool(profile.pop("clear_api_key", False))
                reference = str(profile.get("secret_ref") or previous.get("secret_ref") or "")
                if clear:
                    self.secret_store.delete(reference)
                    reference = ""
                elif incoming:
                    reference = self.secret_store.put(
                        f"model:{service_name}:{profile_id}", incoming
                    )
                elif not reference and previous.get("api_key"):
                    reference = self.secret_store.put(
                        f"model:{service_name}:{profile_id}",
                        str(previous["api_key"]),
                    )
                profile["api_key"] = ""
                profile.pop("api_key_set", None)
                if reference:
                    profile["secret_ref"] = reference
                else:
                    profile.pop("secret_ref", None)
        return stored

    def _resolve_secrets(self, catalog: dict[str, Any]) -> dict[str, Any]:
        runtime = deepcopy(catalog)
        for service in runtime.get("services", {}).values():
            for profile in service.get("profiles", []):
                reference = str(profile.get("secret_ref") or "")
                if reference:
                    profile["api_key"] = self.secret_store.get(reference)
        return runtime

    @staticmethod
    def _profile_index(catalog: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
        return {
            (service_name, str(profile.get("id") or "")): profile
            for service_name, service in catalog.get("services", {}).items()
            for profile in service.get("profiles", [])
        }

    @staticmethod
    def _has_plaintext_secrets(catalog: dict[str, Any]) -> bool:
        return any(
            bool(profile.get("api_key"))
            for service in catalog.get("services", {}).values()
            for profile in service.get("profiles", [])
        )

    def get_active_profile(
        self, catalog: dict[str, Any], service_name: str
    ) -> dict[str, Any] | None:
        service = catalog.get("services", {}).get(service_name, {})
        active_id = service.get("active_profile_id")
        for profile in service.get("profiles", []):
            if profile.get("id") == active_id:
                return profile
        profiles = service.get("profiles", [])
        return profiles[0] if profiles else None

    def get_active_model(self, catalog: dict[str, Any], service_name: str) -> dict[str, Any] | None:
        if service_name == "search":
            return None
        service = catalog.get("services", {}).get(service_name, {})
        active_model_id = service.get("active_model_id")
        profile = self.get_active_profile(catalog, service_name)
        if not profile:
            return None
        for model in profile.get("models", []):
            if model.get("id") == active_model_id:
                return model
        models = profile.get("models", [])
        return models[0] if models else None


def get_model_catalog_service() -> ModelCatalogService:
    try:
        from deeptutor.multi_user.context import get_current_user
        from deeptutor.multi_user.paths import get_admin_path_service

        if not get_current_user().is_admin:
            return ModelCatalogService.get_instance(
                get_admin_path_service().get_settings_file("model_catalog")
            )
    except Exception:
        pass
    return ModelCatalogService.get_instance(get_path_service().get_settings_file("model_catalog"))


__all__ = ["CATALOG_PATH", "ModelCatalogService", "get_model_catalog_service"]
