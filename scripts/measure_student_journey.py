"""Print a privacy-safe performance + budget summary for one profile root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Ensure the repository root is importable when launched as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_REPO_ROOT))

from deeptutor.services.performance_metrics import (  # noqa: E402
    BUDGETS_MS,
    PerformanceMetricStore,
    check_budgets,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile-root",
        required=True,
        type=Path,
        help="已解锁学习档案的私有根目录",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = args.profile_root.resolve()
    summary = PerformanceMetricStore(root).summary()
    budgets = check_budgets(root)

    if args.json:
        print(json.dumps({"metrics": summary, "budgets": budgets}, ensure_ascii=False, indent=2))
        return 0

    print(f"性能记录总数：{summary['total']}")
    for name, metric in summary["metrics"].items():
        print(
            f"- {name}: count={metric['count']} "
            f"p50={metric['p50_ms']}ms p95={metric['p95_ms']}ms "
            f"errors={metric['error_count']} timeouts={metric['timeout_count']}"
        )

    print("\n性能预算验收：")
    for name, budget_ms in BUDGETS_MS.items():
        result = budgets["metrics"][name]
        status = result["status"]
        mark = {"pass": "PASS", "over_budget": "FAIL", "not_measured": "SKIP"}.get(status, status)
        print(f"[{mark}] {name} 预算 {budget_ms}ms：{result.get('detail') or result.get('p50_ms', '—')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
