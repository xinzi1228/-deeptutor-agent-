from __future__ import annotations

import hashlib
import os
from typing import Any
import uuid

import httpx

from .local_credentials import resolve_service_token


class LabelStudioUnavailable(RuntimeError):
    pass


def build_label_studio_result(
    task_type: str,
    predictions: list[dict[str, Any]],
    *,
    image_size: tuple[int, int] = (1000, 1000),
    revision_key: str = "",
) -> list[dict[str, Any]]:
    """Convert learner coordinates to Label Studio's persisted result schema."""
    width = max(1, int(image_size[0]))
    height = max(1, int(image_size[1]))
    if task_type == "bbox":
        results: list[dict[str, Any]] = []
        marker = hashlib.sha256(revision_key.encode("utf-8")).hexdigest()[:12] if revision_key else ""
        for index, row in enumerate(predictions):
            label = str(row.get("label") or "目标")
            results.append({
                "id": f"dt_{marker}_{index}" if marker else str(row.get("id") or uuid.uuid4().hex[:10]),
                "from_name": "label",
                "to_name": "image",
                "type": "rectanglelabels",
                "original_width": width,
                "original_height": height,
                "image_rotation": 0,
                "value": {
                    "x": round(float(row.get("x") or 0) / width * 100, 6),
                    "y": round(float(row.get("y") or 0) / height * 100, 6),
                    "width": round(float(row.get("w") or 0) / width * 100, 6),
                    "height": round(float(row.get("h") or 0) / height * 100, 6),
                    "rotation": 0,
                    "rectanglelabels": [label],
                },
            })
        return results
    if task_type in {"classification", "judgment"}:
        choices = [str(row.get("label")) for row in predictions if row.get("label")]
        marker = hashlib.sha256(revision_key.encode("utf-8")).hexdigest()[:12] if revision_key else uuid.uuid4().hex[:10]
        return [{
            "id": f"dt_{marker}_0",
            "from_name": "label",
            "to_name": "text",
            "type": "choices",
            "value": {"choices": choices},
        }] if choices else []
    return predictions


class LabelStudioClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.environ.get("LABEL_STUDIO_URL", "http://127.0.0.1:8080")).rstrip("/")
        self.token, self.token_source = resolve_service_token(self.base_url, token)

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

    async def create_annotation_revision(
        self,
        *,
        ls_task_id: int,
        task_type: str,
        predictions: list[dict[str, Any]],
        idempotency_key: str,
        image_size: tuple[int, int] = (1000, 1000),
    ) -> dict[str, Any]:
        result = build_label_studio_result(
            task_type,
            predictions,
            image_size=image_size,
            revision_key=idempotency_key,
        )
        expected_ids = {str(row.get("id")) for row in result if isinstance(row, dict) and row.get("id")}
        task = await self.request("GET", f"/api/tasks/{ls_task_id}")
        annotations = task.get("annotations", []) if isinstance(task, dict) else []
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            annotation_result = annotation.get("result", [])
            if not annotation_result and annotation.get("id") is not None:
                full = await self.request("GET", f"/api/annotations/{annotation['id']}")
                annotation_result = full.get("result", []) if isinstance(full, dict) else []
            actual_ids = {
                str(row.get("id"))
                for row in annotation_result
                if isinstance(row, dict) and row.get("id")
            }
            if expected_ids and actual_ids == expected_ids:
                return {
                    "provider": "label_studio",
                    "task_id": ls_task_id,
                    "annotation_id": annotation.get("id"),
                    "idempotency_key": idempotency_key,
                    "reused": True,
                }
        created = await self.request(
            "POST",
            f"/api/tasks/{ls_task_id}/annotations",
            json={"result": result, "was_cancelled": False},
        )
        if not isinstance(created, dict) or created.get("id") is None:
            raise LabelStudioUnavailable("Label Studio 已接收提交，但没有返回正式修订编号")
        return {
            "provider": "label_studio",
            "task_id": ls_task_id,
            "annotation_id": created["id"],
            "idempotency_key": idempotency_key,
            "reused": False,
        }
