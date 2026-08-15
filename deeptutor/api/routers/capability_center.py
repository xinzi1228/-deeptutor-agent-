"""Secret-free capability overview and first-run onboarding state."""

from __future__ import annotations

from datetime import datetime, timezone
import shutil
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deeptutor.multi_user.context import get_current_learning_profile, get_current_user
from deeptutor.multi_user.paths import get_current_path_service
from deeptutor.services.config import get_model_catalog_service
from deeptutor.services.onboarding import (
    ALL_STEP_KEYS,
    OPTIONAL_STEPS,
    apply_action,
    current_step,
    fingerprint,
    load_state,
    mark_stale,
    save_state,
)

router = APIRouter()
Status = Literal["normal", "limited", "fault"]


class OnboardingUpdate(BaseModel):
    # Legacy v1 wizard fields (kept for backward compatibility with saved
    # clients that still submit integer steps). New clients use step_key +
    # action on the resumable state machine.
    step: int | None = Field(default=None, ge=1, le=7)
    completed: list[int] = Field(default_factory=list)
    skipped: list[int] = Field(default_factory=list)
    dismissed: bool | None = None
    step_key: str | None = None
    action: Literal["done", "skip", "resume", "retest"] | None = None
    detail: str = ""


def _card(
    key: str,
    title: str,
    status: Status,
    summary: str,
    impact: str,
    repair_href: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "status": status,
        "summary": summary,
        "impact": impact,
        "repair_href": repair_href,
        "details": details,
    }


def _model_status() -> tuple[dict[str, Any], dict[str, Any]]:
    from deeptutor.services.config import get_model_catalog_service

    service = get_model_catalog_service()
    catalog = service.load()

    def active(kind: str) -> str:
        model = service.get_active_model(catalog, kind) or {}
        return str(model.get("name") or model.get("model") or model.get("id") or "")

    llm = active("llm")
    image = active("imagegen")
    return (
        _card(
            "models", "模型能力", "normal" if llm else "fault",
            f"主对话模型：{llm}" if llm else "尚未配置主对话模型",
            "主模型缺失时无法使用 AI 对话；生图模型是可选项。",
            "/settings/models", llm_model=llm or None, image_model=image or None,
            imagegen_configured=bool(image),
        ),
        {"llm": bool(llm), "imagegen": bool(image)},
    )


def _knowledge_status() -> dict[str, Any]:
    from deeptutor.multi_user.knowledge_access import current_kb_manager
    from deeptutor.services.config import get_model_catalog_service

    try:
        manager = current_kb_manager()
        names = manager.list_knowledge_bases()
    except Exception:
        manager = None
        names = []
    catalog_service = get_model_catalog_service()
    catalog = catalog_service.load()
    embedding = catalog_service.get_active_model(catalog, "embedding") or {}
    embedding_name = str(embedding.get("name") or embedding.get("model") or "")
    rows = []
    if manager is not None:
        for name in names:
            item = (manager.config.get("knowledge_bases", {}) or {}).get(name, {})
            rows.append({
                "name": name,
                "status": item.get("status", "unknown"),
                "progress": item.get("progress", {}),
            })
    ready_count = sum(1 for item in rows if item["status"] == "ready")
    failed_count = sum(1 for item in rows if item["status"] == "error")
    state: Status = "normal" if ready_count and embedding_name else "fault" if names and not embedding_name else "limited"
    if names and not embedding_name:
        summary = f"已有 {len(names)} 个资料库文件，但尚未配置 Embedding 模型，不能检索"
    elif names:
        summary = f"已有 {len(names)} 个知识库，{ready_count} 个可检索"
    else:
        summary = "还没有导入知识资料"
    return _card(
        "knowledge", "知识与资料", state, summary,
        "资料文件与可检索索引是两回事；导入后必须等待索引完成，并用带引用的示例问题验收。",
        "/settings/embedding" if names and not embedding_name else "/capabilities#quick-knowledge",
        knowledge_base_count=len(names), ready_count=ready_count,
        failed_count=failed_count, embedding_model=embedding_name or None,
        imports=rows,
    )


def _extension_status() -> dict[str, Any]:
    from deeptutor.services.mcp import load_mcp_config
    from deeptutor.services.skill import get_skill_service

    skills = get_skill_service().list_skills()
    mcp = load_mcp_config()
    enabled_mcp = [name for name, config in mcp.servers.items() if config.enabled]
    status: Status = "normal" if skills or enabled_mcp else "limited"
    return _card(
        "extensions", "扩展市场", status,
        f"可用 Skill {len(skills)} 个，已启用 MCP {len(enabled_mcp)} 个",
        "扩展是可选能力；不安装不会影响基础聊天和教学标注。",
        "/settings/tools", skill_count=len(skills), mcp_count=len(enabled_mcp),
        mcp_repair_href="/settings/mcp",
    )


async def _annotation_status() -> dict[str, Any]:
    from deeptutor.services.label_studio_gateway import LabelStudioClient

    client = LabelStudioClient()
    available = await client.health()
    configured = bool(client.token)
    state: Status = "normal" if available and configured else "limited"
    if available and not configured:
        summary = "Label Studio 已启动，但尚未配置安全接入 Token"
    elif available:
        summary = "教学模式与 Label Studio 专业模式均已就绪"
    else:
        summary = "教学模式可用，Label Studio 专业模式未启动"
    return _card(
        "annotation", "标注服务", state, summary,
        "专业模式是可选项；服务未启动时自研教学标注台仍可正常使用。",
        "/annotation", label_studio_available=available,
        gateway_configured=configured, coach_context_connected=True,
        credential_mode=("local_auto" if client.token_source == "local_database" else client.token_source),
    )


def _system_status() -> dict[str, Any]:
    root = get_current_path_service().workspace_root
    usage = shutil.disk_usage(root)
    free_gb = round(usage.free / (1024**3), 1)
    state: Status = "fault" if usage.free < 500 * 1024**2 else "normal"
    return _card(
        "system", "系统体检", state,
        f"学习数据存储可用，剩余空间约 {free_gb} GB" if state == "normal" else "磁盘剩余空间不足 500MB",
        "空间不足可能导致知识库导入、生成图片或标注保存失败。",
        "/settings/status", free_disk_gb=free_gb, storage_writable=True,
    )


def _onboarding_file():
    return get_current_path_service().get_settings_file("capability_center")


def _live_onboarding_fingerprints() -> dict[str, str]:
    """Deterministic fingerprints of each step's dependency config.

    Passed steps record the fingerprint at ``done`` time; ``mark_stale``
    compares against the live value so a changed dependency degrades the step
    to ``stale`` instead of keeping a stale "passed".
    """
    from deeptutor.services.config import load_auth_settings

    out: dict[str, str] = {}
    # account_security: auth enabled + secret storage migrated
    try:
        auth = load_auth_settings()
        migration = get_model_catalog_service().secret_migration_status()
        out["account_security"] = fingerprint(
            f"auth={bool(auth.get('enabled'))}",
            f"migrated={not migration.migration_required}",
        )
    except Exception:
        out["account_security"] = ""
    # llm: active chat model id
    catalog = get_model_catalog_service().load()
    llm = get_model_catalog_service().get_active_model(catalog, "llm") or {}
    out["llm"] = fingerprint("llm", llm.get("id") or llm.get("model") or llm.get("name"))
    # embedding: active embedding model id
    embedding = get_model_catalog_service().get_active_model(catalog, "embedding") or {}
    out["embedding"] = fingerprint(
        "embedding", embedding.get("id") or embedding.get("model") or embedding.get("name")
    )
    # knowledge_base: embedding model + ready KB count + names
    try:
        from deeptutor.multi_user.knowledge_access import current_kb_manager

        manager = current_kb_manager()
        names = sorted(manager.list_knowledge_bases())
        ready = sum(
            1
            for name in names
            if (manager.config.get("knowledge_bases", {}) or {}).get(name, {}).get("status")
            == "ready"
        )
        out["knowledge_base"] = fingerprint(
            "kb", embedding.get("id") or "", ",".join(names), f"ready={ready}"
        )
    except Exception:
        out["knowledge_base"] = ""
    # label_studio: gateway token configured
    from deeptutor.services.label_studio_gateway import LabelStudioClient

    try:
        client = LabelStudioClient()
        out["label_studio"] = fingerprint("ls", "configured" if client.token else "missing")
    except Exception:
        out["label_studio"] = ""
    # imagegen (optional): active imagegen model id
    image = get_model_catalog_service().get_active_model(catalog, "imagegen") or {}
    out["imagegen"] = fingerprint(
        "imagegen", image.get("id") or image.get("model") or image.get("name")
    )
    # mcp (optional): enabled server names
    try:
        from deeptutor.services.mcp import load_mcp_config

        mcp_cfg = load_mcp_config()
        enabled = sorted(
            name for name, config in mcp_cfg.servers.items() if config.enabled
        )
        out["mcp"] = fingerprint("mcp", *enabled)
    except Exception:
        out["mcp"] = ""
    # skill (optional): installed skill names
    try:
        from deeptutor.services.skill import get_skill_service

        skills = sorted(info.name for info in get_skill_service().list_skills())
        out["skill"] = fingerprint("skill", *skills)
    except Exception:
        out["skill"] = ""
    # health_check: derived from live overall status + free disk
    try:
        system = _system_status()
        overall = "ok" if system["status"] == "normal" else system["status"]
        out["health_check"] = fingerprint("health", overall, f"free={system['details'].get('free_disk_gb')}")
    except Exception:
        out["health_check"] = ""
    return out


def _read_onboarding() -> dict[str, Any]:
    path = _onboarding_file()
    state = load_state(path)
    try:
        state = mark_stale(state, _live_onboarding_fingerprints())
    except Exception:
        pass
    state["current_step"] = current_step(state)
    state["completed"] = [key for key in ALL_STEP_KEYS if state["steps"].get(key, {}).get("status") == "passed"]
    state["skipped"] = [key for key in ALL_STEP_KEYS if state["steps"].get(key, {}).get("status") == "skipped"]
    state["optional"] = [key for key, _ in OPTIONAL_STEPS]
    return state


@router.get("/overview")
async def overview() -> dict[str, Any]:
    user = get_current_user()
    models, model_flags = _model_status()
    cards = [models, _knowledge_status(), _extension_status(), await _annotation_status(), _system_status()]
    overall: Status = "fault" if any(item["status"] == "fault" for item in cards) else "limited" if any(item["status"] == "limited" for item in cards) else "normal"
    active = get_current_learning_profile()
    return {
        "overall": overall,
        "cards": cards,
        "is_admin": user.is_admin,
        "active_learning_profile": bool(active),
        "onboarding": _read_onboarding() if user.is_admin else None,
        "optional_capabilities": {"imagegen": model_flags["imagegen"], "label_studio": cards[3]["details"]["label_studio_available"]},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": "报告仅包含能力状态和数量，不包含 API Key、PIN、Token、Cookie、路径或隐藏身份。",
    }


@router.get("/onboarding")
async def get_onboarding() -> dict[str, Any]:
    """Read the resumable onboarding state machine (admin)."""
    if not get_current_user().is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以查看初始化进度")
    return _read_onboarding()


@router.put("/onboarding")
async def update_onboarding(body: OnboardingUpdate) -> dict[str, Any]:
    if not get_current_user().is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以修改初始化进度")
    path = _onboarding_file()
    state = load_state(path)
    try:
        if body.action is not None:
            step_key = body.step_key or current_step(state)
            if body.action == "done":
                live = _live_onboarding_fingerprints()
                state = apply_action(
                    state, step_key, "done", detail=body.detail,
                    fingerprint=live.get(step_key, ""),
                )
            else:
                state = apply_action(state, step_key, body.action, detail=body.detail)
        else:
            # Legacy v1 payload: apply integer completed/skipped lists on top of
            # the current state, mapping to the fixed core step order.
            for number in body.completed:
                state = apply_action(state, _legacy_key_for_index(number), "done")
            for number in body.skipped:
                state = apply_action(state, _legacy_key_for_index(number), "skip")
        if body.dismissed is not None:
            state["dismissed"] = body.dismissed
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(path, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _read_onboarding()


def _legacy_key_for_index(index: int) -> str:
    from deeptutor.services.onboarding import legacy_int_to_key

    return legacy_int_to_key(index)


@router.get("/diagnostics")
async def diagnostics() -> dict[str, Any]:
    """Download-friendly redacted health report; never include secret values."""
    report = await overview()
    report["report_schema_version"] = 1
    return report
