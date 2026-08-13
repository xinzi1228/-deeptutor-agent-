"""Local-only Label Studio credential discovery for the desktop launcher.

This module deliberately refuses remote origins. Production deployments must
provide explicit environment variables; only a co-located loopback Label
Studio may reuse its local database token and a private runtime secret.
"""

from __future__ import annotations

import os
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlparse

from deeptutor.runtime.home import get_runtime_home
from deeptutor.services.file_io import atomic_write_text


def is_loopback_url(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _local_database() -> Path:
    configured = os.environ.get("LABEL_STUDIO_LOCAL_DB", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return get_runtime_home() / "data" / "label-studio" / "label_studio.sqlite3"


def discover_local_service_token(base_url: str) -> str:
    """Read the newest local DRF token without ever mutating the LS database."""
    if not is_loopback_url(base_url):
        return ""
    database = _local_database()
    if not database.is_file():
        return ""
    try:
        uri = f"file:{database.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2.0) as connection:
            row = connection.execute(
                """
                SELECT token.key
                FROM authtoken_token AS token
                JOIN htx_user AS user ON user.id = token.user_id
                WHERE user.is_active = 1
                ORDER BY token.created DESC
                LIMIT 1
                """
            ).fetchone()
    except (OSError, sqlite3.Error):
        return ""
    return str(row[0]).strip() if row and row[0] else ""


def resolve_service_token(base_url: str, explicit: str | None = None) -> tuple[str, str]:
    token = (explicit if explicit is not None else os.environ.get("LABEL_STUDIO_API_TOKEN", "")).strip()
    if token:
        return token, "environment"
    local = discover_local_service_token(base_url)
    return (local, "local_database") if local else ("", "missing")


def resolve_bridge_secret(base_url: str) -> tuple[str, str]:
    explicit = os.environ.get("LABEL_STUDIO_BRIDGE_SECRET", "").strip()
    if explicit:
        return explicit, "environment"
    if not is_loopback_url(base_url):
        return "", "missing"
    secret_file = get_runtime_home() / "data" / "user" / "settings" / "label_studio_bridge.secret"
    try:
        if secret_file.is_file():
            value = secret_file.read_text(encoding="utf-8").strip()
            if len(value) >= 32:
                return value, "local_secret_file"
        value = secrets.token_urlsafe(48)
        atomic_write_text(secret_file, value + "\n")
        try:
            os.chmod(secret_file, 0o600)
        except OSError:
            pass
        return value, "local_secret_file"
    except OSError:
        return "", "missing"


__all__ = [
    "discover_local_service_token",
    "is_loopback_url",
    "resolve_bridge_secret",
    "resolve_service_token",
]
