from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import AnnotationScoreResult


def parse_label_studio_bbox_result(
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], tuple[int, int]]:
    """Convert saved Label Studio rectangle results back to pixel coordinates."""
    predictions: list[dict[str, Any]] = []
    image_size = (1000, 1000)
    for row in results:
        if not isinstance(row, dict) or row.get("type") != "rectanglelabels":
            continue
        value = row.get("value")
        if not isinstance(value, dict):
            continue
        width = max(1, int(row.get("original_width") or image_size[0]))
        height = max(1, int(row.get("original_height") or image_size[1]))
        image_size = (width, height)
        labels = value.get("rectanglelabels")
        label = str(labels[0]) if isinstance(labels, list) and labels else "目标"
        try:
            predictions.append(
                {
                    "id": str(row.get("id") or f"ls-box-{len(predictions) + 1}"),
                    "x": round(float(value.get("x") or 0) / 100 * width, 6),
                    "y": round(float(value.get("y") or 0) / 100 * height, 6),
                    "w": round(float(value.get("width") or 0) / 100 * width, 6),
                    "h": round(float(value.get("height") or 0) / 100 * height, 6),
                    "label": label,
                }
            )
        except (TypeError, ValueError):
            continue
    return predictions, image_size


class BboxScorer:
    """Deterministic bbox scorer; language models may explain but never set metrics."""

    def __init__(self, *, iou_threshold: float = 0.5, rule_version: str = "bbox-iou-0.5-v1") -> None:
        self.iou_threshold = iou_threshold
        self.rule_version = rule_version

    def score(
        self,
        predictions: list[dict[str, Any]],
        ground_truth: list[dict[str, Any]],
        *,
        reference_version: str,
        image_size: tuple[int, int] = (1000, 1000),
    ) -> AnnotationScoreResult:
        from deeptutor.tools.annotation_check import _bbox_dict, _bbox_report

        metrics = _bbox_dict(predictions, ground_truth, self.iou_threshold)
        report, _details = _bbox_report(
            predictions,
            ground_truth,
            iou_threshold=self.iou_threshold,
            image_size=image_size,
        )
        canonical = json.dumps(
            {
                "predictions": predictions,
                "ground_truth": ground_truth,
                "rule_version": self.rule_version,
                "reference_version": reference_version,
                "image_size": image_size,
                "metrics": metrics,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return AnnotationScoreResult(
            metrics=metrics,
            report=report,
            rule_version=self.rule_version,
            reference_version=reference_version,
            score_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
