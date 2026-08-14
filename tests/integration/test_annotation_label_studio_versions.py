from __future__ import annotations

import asyncio

from deeptutor.services.label_studio_gateway.client import (
    LabelStudioClient,
    build_label_studio_result,
)


def test_bbox_revision_uses_label_studio_percentage_coordinates() -> None:
    result = build_label_studio_result(
        "bbox",
        [{"x": 100, "y": 50, "w": 200, "h": 100, "label": "车辆"}],
        image_size=(1000, 500),
    )

    assert result[0]["type"] == "rectanglelabels"
    assert result[0]["value"] == {
        "x": 10.0,
        "y": 10.0,
        "width": 20.0,
        "height": 20.0,
        "rotation": 0,
        "rectanglelabels": ["车辆"],
    }


def test_revision_creation_reuses_matching_idempotency_key() -> None:
    client = object.__new__(LabelStudioClient)
    calls: list[tuple[str, str]] = []
    expected = build_label_studio_result(
        "bbox",
        [{"x": 1, "y": 2, "w": 3, "h": 4, "label": "车"}],
        revision_key="revision-key",
    )

    async def request(method: str, path: str, **kwargs):
        calls.append((method, path))
        if method == "GET":
            return {"annotations": [{"id": 91, "result": expected}]}
        raise AssertionError("existing revision must not be posted twice")

    client.request = request  # type: ignore[method-assign]
    revision = asyncio.run(client.create_annotation_revision(
        ls_task_id=17,
        task_type="bbox",
        predictions=[{"x": 1, "y": 2, "w": 3, "h": 4, "label": "车"}],
        idempotency_key="revision-key",
        image_size=(1000, 1000),
    ))

    assert revision["annotation_id"] == 91
    assert revision["reused"] is True
    assert calls == [("GET", "/api/tasks/17")]
