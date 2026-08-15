from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult
from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.visualization_artifacts import freeze_dataset_snapshot


def _numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _label(row: dict[str, Any], index: int) -> str:
    task_id = str(row.get("task_id") or "").strip()
    return task_id or f"第 {index} 次"


class ReadLearningChartDataTool(BaseTool):
    """Create an immutable, profile-private snapshot for truthful charts."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_learning_chart_data",
            description=(
                "Read real numeric data from the active learning profile and return a signed dataset_ref. "
                "Call this before create_visualization for every numeric chart. Never invent labels or values."
            ),
            parameters=[
                ToolParameter(
                    name="dataset",
                    type="string",
                    description="Which trusted profile dataset to read.",
                    enum=["annotation_attempt_metrics", "learning_f1_trend"],
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Most recent rows, 1-30. Default 12.",
                    required=False,
                    default=12,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        from deeptutor.multi_user.paths import get_current_learning_profile_root

        profile_root = get_current_learning_profile_root(require_unlocked=True)
        if profile_root is None:
            return ToolResult(content="请先解锁学习档案。", success=False)
        dataset = str(kwargs.get("dataset") or "").strip()
        try:
            limit = max(1, min(int(kwargs.get("limit") or 12), 30))
        except (TypeError, ValueError):
            limit = 12

        if dataset == "annotation_attempt_metrics":
            rows = AnnotationAttemptStore(profile_root).list_attempts(limit=limit)
            source = "当前学习档案的已提交标注记录"
        elif dataset == "learning_f1_trend":
            rows = _read_jsonl(Path(profile_root) / "learning" / "records.jsonl")[-limit:]
            source = "当前学习档案的学习记录"
        else:
            return ToolResult(content="不支持的数据集。", success=False)

        normalized: list[tuple[str, dict[str, float | None], str]] = []
        for row in rows:
            metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else row
            values = {
                "F1": _numeric(metrics.get("f1")),
                "精确率": _numeric(metrics.get("precision")),
                "召回率": _numeric(metrics.get("recall")),
            }
            if all(value is None for value in values.values()):
                continue
            normalized.append(
                (
                    _label(row, len(normalized) + 1),
                    values,
                    str(row.get("created_at") or row.get("timestamp") or ""),
                )
            )
        if not normalized:
            return ToolResult(
                content="当前档案还没有可用于图表的真实数值；请改用文字说明或流程图。",
                success=False,
            )

        # A missing metric is omitted as a whole series.  It is never replaced
        # with zero because that would silently turn “unknown” into fake data.
        labels = [row[0] for row in normalized]
        datasets = []
        for name in ("F1", "精确率", "召回率"):
            values = [row[1][name] for row in normalized]
            if all(value is not None for value in values):
                datasets.append({"label": name, "data": values})
        if not datasets:
            return ToolResult(
                content="现有记录的数值字段不连续，无法生成不补零的可信趋势图。",
                success=False,
            )

        content = {
            "chart_type": "line",
            "labels": labels,
            "datasets": datasets,
        }
        snapshot = freeze_dataset_snapshot(
            profile_root,
            dataset_id=f"learning_metrics:{dataset}",
            version=1,
            query={"limit": limit},
            source=source,
            unit="比例（0-1）",
            source_updated_at=next(
                (stamp for stamp in reversed([row[2] for row in normalized]) if stamp),
                datetime.now(timezone.utc).isoformat(),
            ),
            content=content,
        )
        return ToolResult(
            content=json.dumps(snapshot, ensure_ascii=False),
            metadata={"dataset": snapshot},
        )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


__all__ = ["ReadLearningChartDataTool"]
