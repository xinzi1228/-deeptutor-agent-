"""
MCP Settings API Router
=======================

Manage the deployment-global MCP server registry: read/update the config,
inspect live connection status, and probe a server before saving.

Mounted at ``/api/v1/settings/mcp``. Admin-gated: the registry is
deployment-global state, and a stdio server's ``command`` runs on the host
as the app user — letting non-admins edit it would be privilege escalation.
Per-user MCP access is granted through the multi-user grant whitelist
(``mcp_tools``), not by sharing this registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from deeptutor.api.routers.auth import require_admin
from deeptutor.core.i18n import t
from deeptutor.services.mcp import (
    MCPConfig,
    MCPServerConfig,
    get_mcp_manager,
    load_mcp_config,
    save_mcp_config,
    validate_mcp_url,
)
from deeptutor.services.mcp.manager import probe_server

router = APIRouter(dependencies=[Depends(require_admin)])


class MCPSettingsPayload(BaseModel):
    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    confirmed: bool = False


def _validate_servers(config: MCPConfig) -> None:
    for name, cfg in config.servers.items():
        transport = cfg.resolved_type()
        if transport is None:
            raise HTTPException(
                status_code=400,
                detail=t("mcp.configure_command_or_url", name=name),
            )
        if transport in {"sse", "streamableHttp"}:
            ok, error = validate_mcp_url(cfg.url)
            if not ok:
                raise HTTPException(
                    status_code=400, detail=t("mcp.server_error", name=name, error=error)
                )


# Each MCP write is recorded as a versioned, rollback-able journal entry. The
# registry is deployment-global and a stdio server runs host commands, so any
# change that adds a server or flips one enabled is a high-risk change that
# must be explicitly confirmed before it is saved.
_CHANGE_JOURNAL = "mcp_changes.jsonl"


def _change_journal_path() -> Path:
    from deeptutor.multi_user.paths import get_admin_path_service

    return get_admin_path_service().get_settings_dir() / _CHANGE_JOURNAL


def _snapshot(config: MCPConfig) -> dict[str, Any]:
    return {name: cfg.model_dump(mode="json") for name, cfg in config.servers.items()}


def _record_change(
    *,
    action: str,
    confirmed: bool,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    from datetime import datetime, timezone
    import json as _json

    path = _change_journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "confirmed": confirmed,
        "before": before,
        "after": after,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _is_high_risk(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Adding a server or enabling one is high-risk (host command execution)."""
    for name, cfg in after.items():
        if name not in before:
            return True
        if bool(cfg.get("enabled", True)) and not bool(before[name].get("enabled", True)):
            return True
    return False


@router.get("")
async def get_mcp_settings() -> dict[str, Any]:
    config = load_mcp_config()
    manager = get_mcp_manager()
    await manager.ensure_started()
    return {
        "servers": {name: cfg.model_dump(mode="json") for name, cfg in config.servers.items()},
        "status": manager.status(),
    }


@router.put("")
async def update_mcp_settings(payload: MCPSettingsPayload) -> dict[str, Any]:
    try:
        config = MCPConfig(servers=payload.servers)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _validate_servers(config)

    previous = load_mcp_config()
    before = _snapshot(previous)
    after = _snapshot(config)
    if _is_high_risk(before, after) and not payload.confirmed:
        raise HTTPException(
            status_code=400,
            detail="添加或启用 MCP 服务器会运行主机命令，属于高风险变更，请二次确认后重试",
        )

    save_mcp_config(config)
    manager = get_mcp_manager()
    await manager.reload()
    _record_change(
        action="update",
        confirmed=payload.confirmed,
        before=before,
        after=after,
    )
    return {"status": manager.status(), "confirmed": payload.confirmed}


@router.get("/changes")
async def mcp_change_log(limit: int = 20) -> dict[str, Any]:
    """Versioned change + rollback journal for the MCP registry (admin)."""
    import json as _json

    path = _change_journal_path()
    if not path.exists():
        return {"changes": []}
    try:
        rows = [
            _json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, ValueError):
        rows = []
    return {"changes": rows[-max(1, min(limit, 200)):]}


@router.post("/test")
async def test_mcp_server(cfg: MCPServerConfig) -> dict[str, Any]:
    transport = cfg.resolved_type()
    if transport is None:
        raise HTTPException(
            status_code=400,
            detail=t("mcp.configure_before_testing"),
        )
    if transport in {"sse", "streamableHttp"}:
        ok, error = validate_mcp_url(cfg.url)
        if not ok:
            raise HTTPException(status_code=400, detail=error)
    return await probe_server(cfg)
