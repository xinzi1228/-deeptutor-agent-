from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from deeptutor.api.routers.auth import TokenPayload, require_admin
from deeptutor.multi_user.context import (
    get_current_learning_profile,
    get_current_user,
    require_learning_profile_write_access,
)
from deeptutor.multi_user.paths import get_current_learning_profile_root
from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.annotation_scoring import (
    AnnotationScoreStore,
    BboxScorer,
    parse_label_studio_bbox_result,
)
from deeptutor.services.label_studio_gateway import (
    LabelStudioAccessPolicy,
    LabelStudioClient,
    LabelStudioProfileMap,
    LabelStudioSessionBridge,
    LabelStudioUnavailable,
)

router = APIRouter()
PROXY_PREFIX = "/api/v1/label-studio/proxy"


class ProfessionalTaskAssignments(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=100)


def _context(*, write: bool = False) -> tuple[object, object, LabelStudioProfileMap]:
    access = get_current_learning_profile()
    if access is None:
        raise HTTPException(status_code=423, detail="请先解锁学习档案")
    if write:
        try:
            access = require_learning_profile_write_access()
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        root = get_current_learning_profile_root(require_unlocked=True)
    except PermissionError as exc:
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    if root is None:
        raise HTTPException(status_code=423, detail="请先解锁学习档案")
    return access, root, LabelStudioProfileMap.load(root, access.profile_id)


@router.get("/status")
async def status() -> dict:
    access, root, mapping = _context()
    client = LabelStudioClient()
    available = await client.health()
    return {
        "available": available,
        "configured": bool(client.token),
        "credential_mode": "local_auto" if client.token_source == "local_database" else client.token_source,
        "mapping": mapping.public_dict(),
        "management_url": client.base_url if get_current_user().role == "admin" else None,
        "mode": "profile_project_same_origin_gateway",
    }


@router.post("/prepare/{task_id}")
async def prepare(task_id: str) -> dict:
    from deeptutor.api.routers.annotation import _task_bank

    access, root, mapping = _context(write=True)
    task = _task_bank().get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"找不到任务 {task_id}")
    allowed = mapping.assigned([
        key for key, value in _task_bank().items() if value.get("modal") in {"image", "text"}
    ])
    if task_id not in allowed:
        raise HTTPException(status_code=403, detail="这项专业任务尚未分配给当前学习档案")
    client = LabelStudioClient()
    try:
        project_id, ls_task_id = await client.ensure_task(mapping, task_id, task, root)
    except LabelStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    AnnotationAttemptStore(root).set_current(
        task_id=task_id,
        mode="professional",
        stage="opened",
        summary={"project_id": project_id, "ls_task_id": ls_task_id, "title": task.get("title", task_id)},
    )
    return {
        "task_id": task_id,
        "project_id": project_id,
        "ls_task_id": ls_task_id,
        "workbench_url": f"{PROXY_PREFIX}/projects/{project_id}/data?task={ls_task_id}",
        "task_list_url": f"{PROXY_PREFIX}/projects/{project_id}/data",
    }


@router.get("/professional/tasks")
async def professional_tasks() -> dict:
    from deeptutor.api.routers.annotation import _task_bank

    _access, _root, mapping = _context()
    bank = _task_bank()
    starter = [key for key, value in bank.items() if value.get("modal") in {"image", "text"}]
    assigned = mapping.assigned(starter)
    return {
        "tasks": [
            {
                "id": task_id,
                "title": bank[task_id].get("title", task_id),
                "type": bank[task_id].get("type", "bbox"),
                "modal": bank[task_id].get("modal", "image"),
                "difficulty": bank[task_id].get("difficulty", ""),
            }
            for task_id in assigned
            if task_id in bank
        ],
        "assignment_mode": "explicit" if mapping.assigned_task_ids else "starter_set",
    }


@router.put("/professional/tasks")
async def assign_professional_tasks(
    body: ProfessionalTaskAssignments,
    _: TokenPayload = Depends(require_admin),
) -> dict:
    from deeptutor.api.routers.annotation import _task_bank

    _access, root, mapping = _context(write=True)
    bank = _task_bank()
    invalid = [task_id for task_id in body.task_ids if task_id not in bank or bank[task_id].get("modal") not in {"image", "text"}]
    if invalid:
        raise HTTPException(status_code=422, detail=f"无效专业任务：{', '.join(invalid[:5])}")
    mapping.assigned_task_ids = list(dict.fromkeys(body.task_ids))
    mapping.save(root)
    return {"assigned_task_ids": mapping.assigned_task_ids}


@router.post("/sync/{task_id}")
async def sync_professional_attempt(task_id: str) -> dict:
    from deeptutor.api.routers.annotation import _reference_version, _task_bank

    access, root, mapping = _context(write=True)
    ls_task_id = mapping.task_map.get(task_id)
    if not ls_task_id:
        raise HTTPException(status_code=404, detail="该题尚未进入专业模式")
    client = LabelStudioClient()
    try:
        task = await client.request("GET", f"/api/tasks/{ls_task_id}")
    except LabelStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    annotations = task.get("annotations", []) if isinstance(task, dict) else []
    if not annotations:
        return {"synced": False, "detail": "Label Studio 中还没有已保存标注"}
    latest = annotations[-1]
    annotation_id = latest.get("id", "unknown")
    task_definition = _task_bank().get(task_id)
    if task_definition is None:
        raise HTTPException(status_code=404, detail=f"找不到任务 {task_id}")
    task_type = str(task_definition.get("type") or "bbox")
    raw_results = latest.get("result", [])
    result_rows = [row for row in raw_results if isinstance(row, dict)] if isinstance(raw_results, list) else []
    metrics: dict[str, object] = {}
    report = "Label Studio 专业模式标注已同步；当前题型暂不支持统一自动评分。"
    scoring = None
    payload: dict[str, object] = {
        "annotations": result_rows,
        "ls_task_id": ls_task_id,
        "ls_annotation_id": annotation_id,
    }
    if task_type == "bbox":
        predictions, image_size = parse_label_studio_bbox_result(result_rows)
        ground_truth = task_definition.get("ground_truth", [])
        ground_truth_rows = [row for row in ground_truth if isinstance(row, dict)] if isinstance(ground_truth, list) else []
        scoring = BboxScorer().score(
            predictions,
            ground_truth_rows,
            reference_version=_reference_version(task_id, ground_truth_rows),
            image_size=image_size,
        )
        metrics = scoring.metrics
        report = scoring.report
        payload.update({"predictions": predictions, "image_size": f"{image_size[0]}x{image_size[1]}"})
    attempt, created = AnnotationAttemptStore(root).append_attempt(
        task_id=task_id,
        task_type=task_type,
        mode="professional",
        payload=payload,
        metrics=metrics,
        report=report,
        idempotency_key=f"ls:{ls_task_id}:{annotation_id}",
        source="professional_gateway",
        sync_status="synced",
        revision={
            "provider": "label_studio",
            "task_id": ls_task_id,
            "annotation_id": annotation_id,
            "unique_id": latest.get("unique_id", ""),
        },
    )
    score_record = None
    if scoring is not None:
        score_record = AnnotationScoreStore(root).record(
            task_id=task_id,
            attempt_id=str(attempt.get("id") or ""),
            metrics=scoring.metrics,
            rule_version=scoring.rule_version,
            reference_version=scoring.reference_version,
            score_hash=scoring.score_hash,
        )
    return {"synced": True, "created": created, "attempt": attempt, "score_record": score_record}


def _rewrite_text(text: str) -> str:
    pairs = (
        ('"/static/', f'"{PROXY_PREFIX}/static/'),
        ("'/static/", f"'{PROXY_PREFIX}/static/"),
        ("url(/static/", f"url({PROXY_PREFIX}/static/"),
        ('"/react-app/', f'"{PROXY_PREFIX}/react-app/'),
        ("'/react-app/", f"'{PROXY_PREFIX}/react-app/"),
        ('"/api/', f'"{PROXY_PREFIX}/api/'),
        ("'/api/", f"'{PROXY_PREFIX}/api/"),
        ('"/projects/', f'"{PROXY_PREFIX}/projects/'),
        ("'/projects/", f"'{PROXY_PREFIX}/projects/"),
        ('href="/user/', f'href="{PROXY_PREFIX}/user/'),
    )
    for old, new in pairs:
        text = text.replace(old, new)
    # Normalize any double-prefix back to a single proxy prefix. Label
    # Studio's HTML/JS can reference assets that were already rewritten
    # (e.g. a nested bundle), which would otherwise produce
    # /proxy/.../proxy/... paths that 404 on our side.
    double = PROXY_PREFIX + PROXY_PREFIX
    while double in text:
        text = text.replace(double, PROXY_PREFIX)
    return text


_REALTIME_BRIDGE = r"""
<script data-deeptutor-label-studio-bridge="1">
(() => {
  if (window.__deeptutorLsBridge) return;
  window.__deeptutorLsBridge = true;
  const send = (event, extra = {}) => window.parent.postMessage({
    type: "label_studio_workbench_event", event,
    taskId: new URLSearchParams(location.search).get("task") || "", ...extra
  }, location.origin);
  const countRegions = () => {
    const selectors = [".lsf-region", ".htx-region", "[data-testid*='region']", "[class*='Region']"];
    return Math.max(0, ...selectors.map((selector) => document.querySelectorAll(selector).length));
  };
  const selectedObjectId = () => {
    const selected = document.querySelector("[data-testid*='region'][aria-selected='true'], [class*='Region'][class*='selected'], .lsf-region.selected, .htx-region.selected");
    if (!selected) return "";
    return String(selected.getAttribute("data-id") || selected.getAttribute("data-region-id") || selected.id || "").slice(0, 120);
  };
  const activeTool = () => {
    const button = document.querySelector("button[aria-pressed='true'], [role='button'][aria-pressed='true']");
    if (!button) return "";
    return String(button.getAttribute("data-tool") || button.getAttribute("aria-label") || button.getAttribute("title") || "").slice(0, 40);
  };
  const snapshot = () => ({ annotationCount: countRegions(), selectedObjectId: selectedObjectId(), tool: activeTool() });
  let lastCount = -1;
  let timer = 0;
  const inspect = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const count = countRegions();
      if (count !== lastCount) { lastCount = count; send("draft_changed", snapshot()); }
    }, 180);
  };
  new MutationObserver(inspect).observe(document.documentElement, { subtree: true, childList: true, attributes: true });
  document.addEventListener("click", (event) => {
    const target = event.target && event.target.closest ? event.target.closest("button,[role='button']") : null;
    if (!target) return;
    const text = `${target.getAttribute("aria-label") || ""} ${target.getAttribute("title") || ""} ${target.textContent || ""}`.toLowerCase();
    if (/undo|撤销/.test(text)) send("undo", snapshot());
    if (/submit|update|save|保存|提交/.test(text)) send("save", snapshot());
    const label = target.getAttribute("data-label") || target.getAttribute("aria-label") || "";
    if (label && /label|标签/i.test(text)) send("label_changed", { label: String(label).slice(0, 80) });
    window.setTimeout(() => send("selection_changed", snapshot()), 0);
  }, true);
  window.addEventListener("popstate", () => send("task_changed"));
  send("bridge_ready", { ...snapshot(), bridgeVersion: 2 });
  inspect();
})();
</script>
"""


def _inject_realtime_bridge(text: str, path: str) -> str:
    """Inject the optional, data-minimal LS workbench bridge into HTML only."""
    if "text/html" not in text[:500].lower() and "</body>" not in text.lower():
        return text
    if not path.lstrip("/").startswith("projects/") or "data-deeptutor-label-studio-bridge" in text:
        return text
    return re.sub(r"</body\s*>", _REALTIME_BRIDGE + "</body>", text, count=1, flags=re.I)


@router.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy(path: str, request: Request) -> Response:
    access, root, mapping = _context(
        write=request.method not in {"GET", "HEAD", "OPTIONS"}
    )
    query = request.url.query
    policy = LabelStudioAccessPolicy(mapping)
    if not policy.allows(request.method, path, query):
        raise HTTPException(status_code=403, detail="当前学习档案无权访问该 Label Studio 资源")
    client = LabelStudioClient()
    annotation_match = re.fullmatch(r"api/annotations/(\d+)/?", path.lstrip("/"))
    if annotation_match:
        # Label Studio's annotation URL does not carry a task id. Resolve it
        # with the server credential before forwarding so a guessed annotation
        # id can never expose or modify another learning profile's work.
        try:
            annotation = await client.request(
                "GET", f"/api/annotations/{annotation_match.group(1)}"
            )
        except LabelStudioUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        owner = annotation.get("task") if isinstance(annotation, dict) else None
        if isinstance(owner, dict):
            owner = owner.get("id")
        try:
            owner_id = int(owner)
        except (TypeError, ValueError):
            raise HTTPException(status_code=403, detail="无法确认该标注所属任务") from None
        if owner_id not in set(mapping.task_map.values()):
            raise HTTPException(status_code=403, detail="当前学习档案无权访问该标注")

    body = await request.body()
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not policy.validate_mutation_body(path, body):
        raise HTTPException(status_code=403, detail="提交内容包含未分配给当前档案的任务")
    bridge = LabelStudioSessionBridge(client.base_url, access.profile_id, mapping.email_alias)
    target = "/" + path.lstrip("/") + (f"?{query}" if query else "")
    try:
        upstream = await bridge.forward(request.method, target, headers=dict(request.headers), body=body)
    except (RuntimeError, LabelStudioUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    content = upstream.content
    content_type = upstream.headers.get("content-type", "application/octet-stream")
    if path.rstrip("/") == "api/projects" and "application/json" in content_type:
        try:
            payload = upstream.json()
            rows = payload.get("results", []) if isinstance(payload, dict) else payload
            filtered = [row for row in rows if isinstance(row, dict) and row.get("id") == mapping.project_id]
            if isinstance(payload, dict):
                payload.update({"results": filtered, "count": len(filtered)})
            else:
                payload = filtered
            return JSONResponse(payload, status_code=upstream.status_code)
        except (ValueError, json.JSONDecodeError):
            pass
    is_html = "text/html" in content_type
    is_css = "text/css" in content_type
    if is_html or is_css:
        # Only HTML/CSS need URL rewriting. JS bundles (runtime/vendor/main,
        # up to ~2.5MB) contain no bare /static/ or /react-app/ paths and
        # rewriting them on every request is expensive (multiple full-file
        # scans that add several seconds of latency through the proxy).
        rewritten = _rewrite_text(upstream.text)
        if is_html:
            rewritten = _inject_realtime_bridge(rewritten, path)
        content = rewritten.encode("utf-8")
    headers: dict[str, str] = {"Cache-Control": upstream.headers.get("cache-control", "no-store")}
    location = upstream.headers.get("location")
    if location and location.startswith("/"):
        headers["Location"] = PROXY_PREFIX + location
    return Response(content=content, status_code=upstream.status_code, media_type=content_type.split(";", 1)[0], headers=headers)
