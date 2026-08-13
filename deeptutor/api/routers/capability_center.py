"""Secret-free capability overview and first-run onboarding state."""

from __future__ import annotations

from datetime import datetime, timezone
import shutil
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deeptutor.multi_user.context import get_current_learning_profile, get_current_user
from deeptutor.multi_user.paths import get_current_path_service
from deeptutor.services.file_io import atomic_write_json

router = APIRouter()
Status = Literal["normal", "limited", "fault"]


class OnboardingUpdate(BaseModel):
    step: int = Field(ge=1, le=7)
    completed: list[int] = Field(default_factory=list)
    skipped: list[int] = Field(default_factory=list)
    dismissed: bool = False


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


def _read_onboarding() -> dict[str, Any]:
    path = _onboarding_file()
    default = {"step": 1, "completed": [], "skipped": [], "dismissed": False}
    if not path.exists():
        return default
    import json
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return {**default, **data} if isinstance(data, dict) else default


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


@router.put("/onboarding")
async def update_onboarding(body: OnboardingUpdate) -> dict[str, Any]:
    if not get_current_user().is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以修改初始化进度")
    payload = body.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(_onboarding_file(), payload)
    return payload


@router.get("/diagnostics")
async def diagnostics() -> dict[str, Any]:
    """Download-friendly redacted health report; never include secret values."""
    report = await overview()
    report["report_schema_version"] = 1
    return report
