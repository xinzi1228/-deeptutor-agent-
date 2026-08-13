from pathlib import Path
import sqlite3

from deeptutor.services.label_studio_gateway import local_credentials


def _database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE htx_user (id INTEGER PRIMARY KEY, is_active INTEGER)")
        connection.execute("CREATE TABLE authtoken_token (key TEXT, created TEXT, user_id INTEGER)")
        connection.execute("INSERT INTO htx_user VALUES (1, 1)")
        connection.execute("INSERT INTO htx_user VALUES (2, 0)")
        connection.execute("INSERT INTO authtoken_token VALUES ('valid-old', '2026-01-01', 1)")
        connection.execute("INSERT INTO authtoken_token VALUES ('valid-new', '2026-02-01', 1)")
        connection.execute("INSERT INTO authtoken_token VALUES ('inactive', '2026-03-01', 2)")


def test_local_discovery_uses_newest_active_token(tmp_path, monkeypatch) -> None:
    database = tmp_path / "label_studio.sqlite3"
    _database(database)
    monkeypatch.setenv("LABEL_STUDIO_LOCAL_DB", str(database))
    assert local_credentials.discover_local_service_token("http://127.0.0.1:8080") == "valid-new"


def test_remote_origin_never_reads_local_database(tmp_path, monkeypatch) -> None:
    database = tmp_path / "label_studio.sqlite3"
    _database(database)
    monkeypatch.setenv("LABEL_STUDIO_LOCAL_DB", str(database))
    assert local_credentials.discover_local_service_token("https://labels.example.com") == ""


def test_explicit_token_has_priority(monkeypatch) -> None:
    monkeypatch.setenv("LABEL_STUDIO_API_TOKEN", "explicit-token")
    assert local_credentials.resolve_service_token("http://127.0.0.1:8080") == (
        "explicit-token",
        "environment",
    )


def test_local_bridge_secret_is_private_and_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEEPTUTOR_HOME", str(tmp_path))
    monkeypatch.delenv("LABEL_STUDIO_BRIDGE_SECRET", raising=False)
    first, source = local_credentials.resolve_bridge_secret("http://localhost:8080")
    second, _ = local_credentials.resolve_bridge_secret("http://localhost:8080")
    assert source == "local_secret_file"
    assert len(first) >= 32
    assert second == first
    assert not local_credentials.resolve_bridge_secret("https://labels.example.com")[0]
