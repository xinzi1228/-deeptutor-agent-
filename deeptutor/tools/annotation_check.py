"""Annotation check tool — evaluates labeling quality against ground truth."""

from __future__ import annotations

import json
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.tools.chart_cards import build_scorecard_chart, render_scorecard_png
from deeptutor.tools.prompting import load_prompt_hints


def collect_public_artifacts(workdir: str) -> list[Any]:
    """Discover public artifacts under *workdir* (module-level alias for monkeypatching in tests)."""
    from deeptutor.services.sandbox.artifacts import collect_public_artifacts as _real

    return _real(workdir)


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


# ------------------------------------------------------- quality heuristics

def check_edge_proximity(boxes: list[dict], image_size: tuple[int, int], threshold: int = 5) -> list[dict]:
    """Flag boxes touching the image edge (within threshold px) — may be drawn over the edge or miss edge objects."""
    img_w, img_h = image_size
    checks = []
    for i, box in enumerate(boxes):
        x, y = box["x"], box["y"]
        w, h = box["w"], box["h"]
        if x < threshold or y < threshold or (x + w) > (img_w - threshold) or (y + h) > (img_h - threshold):
            checks.append({
                "rule": "edge",
                "box_idx": i,
                "message": f"框 {i + 1} 贴到图像边缘 (距边界 < {threshold}px)，可能画过头或漏了边缘目标",
            })
    return checks


def _contains(box_a: dict, box_b: dict) -> bool:
    """True if box_a fully contains box_b."""
    return (
        box_a["x"] <= box_b["x"]
        and box_a["y"] <= box_b["y"]
        and box_a["x"] + box_a["w"] >= box_b["x"] + box_b["w"]
        and box_a["y"] + box_a["h"] >= box_b["y"] + box_b["h"]
    )


def check_overlap(boxes: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Flag heavily overlapping boxes (not nested) — likely duplicate annotations of the same object."""
    checks = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            iou = _calculate_iou(boxes[i], boxes[j])
            # skip nested boxes (one fully inside the other) — treat as acceptable;
            # pixel-identical boxes are duplicate annotations and must still be flagged
            nested = (_contains(boxes[i], boxes[j]) or _contains(boxes[j], boxes[i])) and boxes[i] != boxes[j]
            if iou > iou_threshold and not nested:
                checks.append({
                    "rule": "overlap",
                    "box_idx": i,
                    "other_idx": j,
                    "message": f"框 {i + 1} 与框 {j + 1} 高度重叠 (IOU={iou:.2f})，可能重复标注同一目标",
                })
                break  # only flag once per box
    return checks


def check_tightness(boxes: list[dict], ratio_threshold: float = 5.0) -> list[dict]:
    """Flag boxes with extreme aspect ratio (too wide/thin) — likely too much padding or clipped object."""
    checks = []
    for i, box in enumerate(boxes):
        w, h = box["w"], box["h"]
        if w <= 0 or h <= 0:
            continue
        ratio = max(w, h) / min(w, h)
        if ratio > ratio_threshold:
            checks.append({
                "rule": "tightness",
                "box_idx": i,
                "message": f"框 {i + 1} 宽高比异常 ({ratio:.1f}:1)，可能留白过多或切到目标",
            })
    return checks


def quality_checks(boxes: list[dict], image_size: tuple[int, int]) -> list[dict]:
    """Aggregate all heuristic quality checks (no ground truth needed)."""
    checks = []
    checks.extend(check_edge_proximity(boxes, image_size))
    checks.extend(check_overlap(boxes))
    checks.extend(check_tightness(boxes))
    return checks


def _bbox_metrics(predictions: list[dict], ground_truth: list[dict], iou_threshold: float = 0.5) -> dict:
    """Compute bbox evaluation metrics (tp/fp/fn/precision/recall/f1)."""
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
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "matches": matches, "matched_pred": matched_pred, "matched_gt": matched_gt,
    }


def _bbox_report(
    predictions: list[dict],
    ground_truth: list[dict],
    iou_threshold: float = 0.5,
    image_size: tuple[int, int] = (1000, 1000),
) -> tuple[str, dict]:
    """Evaluate bounding boxes with educational feedback, returns (content, metrics)."""
    metrics = _bbox_metrics(predictions, ground_truth, iou_threshold)

    if not predictions and not ground_truth:
        return "No predictions and no ground truth provided.", metrics

    if not predictions:
        return (
            f"You didn't submit any bounding boxes, but there are {len(ground_truth)} objects to find.\n"
            f"Example format: {{\"x\": 80, \"y\": 120, \"w\": 140, \"h\": 160, \"label\": \"cat\"}}"
        ), metrics

    tp = metrics["tp"]
    fp = metrics["fp"]
    fn = metrics["fn"]
    precision = metrics["precision"]
    recall = metrics["recall"]
    f1 = metrics["f1"]
    matches = metrics["matches"]
    matched_pred = metrics["matched_pred"]
    matched_gt = metrics["matched_gt"]

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

    qchecks = quality_checks(predictions, image_size)
    if qchecks:
        lines.append("\n### 质量检查 (无需标准答案)")
        for qc in qchecks:
            lines.append(f"- {qc['message']}")

    lines.append("\n---")
    if f1 >= 0.8:
        lines.append("**Great job!** Ready for a harder task?")
    elif recall < precision:
        lines.append("**Tip**: Recall < Precision — you're too conservative. Try to find EVERY object.")
    elif precision < recall:
        lines.append("**Tip**: Precision < Recall — too many boxes. Only draw when confident.")
    else:
        lines.append("**Tip**: Slow down. Make each box tightly wrap its object.")

    return "\n".join(lines), metrics


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


_TRUE_ANSWER_SYNONYMS = {"true", "correct", "right", "yes", "1", "对", "正确", "是"}
_FALSE_ANSWER_SYNONYMS = {"false", "incorrect", "no", "0", "错", "错误", "否"}


def _normalize_judgment(value: Any) -> str:
    """Normalize a judgment label/answer to a canonical truth string ("true"/"false")."""
    s = str(value).strip().lower()
    if s in _TRUE_ANSWER_SYNONYMS:
        return "true"
    if s in _FALSE_ANSWER_SYNONYMS:
        return "false"
    return s


def _judgment_is_correct(label: Any, answer: Any) -> bool:
    return _normalize_judgment(label) == _normalize_judgment(answer)


def _judgment_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate judgment (true/false) answers per item."""
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    correct = 0
    total = len(ground_truth)
    lines = ["## 判断题结果\n"]
    for i, pred in enumerate(predictions):
        item_id = pred.get("id", i)
        gt = gt_by_id.get(item_id)
        if not gt:
            lines.append(f"- Item {item_id}: 额外作答（无标准答案）")
            continue
        is_correct = _judgment_is_correct(pred.get("label", ""), gt.get("answer", ""))
        if is_correct:
            correct += 1
            lines.append(f"- Item {item_id}: ✅ 判断正确")
        else:
            lines.append(f"- Item {item_id}: ❌ 判断错误（正确答案: {gt.get('answer')}）")
    for item_id, gt in gt_by_id.items():
        if not any(p.get("id", i) == item_id for i, p in enumerate(predictions)):
            lines.append(f"- Item {item_id}: 未作答")
    accuracy = correct / total if total > 0 else 0
    lines.append(f"\n**准确率 (Accuracy)**: {accuracy:.0%} ({correct}/{total})")
    return "\n".join(lines)


def _standard_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate annotation-standard compliance (required fields / label / coord ranges)."""
    gt = ground_truth[0] if ground_truth else {}
    required = gt.get("required_fields", ["x", "y", "w", "h", "label"])
    labels = gt.get("labels", [])
    valid = 0
    total = len(predictions)
    lines = ["## 规范校验结果\n"]
    for i, pred in enumerate(predictions):
        missing = [f for f in required if f not in pred]
        bad_label = bool(labels) and pred.get("label") not in labels
        bad_coord = any(pred.get(f) is None for f in ["x", "y", "w", "h"] if f in required)
        if missing or bad_label or bad_coord:
            reasons = []
            if missing:
                reasons.append(f"缺字段 {missing}")
            if bad_label:
                reasons.append(f"标签 '{pred.get('label')}' 不在 {labels}")
            if bad_coord:
                reasons.append("坐标字段为空")
            lines.append(f"- 标注 {i + 1}: ❌ {', '.join(reasons)}")
        else:
            valid += 1
            lines.append(f"- 标注 {i + 1}: ✅ 符合规范")
    rate = valid / total if total > 0 else 0
    lines.append(f"\n**合规率**: {rate:.0%} ({valid}/{total})")
    return "\n".join(lines)


def _error_case_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate whether the student flagged the correct erroneous annotations."""
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    correct = 0
    total = len(ground_truth)
    lines = ["## 错误案例检出结果\n"]
    for i, pred in enumerate(predictions):
        item_id = pred.get("id", i)
        gt = gt_by_id.get(item_id)
        if not gt:
            continue
        flagged = bool(pred.get("flagged"))
        should_flag = bool(gt.get("is_error"))
        if flagged == should_flag:
            correct += 1
            lines.append(f"- 案例 {item_id}: ✅ 判断正确{'（标出错误）' if flagged else '（无误标）'}")
        else:
            lines.append(f"- 案例 {item_id}: ❌ 判断错误（{'应标出错误' if should_flag else '不应标出'}）")
    rate = correct / total if total > 0 else 0
    lines.append(f"\n**检出准确率**: {rate:.0%} ({correct}/{total})")
    return "\n".join(lines)


# Dict-returning versions for programmatic use (e.g. Label Studio integration)
def _bbox_dict(predictions: list[dict], ground_truth: list[dict], iou_threshold: float = 0.5) -> dict:
    metrics = _bbox_metrics(predictions, ground_truth, iou_threshold)
    tp = metrics["tp"]
    return {
        "precision": round(metrics["precision"], 4),
        "recall": round(metrics["recall"], 4),
        "f1": round(metrics["f1"], 4),
        "matched_count": tp,
        "extra_count": len(predictions) - tp,
        "missed_count": len(ground_truth) - tp,
    }


def _classify_dict(predictions: list[dict], ground_truth: list[dict]) -> dict:
    gt_by_id = {gt.get("id", i): gt for i, gt in enumerate(ground_truth)}
    correct = sum(1 for p in predictions if gt_by_id.get(p.get("id")) and p.get("label") == gt_by_id[p.get("id")].get("label"))
    total = len(ground_truth)
    return {"accuracy": round(correct / total, 4) if total else 0, "correct": correct, "total": total}


def _judgment_dict(predictions: list[dict], ground_truth: list[dict]) -> dict:
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    correct = sum(
        1
        for p in predictions
        if gt_by_id.get(p.get("id"))
        and _judgment_is_correct(p.get("label", ""), gt_by_id[p.get("id")].get("answer", ""))
    )
    total = len(ground_truth)
    return {"accuracy": round(correct / total, 4) if total else 0, "correct": correct, "total": total}


def _standard_dict(predictions: list[dict], ground_truth: list[dict]) -> dict:
    gt = ground_truth[0] if ground_truth else {}
    required = gt.get("required_fields", ["x", "y", "w", "h", "label"])
    labels = gt.get("labels", [])
    valid = 0
    for pred in predictions:
        missing = [f for f in required if f not in pred]
        bad_label = bool(labels) and pred.get("label") not in labels
        bad_coord = any(pred.get(f) is None for f in ["x", "y", "w", "h"] if f in required)
        if not (missing or bad_label or bad_coord):
            valid += 1
    total = len(predictions)
    return {"compliance_rate": round(valid / total, 4) if total else 0, "valid": valid, "total": total}


def _error_case_dict(predictions: list[dict], ground_truth: list[dict]) -> dict:
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    correct = sum(
        1
        for p in predictions
        if gt_by_id.get(p.get("id")) and bool(p.get("flagged")) == bool(gt_by_id[p.get("id")].get("is_error"))
    )
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
                "For judgment: true/false answers per item. "
                "For standard: annotation-standard compliance (required fields / label / coord ranges). "
                "For error_case: whether erroneous annotations were flagged correctly. "
                "Returns a detailed educational report with per-item feedback."
            ),
            parameters=[
                ToolParameter(
                    name="predictions",
                    type="string",
                    description=(
                        "JSON string of user's predictions. "
                        "Bbox: [{\"x\":80,\"y\":120,\"w\":140,\"h\":160,\"label\":\"cat\"},...]. "
                        "Classification: [{\"id\":1,\"label\":\"positive\"},...]. "
                        "Judgment: [{\"id\":1,\"label\":\"correct\"},...]. "
                        "Standard: [{\"x\":80,\"y\":120,\"w\":140,\"h\":160,\"label\":\"cat\"},...]. "
                        "Error_case: [{\"id\":1,\"flagged\":true},...]."
                    ),
                ),
                ToolParameter(
                    name="ground_truth",
                    type="string",
                    description=(
                        "JSON string of correct answers, same format. You prepare this from your task description. "
                        "Judgment: [{\"id\":1,\"answer\":true},...]. "
                        "Standard: [{\"required_fields\":[\"x\",\"y\",\"w\",\"h\",\"label\"],\"labels\":[\"cat\",\"dog\"]}]. "
                        "Error_case: [{\"id\":1,\"is_error\":true},...]."
                    ),
                ),
                ToolParameter(
                    name="task_type",
                    type="string",
                    description="'bbox', 'classification', 'judgment', 'standard', or 'error_case'.",
                    required=False,
                    enum=["bbox", "classification", "judgment", "standard", "error_case"],
                    default="bbox",
                ),
                ToolParameter(
                    name="image_size",
                    type="string",
                    description="Image dimensions as 'WxH' (e.g. '1000x1000'), used for edge proximity checks. Optional.",
                    required=False,
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
            chart = None
            metadata = {}
        elif task_type == "judgment":
            content = _judgment_report(predictions, ground_truth)
            chart = None
            metadata = _judgment_dict(predictions, ground_truth)
        elif task_type == "standard":
            content = _standard_report(predictions, ground_truth)
            chart = None
            metadata = _standard_dict(predictions, ground_truth)
        elif task_type == "error_case":
            content = _error_case_report(predictions, ground_truth)
            chart = None
            metadata = _error_case_dict(predictions, ground_truth)
        else:
            image_size = (1000, 1000)
            metadata = {}
            image_size_raw = kwargs.get("image_size")
            if image_size_raw:
                try:
                    img_w, img_h = str(image_size_raw).split("x")
                    image_size = (int(img_w.strip()), int(img_h.strip()))
                except (ValueError, AttributeError):
                    pass  # malformed input -> fall back to default
            content, metrics = _bbox_report(predictions, ground_truth, image_size=image_size)
            f1 = metrics.get("f1", 0.0)
            passed = f1 >= 0.7
            chart = build_scorecard_chart(
                f1=f1,
                precision=metrics.get("precision", 0.0),
                recall=metrics.get("recall", 0.0),
                passed=passed,
            )
            try:
                from deeptutor.services.path_service import get_path_service

                out_dir = get_path_service().get_task_workspace("chat", "scorecard") / "media"
                feedback = [f"IOU {m['iou']:.2f}" for m in metrics.get("matches", [])][:3]
                png = await render_scorecard_png(
                    f1=f1,
                    precision=metrics.get("precision", 0.0),
                    recall=metrics.get("recall", 0.0),
                    passed=passed,
                    feedback=feedback,
                    out_dir=out_dir,
                )
                if png is not None:
                    artifacts = collect_public_artifacts(str(out_dir))
                    if artifacts:
                        content = f"![成绩单]({artifacts[0].url})\n\n" + content
            except Exception:
                pass  # scorecard is best-effort; text feedback remains

        # 落盘保障 (回归发现: Coach 多轮对话中会漏记录): 评测后必须写学习记录
        content += (
            "\n\n---\n"
            "[必做] 请立即调用 `write_learning_record` 记录本次练习: "
            "type=annotation_exercise, 带上 f1/precision/recall/readiness/knowledge_points, "
            "并调用 `log_decision` 记录推进判定依据。然后 `write_learning_record` 中附带 "
            "foresight 预测学生下一步。"
        )

        if chart:
            metadata["chart"] = chart
        return ToolResult(content=content, metadata=metadata or None)

    def get_prompt_hints(self, language: str = "en") -> Any:
        hints = load_prompt_hints(self.name, language=language)
        if hints.short_description:
            return hints
        return super().get_prompt_hints(language=language)
