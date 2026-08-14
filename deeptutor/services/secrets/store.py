from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
from typing import Protocol


class SecretStoreUnavailable(RuntimeError):
    """Raised when no secure operating-system-backed store is available."""


class SecretBackend(Protocol):
    scheme: str

    def put(self, key: str, value: str) -> str: ...

    def get(self, reference: str) -> str: ...

    def delete(self, reference: str) -> None: ...


class MemorySecretBackend:
    """Deterministic in-memory backend for tests; never selected in production."""

    scheme = "memory"

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def put(self, key: str, value: str) -> str:
        reference = f"{self.scheme}:{_opaque_id(key)}"
        self._values[reference] = value
        return reference

    def get(self, reference: str) -> str:
        return self._values.get(reference, "")

    def delete(self, reference: str) -> None:
        self._values.pop(reference, None)


class WindowsDpapiBackend:
    """Encrypt secrets with DPAPI and persist only encrypted blobs on disk.

    DPAPI binds ciphertext to the current Windows account. Moving the project
    directory to another computer therefore does not move usable credentials.
    """

    scheme = "dpapi"

    def __init__(self, directory: Path) -> None:
        if os.name != "nt":
            raise SecretStoreUnavailable("Windows DPAPI is only available on Windows.")
        try:
            import win32crypt  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on host image
            raise SecretStoreUnavailable(
                "Windows DPAPI support requires the pywin32 runtime."
            ) from exc
        self.directory = directory

    def put(self, key: str, value: str) -> str:
        import win32crypt

        reference = f"{self.scheme}:{_opaque_id(key)}"
        encrypted = win32crypt.CryptProtectData(
            value.encode("utf-8"),
            "DeepTutor model credential",
            None,
            None,
            None,
            0,
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(reference).write_bytes(encrypted)
        return reference

    def get(self, reference: str) -> str:
        import win32crypt

        path = self._path(reference)
        if not path.exists():
            return ""
        try:
            _description, plaintext = win32crypt.CryptUnprotectData(
                path.read_bytes(), None, None, None, 0
            )
        except Exception as exc:  # pragma: no cover - host/user mismatch
            raise SecretStoreUnavailable(
                "The saved credential cannot be unlocked by the current Windows account."
            ) from exc
        return plaintext.decode("utf-8")

    def delete(self, reference: str) -> None:
        self._path(reference).unlink(missing_ok=True)

    def _path(self, reference: str) -> Path:
        if not reference.startswith(f"{self.scheme}:"):
            raise ValueError("Invalid DPAPI secret reference.")
        opaque = reference.split(":", 1)[1]
        if not opaque or any(char not in "0123456789abcdef" for char in opaque):
            raise ValueError("Invalid DPAPI secret reference.")
        return self.directory / f"{opaque}.bin"


class SecretStore:
    def __init__(self, backend: SecretBackend):
        self.backend = backend

    @classmethod
    def for_catalog(cls, catalog_path: Path) -> "SecretStore":
        return cls(WindowsDpapiBackend(catalog_path.parent / "model_credentials"))

    def put(self, key: str, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Cannot store an empty secret.")
        return self.backend.put(key, clean)

    @property
    def backend_name(self) -> str:
        return self.backend.scheme

    def get(self, reference: str) -> str:
        if not reference:
            return ""
        if reference.startswith("env:"):
            variable = reference.split(":", 1)[1]
            return os.environ.get(variable, "")
        if not reference.startswith(f"{self.backend.scheme}:"):
            return ""
        return self.backend.get(reference)

    def delete(self, reference: str) -> None:
        if not reference or reference.startswith("env:"):
            return
        if reference.startswith(f"{self.backend.scheme}:"):
            self.backend.delete(reference)


def _opaque_id(key: str) -> str:
    return sha256(key.encode("utf-8")).hexdigest()[:40]


__all__ = [
    "MemorySecretBackend",
    "SecretBackend",
    "SecretStore",
    "SecretStoreUnavailable",
    "WindowsDpapiBackend",
]
