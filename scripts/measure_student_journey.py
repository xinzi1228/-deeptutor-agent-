"""Print a privacy-safe performance summary for one learning-profile root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from deeptutor.services.performance_metrics import PerformanceMetricStore


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

    summary = PerformanceMetricStore(args.profile_root.resolve()).summary()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"性能记录总数：{summary['total']}")
    for name, metric in summary["metrics"].items():
        print(
            f"- {name}: count={metric['count']} "
            f"p50={metric['p50_ms']}ms p95={metric['p95_ms']}ms "
            f"errors={metric['error_count']} timeouts={metric['timeout_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
