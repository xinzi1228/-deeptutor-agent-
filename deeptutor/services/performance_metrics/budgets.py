"""Performance budget validation for the competition readiness gates.

Encodes the budgets from release-readiness-gates design §5 as machine-checkable
rules applied to the captured performance-metric store (p50 / p95). The
validation never fabricates numbers: a metric with no captured records reports
``not_measured`` instead of passing, so an unmeasured gate cannot be claimed as
met.

Budgets (ms):
  * cold_start_interactive   ≤ 3000  (冷启动 3 秒内可操作)
  * route_visible           ≤ 1000  (页面切换 1 秒内出现核心内容)
  * progress_core_visible   ≤ 2000  (成长首屏 2 秒内完成)
  * chat_status_visible     ≤ 300   (发送后 300 毫秒内出现真实处理状态)
  * chat_first_token        ≤ 5000  (模型正常时 5 秒内首字)
"""

from __future__ import annotations

from pathlib import Path

from .store import PerformanceMetricStore

BUDGETS_MS: dict[str, int] = {
    "cold_start_interactive": 3000,
    "route_visible": 1000,
    "progress_core_visible": 2000,
    "chat_status_visible": 300,
    "chat_first_token": 5000,
}

SUCCESS_BUDGETS_MS: dict[str, int] = BUDGETS_MS


def check_budgets(profile_root: Path) -> dict[str, object]:
    """Validate captured p50/p95 against the design budgets.

    Returns per-metric status: ``pass`` / ``over_budget`` / ``not_measured``.
    ``not_measured`` is *not* a pass — it means the gate was not exercised.
    """
    summary = PerformanceMetricStore(profile_root).summary()
    metrics = summary.get("metrics", {})
    results: dict[str, object] = {}
    for name, budget_ms in BUDGETS_MS.items():
        entry = metrics.get(name)
        if not entry or entry.get("count", 0) == 0:
            results[name] = {
                "status": "not_measured",
                "budget_ms": budget_ms,
                "detail": "未采集到该指标，不能判定达标",
            }
            continue
        p50 = float(entry["p50_ms"])
        p95 = float(entry["p95_ms"])
        ok = p50 <= budget_ms and p95 <= budget_ms
        results[name] = {
            "status": "pass" if ok else "over_budget",
            "budget_ms": budget_ms,
            "p50_ms": p50,
            "p95_ms": p95,
            "count": int(entry.get("count", 0)),
            "detail": "" if ok else f"p95 {p95:.0f}ms 超过预算 {budget_ms}ms",
        }
    all_measured = all(
        results[name]["status"] in {"pass", "over_budget"} for name in BUDGETS_MS
    )
    all_pass = all(results[name]["status"] == "pass" for name in BUDGETS_MS)
    return {
        "schema_version": 1,
        "all_measured": all_measured,
        "budgets_met": all_pass,
        "metrics": results,
        "note": "未采集指标视为 not_measured，不视为达标",
    }


__all__ = ["BUDGETS_MS", "check_budgets"]
