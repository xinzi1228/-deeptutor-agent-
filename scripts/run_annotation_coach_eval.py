"""Validate the annotation-coach replay suite without calling a paid model."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deeptutor.core.context import UnifiedContext  # noqa: E402
from deeptutor.services.teaching_orchestration import (  # noqa: E402
    TeachingIntent,
    build_teaching_run_policy,
)

CASES_PATH = ROOT / "tests" / "evals" / "annotation_coach_cases.json"
MOUNTED_TOOLS = [
    "ask_user",
    "route_input",
    "verify_output",
    "render_ui",
    "rag",
    "kb_search",
    "read_source",
    "read_memory",
    "graph_query",
    "competency_map",
    "delegate_to_expert",
    "read_learning_chart_data",
    "create_visualization",
    "imagegen",
    "get_annotation_task",
    "annotation_check",
    "teaching_flow",
    "struggle_detect",
    "finalize_diagnosis",
    "write_learning_record",
]


def load_suite(path: Path = CASES_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("评测文件必须包含 cases 数组")
    return payload


def validate_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "id",
        "scene",
        "input",
        "role",
        "profile_id",
        "task_snapshot",
        "allowed_sources",
        "expected_intent",
        "budget",
        "must_include",
        "must_not_include",
        "citation",
        "dataset",
        "flags",
        "human_review_hint",
    }
    missing = sorted(required - set(case))
    if missing:
        return [f"缺少字段：{', '.join(missing)}"]

    task = case["task_snapshot"]
    if not isinstance(task, dict) or not all(task.get(key) for key in ("task_id", "stage", "mode")):
        errors.append("task_snapshot 必须包含 task_id、stage 和 mode")
    if not isinstance(case["allowed_sources"], list):
        errors.append("allowed_sources 必须是数组")
    for field in ("must_include", "must_not_include", "flags"):
        if not isinstance(case[field], list):
            errors.append(f"{field} 必须是数组")

    context = UnifiedContext(
        session_id=f"eval-{case['id']}",
        user_message=str(case["input"]),
        language="zh",
        metadata={
            "learning_profile_id": str(case["profile_id"]),
            "current_task_id": str(task.get("task_id") or ""),
        },
    )
    policy = build_teaching_run_policy(context, MOUNTED_TOOLS)
    expected_intent = str(case["expected_intent"])
    if policy.intent.value != expected_intent:
        errors.append(f"意图应为 {expected_intent}，实际为 {policy.intent.value}")
    budget = case["budget"]
    expected_budget = {
        "max_tool_calls": policy.max_tool_calls,
        "max_retrieval_calls": policy.max_retrieval_calls,
        "hard_timeout_ms": policy.hard_timeout_ms,
    }
    if budget != expected_budget:
        errors.append(f"预算不一致：期望 {expected_budget}，文件为 {budget}")

    dataset = case["dataset"]
    if not isinstance(dataset, dict) or "required" not in dataset:
        errors.append("dataset 必须声明 required")
    elif dataset.get("required"):
        if policy.intent is not TeachingIntent.REPORT:
            errors.append("可信数字图案例必须归类为 report")
        if not dataset.get("hash_stable_on_rerender"):
            errors.append("可信数字图必须要求换图哈希不变")
        if "current_profile_records" not in case["allowed_sources"]:
            errors.append("可信数字图只能使用当前档案记录")

    flags = set(case["flags"])
    if "no_reliable_source" in flags and case["citation"] != "uncertainty":
        errors.append("无可靠来源案例必须要求 uncertainty")
    if "cross_profile" in flags and not any("档案" in item for item in case["must_not_include"]):
        errors.append("跨档案案例必须声明禁止泄露档案内容")
    if "teacher_readonly" in flags and not any("写入" in item for item in case["must_not_include"]):
        errors.append("教师只读案例必须声明禁止写入")
    return errors


def validate_suite(payload: dict[str, Any]) -> dict[str, Any]:
    cases = payload["cases"]
    errors: dict[str, list[str]] = {}
    seen: set[str] = set()
    for case in cases:
        case_id = str(case.get("id") or "(missing-id)") if isinstance(case, dict) else "(invalid)"
        if not isinstance(case, dict):
            errors.setdefault(case_id, []).append("案例必须是对象")
            continue
        if case_id in seen:
            errors.setdefault(case_id, []).append("案例编号重复")
        seen.add(case_id)
        case_errors = validate_case(case)
        if case_errors:
            errors.setdefault(case_id, []).extend(case_errors)
    return {
        "schema_version": payload.get("schema_version"),
        "case_count": len(cases),
        "scene_counts": dict(Counter(case.get("scene") for case in cases if isinstance(case, dict))),
        "intent_counts": dict(
            Counter(case.get("expected_intent") for case in cases if isinstance(case, dict))
        ),
        "valid": not errors,
        "errors": errors,
        "mode": "offline-contracts",
        "model_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline-contracts",
        action="store_true",
        help="Only validate deterministic contracts; never call an LLM.",
    )
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    args = parser.parse_args()
    if not args.offline_contracts:
        parser.error("当前脚本只支持 --offline-contracts，防止误触发付费模型")
    summary = validate_suite(load_suite(args.cases))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
