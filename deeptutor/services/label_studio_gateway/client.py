from __future__ import annotations

import os
from typing import Any

import httpx


class LabelStudioUnavailable(RuntimeError):
    pass


class LabelStudioClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.environ.get("LABEL_STUDIO_URL", "http://127.0.0.1:8080")).rstrip("/")
        self.token = token if token is not None else os.environ.get("LABEL_STUDIO_API_TOKEN", "")

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=12.0, follow_redirects=False) as client:
                response = await client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise LabelStudioUnavailable(f"Label Studio 服务不可用：{exc}") from exc
        if response.status_code >= 400:
            raise LabelStudioUnavailable(f"Label Studio 返回 {response.status_code}：{response.text[:200]}")
        if "application/json" in response.headers.get("content-type", ""):
            return response.json()
        return response.text

    async def health(self) -> bool:
        try:
            await self.request("GET", "/health")
            return True
        except LabelStudioUnavailable:
            return False

    async def ensure_task(self, mapping: Any, task_id: str, task: dict[str, Any], profile_root: Any) -> tuple[int, int]:
        if not self.token:
            raise LabelStudioUnavailable("尚未配置 LABEL_STUDIO_API_TOKEN")
        if mapping.project_id is None:
            labels = task.get("labels") or ["目标"]
            task_type = task.get("type", "bbox")
            if task_type in {"classification", "judgment"}:
                controls = "".join(f'<Choice value="{label}"/>' for label in labels)
                config = f'<View><Text name="text" value="$text"/><Choices name="label" toName="text">{controls}</Choices></View>'
            else:
                controls = "".join(f'<Label value="{label}"/>' for label in labels)
                config = f'<View><Image name="image" value="$image"/><RectangleLabels name="label" toName="image">{controls}</RectangleLabels></View>'
            project = await self.request("POST", "/api/projects", json={"title": f"标注星图 · {mapping.profile_id}", "description": "由标注星图专业模式管理", "label_config": config})
            mapping.project_id = int(project["id"])
        if task_id not in mapping.task_map:
            source = task.get("image_url") or task.get("media_url") or task.get("text") or task.get("instruction") or task.get("title", task_id)
            data_key = "text" if task.get("modal") == "text" else "image"
            imported = await self.request("POST", f"/api/projects/{mapping.project_id}/import", json=[{"data": {data_key: source}, "meta": {"deeptutor_task_id": task_id}}])
            ids = imported.get("task_ids", []) if isinstance(imported, dict) else []
            if not ids:
                tasks = await self.request("GET", f"/api/projects/{mapping.project_id}/tasks?page=1&page_size=100")
                ids = [row.get("id") for row in tasks if isinstance(row, dict)]
            if not ids:
                raise LabelStudioUnavailable("任务已导入但无法取得 Label Studio 任务编号")
            mapping.task_map[task_id] = int(ids[-1])
            mapping.save(profile_root)
        return int(mapping.project_id), int(mapping.task_map[task_id])
