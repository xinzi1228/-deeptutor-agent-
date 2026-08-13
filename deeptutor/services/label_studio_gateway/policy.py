from __future__ import annotations

import re
from urllib.parse import parse_qs

from .identity_map import LabelStudioProfileMap

_ASSET_PREFIXES = ("static/", "react-app/", "dm/", "favicon", "health", "api/version")


class LabelStudioAccessPolicy:
    """Server-side allow list; hiding navigation is never treated as security."""

    def __init__(self, mapping: LabelStudioProfileMap):
        self.mapping = mapping

    def allows(self, method: str, path: str, query: str = "") -> bool:
        clean = path.lstrip("/")
        if clean == "" or clean.startswith(_ASSET_PREFIXES):
            return method.upper() == "GET"
        if clean in {"api/current-user/whoami", "api/current-user/whoami/"}:
            return method.upper() == "GET"
        project_id = self.mapping.project_id
        task_ids = set(self.mapping.task_map.values())
        if not project_id:
            return False
        if clean in {"api/projects", "api/projects/"}:
            return method.upper() == "GET"
        if re.fullmatch(rf"api/projects/{project_id}/?", clean):
            return method.upper() == "GET"
        if re.fullmatch(rf"api/projects/{project_id}/tasks/?", clean):
            return method.upper() == "GET"
        if re.fullmatch(rf"projects/{project_id}/data/?", clean):
            requested = parse_qs(query).get("task", [])
            return method.upper() == "GET" and (not requested or all(int(item) in task_ids for item in requested if item.isdigit()))
        task_match = re.fullmatch(r"api/tasks/(\d+)/?", clean)
        if task_match:
            return int(task_match.group(1)) in task_ids and method.upper() in {"GET", "PATCH"}
        task_annotations = re.fullmatch(r"api/tasks/(\d+)/annotations/?", clean)
        if task_annotations:
            return int(task_annotations.group(1)) in task_ids and method.upper() in {"GET", "POST"}
        # Annotation URLs do not carry a task id. The router resolves every
        # annotation with the service credential and verifies its owning task
        # before the request is forwarded.
        if re.fullmatch(r"api/annotations/\d+/?", clean):
            return method.upper() in {"GET", "PATCH", "DELETE"}
        return False

    def validate_mutation_body(self, path: str, body: bytes) -> bool:
        if not body:
            return True
        import json
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        allowed = set(self.mapping.task_map.values())
        values = payload if isinstance(payload, list) else [payload]
        for item in values:
            if isinstance(item, dict) and "task" in item:
                try:
                    if int(item["task"]) not in allowed:
                        return False
                except (TypeError, ValueError):
                    return False
        return True
