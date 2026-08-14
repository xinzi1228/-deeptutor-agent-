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


# ------------------------------------------------------- audio/video temporal metrics

def _calculate_tiou(seg1: dict, seg2: dict) -> float:
    s1, e1 = seg1["start_time"], seg1["end_time"]
    s2, e2 = seg2["start_time"], seg2["end_time"]
    inter = max(0.0, min(e1, e2) - max(s1, s2))
    union = max(e1, e2) - min(s1, s2)
    return inter / union if union > 0 else 0.0


def _calculate_wer(reference: str, hypothesis: str) -> dict:
    ref_words = reference.strip().split()
    hyp_words = hypothesis.strip().split()
    m, n = len(ref_words), len(hyp_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if ref_words[i - 1] == hyp_words[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    edits = dp[m][n]
    wer = edits / m if m > 0 else float("inf")
    return {"wer": wer, "edits": edits, "ref_words": m, "hyp_words": n}


def _segment_f1_metrics(predictions: list[dict], ground_truth: list[dict], iou_threshold: float = 0.5) -> dict:
    pairs = []
    for pi, pred in enumerate(predictions):
        for gj, gt in enumerate(ground_truth):
            if pred.get("label", "") != gt.get("label", ""):
                continue
            tiou = _calculate_tiou(pred, gt)
            if tiou >= iou_threshold:
                pairs.append((tiou, pi, gj))
    pairs.sort(key=lambda x: x[0], reverse=True)
    matched_pred: set[int] = set()
    matched_gt: set[int] = set()
    matches: list[dict] = []
    for tiou, pi, gj in pairs:
        if pi not in matched_pred and gj not in matched_gt:
            matches.append({"pred_idx": pi, "gt_idx": gj, "tiou": tiou})
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


# -------------------------------------------------------- auto readiness gate

READINESS_ADVANCE = "advance"
READINESS_ADVANCE_WITH_CAUTION = "advance_with_caution"
READINESS_MORE_PRACTICE = "more_practice"
READINESS_REVIEW_FIRST = "review_first"


def auto_readiness(f1: float | None) -> str:
    """Map an F1 score to a readiness_gate decision (deterministic, conservative on missing).

    Emits 4 of the 6 readiness_gate 判定 (decision-matrix §3): advance /
    advance_with_caution / more_practice / review_first. The other two —
    step_down and diagnose_again — are NOT produced here: they are coach /
    struggle-detection decisions made from deeper signals (prerequisite gaps,
    repeated failed interventions), not from a single F1 score. Coach may
    override this default via the teaching_flow advance readiness parameter.
    """
    try:
        f = float(f1)
    except (TypeError, ValueError):
        return READINESS_REVIEW_FIRST
    if f >= 0.85:
        return READINESS_ADVANCE
    if f >= 0.7:
        return READINESS_ADVANCE_WITH_CAUTION
    if f >= 0.65:
        return READINESS_MORE_PRACTICE
    return READINESS_REVIEW_FIRST


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
_FALSE_ANSWER_SYNONYMS = {"false", "wrong", "incorrect", "no", "0", "错", "错误", "否"}


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


def _resolve_id(pred: dict, idx: int) -> int:
    return pred.get("id", idx)


def _judgment_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate judgment (true/false) answers per item."""
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    correct = 0
    total = len(ground_truth)
    lines = ["## 判断题结果\n"]
    for i, pred in enumerate(predictions):
        item_id = _resolve_id(pred, i)
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
        if not any(_resolve_id(p, i) == item_id for i, p in enumerate(predictions)):
            lines.append(f"- Item {item_id}: 未作答")
    accuracy = correct / total if total > 0 else 0
    lines.append(f"\n**准确率 (Accuracy)**: {accuracy:.0%} ({correct}/{total})")
    return "\n".join(lines)


def _standard_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    """Evaluate annotation-standard compliance (required fields / label / coord ranges)."""
    gt = ground_truth[0] if ground_truth else {}
    required = gt.get("required_fields", ["x", "y", "w", "h", "label"])
    labels = gt.get("labels", [])
    if not predictions:
        return (
            "## 规范校验结果\n"
            f"无提交。需要 {len(ground_truth)} 条标注，请按 `{required}` 字段提交。"
        )
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
    """Evaluate whether the student flagged the correct erroneous annotations.

    Unlisted ground-truth cases are implicitly treated as not flagged — a student
    who lists only the error ids (the natural answer) gets full credit for the
    non-error cases they correctly left unflagged.
    """
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    flagged_by_id = {_resolve_id(p, i): bool(p.get("flagged")) for i, p in enumerate(predictions)}
    correct = 0
    total = len(ground_truth)
    lines = ["## 错误案例检出结果\n"]
    for item_id, gt in gt_by_id.items():
        flagged = flagged_by_id.get(item_id, False)
        should_flag = bool(gt.get("is_error"))
        if flagged == should_flag:
            correct += 1
            if item_id in flagged_by_id:
                lines.append(f"- 案例 {item_id}: ✅ 判断正确{'（标出错误）' if flagged else '（无误标）'}")
            else:
                lines.append(f"- 案例 {item_id}: ✅ 判断正确（未标出，视为无误）")
        else:
            if item_id in flagged_by_id:
                lines.append(f"- 案例 {item_id}: ❌ 判断错误（{'应标出错误' if should_flag else '不应标出'}）")
            else:
                lines.append(f"- 案例 {item_id}: ❌ 漏标（应为错误）")
    for i, pred in enumerate(predictions):
        item_id = _resolve_id(pred, i)
        if item_id not in gt_by_id:
            lines.append(f"- 案例 {item_id}: 额外作答（无标准案例）")
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
        for i, p in enumerate(predictions)
        if gt_by_id.get(_resolve_id(p, i))
        and _judgment_is_correct(p.get("label", ""), gt_by_id[_resolve_id(p, i)].get("answer", ""))
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
    """Score error-case answers: unlisted GT cases are implicitly "not flagged" (correct when not an error)."""
    gt_by_id = {g.get("id", i): g for i, g in enumerate(ground_truth)}
    flagged_by_id = {_resolve_id(p, i): bool(p.get("flagged")) for i, p in enumerate(predictions)}
    correct = sum(
        1
        for item_id, gt in gt_by_id.items()
        if flagged_by_id.get(item_id, False) == bool(gt.get("is_error"))
    )
    total = len(ground_truth)
    return {"accuracy": round(correct / total, 4) if total else 0, "correct": correct, "total": total}


# -------------------------------------------------------- audio event evaluation

def _audio_event_report(predictions: list[dict], ground_truth: list[dict], tiou_threshold: float = 0.5) -> str:
    metrics = _segment_f1_metrics(predictions, ground_truth, tiou_threshold)
    tp = metrics["tp"]; fp = metrics["fp"]; fn = metrics["fn"]
    precision = metrics["precision"]; recall = metrics["recall"]; f1 = metrics["f1"]
    matches = metrics["matches"]; matched_pred = metrics["matched_pred"]; matched_gt = metrics["matched_gt"]

    lines = ["## 音频事件检测结果\n"]
    lines.append(f"**精确率**: {precision:.0%}  — 标出的事件中有多少是正确的？")
    lines.append(f"**召回率**: {recall:.0%}  — 实际事件中找到了多少？")
    lines.append(f"**F1 分数**: {f1:.0%}  — 综合评分")
    lines.append(f"**汇总**: {tp} 正确 | {fp} 误报 | {fn} 漏检\n")

    if matches:
        lines.append("### 正确匹配")
        for m in matches:
            pred = predictions[m["pred_idx"]]
            lines.append(f"- [{pred['start_time']}s–{pred['end_time']}s] '{pred.get('label','?')}' — tIoU={m['tiou']:.2f} ✓")

    for pi, pred in enumerate(predictions):
        if pi in matched_pred:
            continue
        lines.append(f"- [{pred['start_time']}s–{pred['end_time']}s] '{pred.get('label','?')}': 误报（无对应事件）")

    for gj in range(len(ground_truth)):
        if gj not in matched_gt:
            gt = ground_truth[gj]
            lines.append(f"- 漏检: '{gt.get('label','?')}' 在 [{gt['start_time']}s–{gt['end_time']}s] 未被标出")

    lines.append("\n---")
    if f1 >= 0.8:
        lines.append("**很不错！** 事件检测准确率高。")
    elif recall < precision:
        lines.append("**提示**: 召回率偏低，可能漏了一些事件。试着降低标注门槛。")
    else:
        lines.append("**提示**: 精确率偏低，有较多误报。标注时请更谨慎。")

    return "\n".join(lines)


def _audio_event_dict(predictions: list[dict], ground_truth: list[dict], tiou_threshold: float = 0.5) -> dict:
    metrics = _segment_f1_metrics(predictions, ground_truth, tiou_threshold)
    return {
        "precision": round(metrics["precision"], 4),
        "recall": round(metrics["recall"], 4),
        "f1": round(metrics["f1"], 4),
        "matched_count": metrics["tp"],
        "extra_count": len(predictions) - metrics["tp"],
        "missed_count": len(ground_truth) - metrics["tp"],
    }


# -------------------------------------------------------- audio transcription evaluation

def _audio_transcription_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    lines = ["## 语音转录评估结果\n"]
    if not predictions:
        return "\n".join(lines) + "无提交。"
    gt_by_id = {gt.get("id", i): gt for i, gt in enumerate(ground_truth)}
    total_wer = 0.0
    count = 0
    for i, pred in enumerate(predictions):
        item_id = pred.get("id", i)
        gt = gt_by_id.get(item_id)
        if not gt:
            lines.append(f"- 段落 {item_id}: 额外作答（无标准答案）")
            continue
        ref = gt.get("text", "")
        hyp = pred.get("text", "")
        result = _calculate_wer(ref, hyp)
        wer = result["wer"]
        total_wer += wer
        count += 1
        lines.append(f"- 段落 {item_id}: WER={wer:.1%} (编辑距离={result['edits']}, 参考词数={result['ref_words']})")
        if wer < 0.1:
            lines.append(f"  转录质量优秀 ✓")
        elif wer < 0.3:
            lines.append(f"  转录质量一般，注意听清每个词")
        else:
            lines.append(f"  错误较多，建议重新仔细听")

    for item_id, gt in gt_by_id.items():
        if not any(p.get("id", i) == item_id for i, p in enumerate(predictions)):
            lines.append(f"- 段落 {item_id}: 未作答")

    avg_wer = total_wer / count if count > 0 else 1.0
    accuracy = max(0.0, 1.0 - avg_wer)
    lines.append(f"\n**平均 WER**: {avg_wer:.1%} | **转录准确率**: {accuracy:.0%}")
    lines.append("\n---")
    if avg_wer < 0.1:
        lines.append("**优秀！** 转录质量很高。")
    elif avg_wer < 0.3:
        lines.append("**不错。** 继续练习提高准确率。")
    else:
        lines.append("**需要改进。** 仔细听音频，逐词对照检查。")
    return "\n".join(lines)


def _audio_transcription_dict(predictions: list[dict], ground_truth: list[dict]) -> dict:
    gt_by_id = {gt.get("id", i): gt for i, gt in enumerate(ground_truth)}
    total_wer = 0.0; count = 0
    for i, pred in enumerate(predictions):
        item_id = pred.get("id", i)
        gt = gt_by_id.get(item_id)
        if gt:
            result = _calculate_wer(gt.get("text", ""), pred.get("text", ""))
            total_wer += result["wer"]
            count += 1
    avg_wer = total_wer / count if count > 0 else 1.0
    return {"wer": round(avg_wer, 4), "accuracy": round(max(0.0, 1.0 - avg_wer), 4), "segments": count}


# -------------------------------------------------------- video tracking evaluation

def _video_tracking_report(predictions: list[dict], ground_truth: list[dict], iou_threshold: float = 0.5) -> str:
    total_frames = len(ground_truth)
    if total_frames == 0:
        return "无标准答案数据。"

    frames_correct = 0
    total_precision = 0.0
    total_recall = 0.0
    detail_lines: list[str] = []

    for frame_idx, gt_frame in enumerate(ground_truth):
        gt_boxes = gt_frame.get("boxes", [])
        frame_id = gt_frame.get("frame", frame_idx)
        pred_frame = predictions[frame_idx] if frame_idx < len(predictions) else {}
        pred_boxes = pred_frame.get("boxes", [])

        if not gt_boxes:
            continue

        frame_metrics = _bbox_metrics(pred_boxes, gt_boxes, iou_threshold)
        total_precision += frame_metrics["precision"]
        total_recall += frame_metrics["recall"]
        f1 = frame_metrics["f1"]
        if f1 >= 0.5:
            frames_correct += 1

        detail_lines.append(
            f"- 帧 {frame_id}: P={frame_metrics['precision']:.0%} R={frame_metrics['recall']:.0%} "
            f"F1={f1:.0%} ({frame_metrics['tp']}/{len(gt_boxes)} 匹配)"
        )

    avg_precision = total_precision / total_frames if total_frames > 0 else 0
    avg_recall = total_recall / total_frames if total_frames > 0 else 0
    avg_f1 = 2 * avg_precision * avg_recall / (avg_precision + avg_recall) if (avg_precision + avg_recall) > 0 else 0
    frame_accuracy = frames_correct / total_frames if total_frames > 0 else 0

    lines = ["## 视频跟踪评估结果\n"]
    lines.append(f"**平均精确率**: {avg_precision:.0%}")
    lines.append(f"**平均召回率**: {avg_recall:.0%}")
    lines.append(f"**平均 F1**: {avg_f1:.0%}")
    lines.append(f"**帧正确率**: {frame_accuracy:.0%} ({frames_correct}/{total_frames} 帧达标)\n")
    lines.append("### 逐帧详情")
    lines.extend(detail_lines[:10])
    if len(detail_lines) > 10:
        lines.append(f"... 共 {len(detail_lines)} 帧，仅展示前 10 帧")

    lines.append("\n---")
    if avg_f1 >= 0.8:
        lines.append("**优秀！** 跟踪标注质量很高。")
    elif avg_f1 >= 0.5:
        lines.append("**继续加油。** 注意框的边缘贴合度和逐帧一致性。")
    else:
        lines.append("**需要改进。** 逐帧检查框是否完整覆盖目标。")
    return "\n".join(lines)


def _video_tracking_dict(predictions: list[dict], ground_truth: list[dict], iou_threshold: float = 0.5) -> dict:
    total_frames = len(ground_truth)
    if total_frames == 0:
        return {"f1": 0, "frame_accuracy": 0, "total_frames": 0}
    total_precision = 0.0; total_recall = 0.0; frames_correct = 0
    for frame_idx, gt_frame in enumerate(ground_truth):
        gt_boxes = gt_frame.get("boxes", [])
        pred_frame = predictions[frame_idx] if frame_idx < len(predictions) else {}
        pred_boxes = pred_frame.get("boxes", [])
        if not gt_boxes:
            continue
        fm = _bbox_metrics(pred_boxes, gt_boxes, iou_threshold)
        total_precision += fm["precision"]
        total_recall += fm["recall"]
        if fm["f1"] >= 0.5:
            frames_correct += 1
    avg_p = total_precision / total_frames if total_frames > 0 else 0
    avg_r = total_recall / total_frames if total_frames > 0 else 0
    avg_f1 = 2 * avg_p * avg_r / (avg_p + avg_r) if (avg_p + avg_r) > 0 else 0
    return {"f1": round(avg_f1, 4), "frame_accuracy": round(frames_correct / total_frames, 4) if total_frames > 0 else 0, "total_frames": total_frames}


# -------------------------------------------------------- video event evaluation

def _video_event_report(predictions: list[dict], ground_truth: list[dict], tiou_threshold: float = 0.5) -> str:
    return _audio_event_report(predictions, ground_truth, tiou_threshold).replace("音频事件检测", "视频事件检测")


def _video_event_dict(predictions: list[dict], ground_truth: list[dict], tiou_threshold: float = 0.5) -> dict:
    return _audio_event_dict(predictions, ground_truth, tiou_threshold)


# -------------------------------------------------------- NER evaluation (text annotation)

def _ner_metrics(predictions: list[dict], ground_truth: list[dict]) -> dict:
    """Entity-level exact match F1 for NER."""
    pred_set = set()
    gt_set = set()
    for p in predictions:
        pred_set.add((p.get("start", 0), p.get("end", 0), p.get("label", "")))
    for g in ground_truth:
        gt_set.add((g.get("start", 0), g.get("end", 0), g.get("label", "")))
    tp = len(pred_set & gt_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    precision = tp / len(pred_set) if pred_set else 0
    recall = tp / len(gt_set) if gt_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def _ner_report(predictions: list[dict], ground_truth: list[dict]) -> str:
    metrics = _ner_metrics(predictions, ground_truth)
    tp = metrics["tp"]; fp = metrics["fp"]; fn = metrics["fn"]
    precision = metrics["precision"]; recall = metrics["recall"]; f1 = metrics["f1"]

    lines = ["## 命名实体识别(NER)评估结果\n"]
    lines.append(f"**精确率**: {precision:.0%}  — 标出的实体中有多少是正确的？")
    lines.append(f"**召回率**: {recall:.0%}  — 实际实体中找到了多少？")
    lines.append(f"**F1 分数**: {f1:.0%}  — 综合评分")
    lines.append(f"**汇总**: {tp} 正确 | {fp} 误标/错标 | {fn} 漏标\n")

    pred_set = set((p.get("start", 0), p.get("end", 0), p.get("label", "")) for p in predictions)
    gt_set = set((g.get("start", 0), g.get("end", 0), g.get("label", "")) for g in ground_truth)

    if pred_set & gt_set:
        lines.append("### 正确匹配的实体")
        for s, e, label in sorted(pred_set & gt_set):
            lines.append(f"- [{s}:{e}] `{label}` ✓")

    for s, e, label in sorted(pred_set - gt_set):
        lines.append(f"- [{s}:{e}] `{label}`: ❌ 误标（不存在此实体）")

    for s, e, label in sorted(gt_set - pred_set):
        lines.append(f"- [{s}:{e}] `{label}`: ⚠ 漏标（未标注此实体）")

    lines.append("\n---")
    if f1 >= 0.8:
        lines.append("**优秀！** 实体识别准确率高。")
    elif f1 >= 0.6:
        lines.append("**不错。** 检查漏标或误标的实体。")
    else:
        lines.append("**需要改进。** 仔细对比每个实体的起止位置和标签。")
    return "\n".join(lines)


def _ner_dict(predictions: list[dict], ground_truth: list[dict]) -> dict:
    metrics = _ner_metrics(predictions, ground_truth)
    return {
        "precision": round(metrics["precision"], 4),
        "recall": round(metrics["recall"], 4),
        "f1": round(metrics["f1"], 4),
        "matched": metrics["tp"],
        "extra": metrics["fp"],
        "missed": metrics["fn"],
    }


class AnnotationCheckTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="annotation_check",
            description=(
                "Evaluate annotation quality by comparing predictions against ground truth. "
                "For bounding boxes (bbox): computes IOU, precision, recall, F1. "
                "For classification: computes per-item accuracy. "
                "For judgment: true/false answers per item. "
                "For standard: annotation-standard compliance (required fields / label / coord ranges). "
                "For error_case: whether erroneous annotations were flagged correctly. "
                "For audio_event: computes tIoU (temporal IOU), precision, recall, F1 on audio segments. "
                "For audio_transcription: computes WER (Word Error Rate) for speech-to-text. "
                "For video_tracking: computes frame-level IOU across video frames. "
                "For video_event: computes tIoU on video temporal segments. "
                "For ner: computes entity-level exact-match F1 for text NER annotation. "
                "Returns a detailed educational report with per-item feedback. "
                "评测 bbox 后若提供 task_id 会自动推进教学流程 evaluate→feedback。"
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
                    description="'bbox', 'classification', 'judgment', 'standard', 'error_case', 'audio_event', 'audio_transcription', 'video_tracking', 'video_event', 'ner'.",
                    required=False,
                    enum=["bbox", "classification", "judgment", "standard", "error_case", "audio_event", "audio_transcription", "video_tracking", "video_event", "ner"],
                    default="bbox",
                ),
                ToolParameter(
                    name="image_size",
                    type="string",
                    description="Image dimensions as 'WxH' (e.g. '1000x1000'), used for edge proximity checks. Optional.",
                    required=False,
                ),
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="(可选) 当前评测的标注任务 id。评测 bbox 后若提供会自动推进教学流程 evaluate→feedback。",
                    required=False,
                ),
                ToolParameter(
                    name="pre_annotation",
                    type="string",
                    description=(
                        "(可选) AI 预标注的 JSON string（格式同 predictions，仅 bbox 生效）。"
                        "提供时用同一 ground_truth 额外评 AI 预标注，返回 pre_annotation_metrics "
                        "（同 predictions metrics 结构）+ improvement（学生 F1 - AI 预标注 F1）。"
                        "用于『AI 辅助标注审阅教学』双评对比。"
                    ),
                    required=False,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        task_type = kwargs.get("task_type", "bbox")
        task_id = kwargs.get("task_id")
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

        pre_annotation = None
        pre_raw = kwargs.get("pre_annotation")
        if pre_raw:
            try:
                pre_annotation = json.loads(pre_raw) if isinstance(pre_raw, str) else pre_raw
            except json.JSONDecodeError:
                pre_annotation = None  # malformed pre-annotation -> ignore, keep normal grading

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
        elif task_type == "audio_event":
            content = _audio_event_report(predictions, ground_truth)
            chart = None
            metadata = _audio_event_dict(predictions, ground_truth)
        elif task_type == "audio_transcription":
            content = _audio_transcription_report(predictions, ground_truth)
            chart = None
            metadata = _audio_transcription_dict(predictions, ground_truth)
        elif task_type == "video_tracking":
            content = _video_tracking_report(predictions, ground_truth)
            chart = None
            metadata = _video_tracking_dict(predictions, ground_truth)
        elif task_type == "video_event":
            content = _video_event_report(predictions, ground_truth)
            chart = None
            metadata = _video_event_dict(predictions, ground_truth)
        elif task_type == "ner":
            content = _ner_report(predictions, ground_truth)
            chart = None
            metadata = _ner_dict(predictions, ground_truth)
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
            from deeptutor.services.annotation_scoring import BboxScorer

            score = BboxScorer().score(
                predictions,
                ground_truth,
                reference_version=str(kwargs.get("reference_version") or "tool:provided-ground-truth"),
                image_size=image_size,
            )
            content = score.report
            metrics = score.metrics
            f1 = metrics.get("f1", 0.0)
            readiness = auto_readiness(f1)
            metadata.update(metrics)
            metadata.update({
                "readiness": readiness,
                "rule_version": score.rule_version,
                "reference_version": score.reference_version,
                "score_hash": score.score_hash,
            })
            passed = f1 >= 0.7
            if pre_annotation:
                # 畸形 pre_annotation (合法 JSON 但缺 x/y/w/h 字段) 会令 _bbox_dict
                # 抛 KeyError -> 忽略双评, 不阻塞主评分 (畸形不致命)
                try:
                    pre_metrics = _bbox_dict(pre_annotation, ground_truth)
                except Exception:
                    pre_metrics = None
                if pre_metrics is not None:
                    improvement = round(f1 - pre_metrics["f1"], 4)
                    metadata["pre_annotation_metrics"] = pre_metrics
                    metadata["improvement"] = improvement
                    content += (
                        "\n\n### AI 预标注对比 (双评)\n"
                        f"**AI 预标注 F1**: {pre_metrics['f1']:.0%} "
                        f"(precision={pre_metrics['precision']:.0%}, recall={pre_metrics['recall']:.0%}, "
                        f"正确 {pre_metrics['matched_count']} | 多余 {pre_metrics['extra_count']} | 漏标 {pre_metrics['missed_count']})\n"
                        f"**你的 F1**: {f1:.0%}\n"
                        f"**改进 (你的 F1 - AI F1)**: {improvement:+.0%}"
                    )
            if task_id:
                try:
                    from deeptutor.services.teaching_flow import TeachingFlowEngine

                    TeachingFlowEngine().on_evaluated(task_id, f1=f1, readiness=readiness)
                except Exception:
                    pass  # auto-advance is best-effort; never block grading
            content += f"\n\n**自动 readiness 判定**: {readiness}"
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
