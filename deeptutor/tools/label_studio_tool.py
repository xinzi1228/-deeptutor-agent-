"""Label Studio integration tools for DeepTutor.

Provides tools to create annotation projects, import tasks with ground truth,
fetch annotation results, and run automated quality checks — all through the
Label Studio REST API.
"""

from __future__ import annotations

import json
import os
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.annotation_check import _bbox_dict, _classify_dict
from deeptutor.tools.prompting import load_prompt_hints


LS_BASE_URL = os.environ.get("LABEL_STUDIO_URL", "http://localhost:8080")
LS_API_TOKEN = os.environ.get("LABEL_STUDIO_API_TOKEN", "")


async def _ls_request(method: str, path: str, **kwargs: Any) -> dict:
    """Make an authenticated request to the Label Studio API."""
    import aiohttp

    url = f"{LS_BASE_URL}{path}"
    headers = kwargs.pop("headers", {})
    if LS_API_TOKEN:
        headers["Authorization"] = f"Token {LS_API_TOKEN}"

    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, headers=headers, **kwargs) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(
                    f"Label Studio API error {resp.status}: {text[:300]}"
                )
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}


def _default_label_config(labels: list[str], task_type: str = "bbox") -> str:
    """Generate a Label Studio XML config for a simple labeling task."""
    if task_type == "bbox":
        label_choices = "".join(
            f'<Label value="{l}" background="#{hash(l) & 0xFFFFFF:06x}"/>'
            for l in labels
        )
        return f"""<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    {label_choices}
  </RectangleLabels>
</View>"""
    else:
        label_choices = "".join(
            f'<Choice value="{l}"/>' for l in labels
        )
        return f"""<View>
  <Text name="text" value="$text"/>
  <Choices name="label" toName="text" choice="single">
    {label_choices}
  </Choices>
</View>"""


class LabelStudioCreateProjectTool(BaseTool):
    """Create a Label Studio annotation project."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ls_create_project",
            description=(
                "Create a new annotation project in Label Studio. "
                "Use this tool to set up an annotation workspace before the user starts labeling."
            ),
            parameters=[
                ToolParameter(
                    name="title",
                    type="string",
                    description="Project title, e.g. 'Object Detection Practice 1'.",
                ),
                ToolParameter(
                    name="labels",
                    type="string",
                    description=(
                        "JSON array of label strings, e.g. '[\"cat\",\"dog\",\"bird\"]'."
                    ),
                ),
                ToolParameter(
                    name="task_type",
                    type="string",
                    description="Annotation type: 'bbox' or 'classification'.",
                    required=False,
                    enum=["bbox", "classification"],
                    default="bbox",
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Optional project description / instructions.",
                    required=False,
                    default="",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not LS_API_TOKEN:
            return ToolResult(
                content=(
                    "Label Studio API token not configured. "
                    "Please set the LABEL_STUDIO_API_TOKEN environment variable. "
                    "You can get your token from Label Studio: "
                    "click your avatar → Account & Settings → Access Token."
                ),
                success=False,
            )

        title = kwargs.get("title", "Annotation Practice")
        labels = json.loads(kwargs["labels"]) if isinstance(kwargs["labels"], str) else kwargs["labels"]
        task_type = kwargs.get("task_type", "bbox")
        description = kwargs.get("description", "")

        label_config = _default_label_config(labels, task_type)

        try:
            result = await _ls_request(
                "POST",
                "/api/projects",
                json={
                    "title": title,
                    "description": description,
                    "label_config": label_config,
                },
            )
            project_id = result.get("id", "?")
            return ToolResult(
                content=(
                    f"Project '{title}' created successfully.\n"
                    f"  Project ID: {project_id}\n"
                    f"  Labels: {', '.join(labels)}\n"
                    f"  Type: {task_type}\n"
                    f"  URL: {LS_BASE_URL}/projects/{project_id}\n\n"
                    f"The user can now open this project and start annotating."
                ),
                metadata={"project_id": project_id, "url": f"{LS_BASE_URL}/projects/{project_id}"},
            )
        except Exception as e:
            return ToolResult(content=f"Failed to create project: {e}", success=False)

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)


class LabelStudioCheckTool(BaseTool):
    """Fetch annotations from Label Studio and check against ground truth."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ls_check_annotations",
            description=(
                "Fetch the user's annotations from a Label Studio project and compare them "
                "against ground truth. Computes IOU/F1 for bounding boxes or accuracy for "
                "classification, then returns detailed feedback."
            ),
            parameters=[
                ToolParameter(
                    name="project_id",
                    type="integer",
                    description="Label Studio project ID to check.",
                ),
                ToolParameter(
                    name="task_type",
                    type="string",
                    description="Annotation type: 'bbox' or 'classification'.",
                    required=False,
                    enum=["bbox", "classification"],
                    default="bbox",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not LS_API_TOKEN:
            return ToolResult(
                content=(
                    "Label Studio API token not configured. "
                    "Please set the LABEL_STUDIO_API_TOKEN environment variable."
                ),
                success=False,
            )

        project_id = kwargs["project_id"]
        task_type = kwargs.get("task_type", "bbox")

        try:
            export_data = await _ls_request(
                "GET",
                f"/api/projects/{project_id}/export?exportType=JSON",
            )

            all_results: list[str] = []
            total_f1 = 0.0
            task_count = 0

            for task in export_data:
                annotations = task.get("annotations", [])
                if not annotations:
                    continue

                latest = annotations[-1]
                pred_results = latest.get("result", [])
                gt_results = task.get("predictions", [{}])[0].get("result", []) if task.get("predictions") else []

                if not gt_results:
                    all_results.append(
                        f"Task {task.get('id', '?')}: No ground truth configured. Skipping."
                    )
                    continue

                if task_type == "bbox":
                    pred_boxes = [
                        {
                            "x": int(r["value"]["x"]),
                            "y": int(r["value"]["y"]),
                            "w": int(r["value"]["width"]),
                            "h": int(r["value"]["height"]),
                            "label": r["value"].get("rectanglelabels", ["unknown"])[0],
                        }
                        for r in pred_results
                        if r.get("type") == "rectanglelabels"
                    ]
                    gt_boxes = [
                        {
                            "x": int(r["value"]["x"]),
                            "y": int(r["value"]["y"]),
                            "w": int(r["value"]["width"]),
                            "h": int(r["value"]["height"]),
                            "label": r["value"].get("rectanglelabels", ["unknown"])[0],
                        }
                        for r in gt_results
                        if r.get("type") == "rectanglelabels"
                    ]
                    check = _bbox_dict(pred_boxes, gt_boxes)
                    all_results.append(
                        f"Task {task.get('id', '?')}: "
                        f"Precision={check['precision']:.0%} "
                        f"Recall={check['recall']:.0%} "
                        f"F1={check['f1']:.0%}"
                    )
                    total_f1 += check["f1"]
                    task_count += 1

                else:
                    pred_labels = [
                        {"id": task.get("id", i), "label": r.get("value", {}).get("choices", ["?"])[0]}
                        for i, r in enumerate(pred_results)
                        if r.get("type") == "choices"
                    ]
                    gt_labels = [
                        {"id": task.get("id", i), "label": r.get("value", {}).get("choices", ["?"])[0]}
                        for i, r in enumerate(gt_results)
                        if r.get("type") == "choices"
                    ]
                    check = _classify_dict(pred_labels, gt_labels)
                    all_results.append(
                        f"Task {task.get('id', '?')}: "
                        f"Accuracy={check['accuracy']:.0%}"
                    )
                    total_f1 += check.get("accuracy", 0)
                    task_count += 1

            if task_count == 0:
                return ToolResult(
                    content=(
                        f"No annotated tasks found in project {project_id}. "
                        f"Make sure the user has submitted annotations."
                    ),
                )

            avg_score = total_f1 / task_count if task_count > 0 else 0
            summary = (
                f"Checked {task_count} tasks in project {project_id}:\n\n"
                + "\n".join(all_results)
                + f"\n\nAverage F1/Accuracy: {avg_score:.0%}"
            )

            return ToolResult(
                content=summary,
                metadata={"project_id": project_id, "task_count": task_count, "avg_score": avg_score},
            )

        except Exception as e:
            return ToolResult(
                content=f"Failed to check annotations: {e}\n\nMake sure Label Studio is running at {LS_BASE_URL} and the API token is correct.",
                success=False,
            )

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)
