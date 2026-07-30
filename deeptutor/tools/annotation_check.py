"""Annotation check tool — evaluates labeling quality against ground truth."""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.prompting import load_prompt_hints


def _calculate_iou(box1: dict, box2: dict) -> float:
    ax1, ay1 = box1["x"], box1["y"]
    ax2, ay2 = box1["x"] + box1["w"], box1["y"] + box1["h"]
    bx1, by1 = box2["x"], box2["y"]
    bx2, by2 = box2["x"] + box2["w"], box2["y"] + box2["h"]
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    intersection = inter_w * inter_h
    area1 = box1["w"] * box1["h"]
    area2 = box2["w"] * box2["h"]
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0.0


def _bbox_report(predictions: list[dict], ground_truth: list[dict], iou_threshold: float = 0.5) -> str:
    """Evaluate bounding boxes with detailed educational feedback (returns string)."""
    if not predictions and not ground_truth:
        return "No predictions and no ground truth provided."

    if not predictions:
        return (
            f"You didn't submit any bounding boxes, but there are {len(ground_truth)} objects to find.\n"
            f"Example format: {{\"x\": 80, \"y\": 120, \"w\": 140, \"h\": 160, \"label\": \"cat\"}}"
        )

    all_ious: list[tuple[float, int, int]] = []
    for pi, pred in enumerate(predictions):
        for gj, gt in enumerate(ground_truth):
            if pred.get("label", "") != gt.get("label", ""):
                continue
            iou = _calculate_iou(pred, gt)
            if iou >= iou_threshold:
                all_ious.append((iou, pi, gj))

    all_ious.sort(key=lambda x: x[0], reverse=True)
    matched_pred: set[int] = set()
    matched_gt: set[int] = set()
    matches: list[dict] = []

    for iou, pi, gj in all_ious:
        if pi not in matched_pred and gj not in matched_gt:
            matches.append({"pred_idx": pi, "gt_idx": gj, "iou": iou})
            matched_pred.add(pi)
            matched_gt.add(gj)

    tp = len(matches)
    fp = len(predictions) - tp
    fn = len(ground_truth) - tp
    precision = tp / len(predictions) if predictions else 0
    recall = tp / len(ground_truth) if ground_truth else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    lines = ["## Bounding Box Results\n"]
    lines.append(f"**Precision**: {precision:.0%}  — when you draw a box, how often is it correct?")
    lines.append(f"**Recall**: {recall:.0%}  — how many actual objects did you find?")
    lines.append(f"**F1 Score**: {f1:.0%}  — balanced overall score")
    lines.append(f"**Summary**: {tp} correct | {fp} wrong/extra | {fn} missed\n")

    if matches:
        lines.append("### Correct Matches")
        for m in matches:
            pred = predictions[m["pred_idx"]]
            lines.append(f"- Box ({pred['x']},{pred['y']}) {pred['w']}x{pred['h']} '{pred.get('label','?')}' — IOU={m['iou']:.2f}. Well done!")

    wrong_label_items = []
    extra_items = []
    for pi, pred in enumerate(predictions):
        if pi in matched_pred:
            continue
        best_match_label = None
        for gt in ground_truth:
            if pi not in matched_pred and _calculate_iou(pred, gt) >= iou_threshold:
                best_match_label = gt.get("label", "?")
                break
        if best_match_label:
            wrong_label_items.append(
                f"- Box ({pred['x']},{pred['y']}): you labeled '{pred.get('label','?')}' but it's actually '{best_match_label}'. Position is correct, check the label."
            )
        else:
            best_iou = max((_calculate_iou(pred, gt) for gt in ground_truth), default=0)
            extra_items.append(
                f"- Box ({pred['x']},{pred['y']}) '{pred.get('label','?')}': no matching object here (best overlap={best_iou:.0%}). Extra box."
            )

    if wrong_label_items:
        lines.append("\n### Label Mistakes")
        lines.extend(wrong_label_items)
    if extra_items:
        lines.append(f"\n### Extra Boxes ({len(extra_items)})")
        lines.extend(extra_items)

    missed = [gj for gj in range(len(ground_truth)) if gj not in matched_gt]
    if missed:
        lines.append(f"\n### Missed ({len(missed)})")
        for gj in missed:
            gt = ground_truth[gj]
            lines.append(f"- '{gt.get('label','?')}' at ({gt['x']},{gt['y']}) {gt['w']}x{gt['h']}: not found!")

    lines.append("\n---")
    if f1 >= 0.8:
        lines.append("**Great job!** Ready for a harder task?")
    elif recall < precision:
        lines.append("**Tip**: Recall < Precision — you're too conservative. Try to find EVERY object.")
    elif precision < recall:
        lines.append("**Tip**: Precision < Recall — too many boxes. Only draw when confident.")
    else:
        lines.append("**Tip**: Slow down. Make each box tightly wrap its object.")

    return "\n".join(lines)


def _classify_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate classification with educational feedback (returns string)."""
    if not predictions and not ground_truth:
        return "No predictions and no ground truth provided."

    if not predictions:
        return f"{len(ground_truth)} items to classify but no answers submitted."

    lines = ["## Classification Results\n"]
    gt_by_id = {gt.get("id", i): gt for i, gt in enumerate(ground_truth)}
    correct = 0
    total = len(ground_truth)

    for i, pred in enumerate(predictions):
        item_id = pred.get("id", i)
        gt = gt_by_id.get(item_id)
        if gt and pred.get("label") == gt.get("label"):
            correct += 1
            lines.append(f"- Item {item_id}: Correct — '{pred['label']}'")
        elif gt:
            lines.append(f"- Item {item_id}: Wrong — you said '{pred.get('label','?')}' but correct is '{gt.get('label','?')}'")
        else:
            lines.append(f"- Item {item_id}: Extra — no ground truth for this id")

    for item_id, gt in gt_by_id.items():
        if not any(p.get("id", i) == item_id for i, p in enumerate(predictions)):
            lines.append(f"- Item {item_id}: Missed — '{gt.get('label','?')}' not labeled")

    accuracy = correct / total if total > 0 else 0
    lines.append(f"\n**Accuracy**: {accuracy:.0%} ({correct}/{total})")

    lines.append("\n---")
    if accuracy == 1.0:
        lines.append("**Perfect!** All correct. Ready for harder distinctions?")
    elif accuracy >= 0.6:
        lines.append(f"**Good effort.** {correct}/{total} correct. Review the wrong ones.")
    else:
        lines.append(f"**Keep practicing.** {correct}/{total} correct. Read carefully before deciding.")

    return "\n".join(lines)


# Dict-returning versions for programmatic use (e.g. Label Studio integration)
def _bbox_dict(predictions: list[dict], ground_truth: list[dict], iou_threshold: float = 0.5) -> dict:
    all_ious: list[tuple[float, int, int]] = []
    for pi, pred in enumerate(predictions):
        for gj, gt in enumerate(ground_truth):
            if pred.get("label", "") != gt.get("label", ""):
                continue
            iou = _calculate_iou(pred, gt)
            if iou >= iou_threshold:
                all_ious.append((iou, pi, gj))

    all_ious.sort(key=lambda x: x[0], reverse=True)
    matched_pred: set[int] = set()
    matched_gt: set[int] = set()
    for iou, pi, gj in all_ious:
        if pi not in matched_pred and gj not in matched_gt:
            matched_pred.add(pi)
            matched_gt.add(gj)
    tp = len(matched_pred)
    return {
        "precision": round(tp / len(predictions), 4) if predictions else 0,
        "recall": round(tp / len(ground_truth), 4) if ground_truth else 0,
        "f1": 0,  # computed below
        "matched_count": tp,
        "extra_count": len(predictions) - tp,
        "missed_count": len(ground_truth) - tp,
    }


def _classify_dict(predictions: list[dict], ground_truth: list[dict]) -> dict:
    gt_by_id = {gt.get("id", i): gt for i, gt in enumerate(ground_truth)}
    correct = sum(1 for p in predictions if gt_by_id.get(p.get("id")) and p.get("label") == gt_by_id[p.get("id")].get("label"))
    total = len(ground_truth)
    return {"accuracy": round(correct / total, 4) if total else 0, "correct": correct, "total": total}


class AnnotationCheckTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="annotation_check",
            description=(
                "Evaluate annotation quality by comparing predictions against ground truth. "
                "For bounding boxes: computes IOU, precision, recall, F1. "
                "For classification: computes per-item accuracy. "
                "Returns a detailed educational report with per-item feedback."
            ),
            parameters=[
                ToolParameter(
                    name="predictions",
                    type="string",
                    description=(
                        "JSON string of user's predictions. "
                        "Bbox: [{\"x\":80,\"y\":120,\"w\":140,\"h\":160,\"label\":\"cat\"},...]. "
                        "Classification: [{\"id\":1,\"label\":\"positive\"},...]."
                    ),
                ),
                ToolParameter(
                    name="ground_truth",
                    type="string",
                    description="JSON string of correct answers, same format. You prepare this from your task description.",
                ),
                ToolParameter(
                    name="task_type",
                    type="string",
                    description="'bbox' or 'classification'.",
                    required=False,
                    enum=["bbox", "classification"],
                    default="bbox",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        task_type = kwargs.get("task_type", "bbox")
        predictions_raw = kwargs.get("predictions", "[]")
        ground_truth_raw = kwargs.get("ground_truth", "[]")

        try:
            predictions = json.loads(predictions_raw) if isinstance(predictions_raw, str) else predictions_raw
            ground_truth = json.loads(ground_truth_raw) if isinstance(ground_truth_raw, str) else ground_truth_raw
        except json.JSONDecodeError as e:
            return ToolResult(
                content=f"Invalid JSON: {e}\n\nExpected format:\nBbox: [{{\"x\":80,\"y\":120,\"w\":140,\"h\":160,\"label\":\"cat\"}}]\nClassification: [{{\"id\":1,\"label\":\"positive\"}}]",
                success=False,
            )

        if task_type == "classification":
            content = _classify_report(predictions, ground_truth)
        else:
            content = _bbox_report(predictions, ground_truth)

        return ToolResult(content=content)

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)
