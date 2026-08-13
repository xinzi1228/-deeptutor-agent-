from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

VisualizationKind = Literal["chart", "diagram", "generated_image"]
_CHART_TYPES = {"line", "bar", "pie", "doughnut", "radar", "scatter"}


@dataclass(slots=True)
class VisualizationArtifact:
    id: str
    kind: VisualizationKind
    title: str
    description: str
    alt_text: str
    render_protocol: str
    content: dict[str, Any]
    source: str
    unit: str
    source_updated_at: str
    validation_status: str
    validation_message: str
    created_at: str
    session_id: str = ""
    model: str = ""
    save_state: str = "session"
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_visualization_request(payload: dict[str, Any], *, session_id: str = "") -> VisualizationArtifact:
    kind = str(payload.get("kind") or "").strip()
    title = str(payload.get("title") or "").strip()
    description = str(payload.get("description") or "").strip()
    alt_text = str(payload.get("alt_text") or description or title).strip()
    source = str(payload.get("source") or "").strip()
    unit = str(payload.get("unit") or "").strip()
    content = payload.get("content")
    if kind not in {"chart", "diagram", "generated_image"}:
        raise ValueError("kind 必须是 chart、diagram 或 generated_image")
    if not title or len(title) > 120:
        raise ValueError("标题需要 1 到 120 个字符")
    if not isinstance(content, dict):
        raise ValueError("content 必须是对象")
    protocol = ""
    message = "结构、来源与字段已通过确定性校验"
    if kind == "chart":
        chart_type = str(content.get("chart_type") or "").strip()
        labels = content.get("labels")
        datasets = content.get("datasets")
        if chart_type not in _CHART_TYPES:
            raise ValueError(f"不支持的图表类型：{chart_type}")
        if not source:
            raise ValueError("数字图表必须提供真实数据来源，不能编造数字")
        if not unit:
            raise ValueError("数字图表必须说明单位")
        if not isinstance(labels, list) or not labels or len(labels) > 100:
            raise ValueError("labels 需要是 1 到 100 项的数组")
        if not isinstance(datasets, list) or not datasets or len(datasets) > 12:
            raise ValueError("datasets 需要是 1 到 12 项的数组")
        for dataset in datasets:
            values = dataset.get("data") if isinstance(dataset, dict) else None
            if not isinstance(values, list) or len(values) != len(labels):
                raise ValueError("每组数据长度必须与 labels 一致")
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
                raise ValueError("数字图表的数据只能包含真实数值")
        protocol = "chartjs"
    elif kind == "diagram":
        mermaid = str(content.get("mermaid") or "").strip()
        if not mermaid or len(mermaid) > 30_000:
            raise ValueError("图解必须提供合法长度的 Mermaid 源码")
        if any(token in mermaid.lower() for token in ("<script", "javascript:", "click ")):
            raise ValueError("Mermaid 图解包含不安全内容")
        protocol = "mermaid"
        message = "图解语法与安全边界已校验；关系准确性由给定来源负责"
    else:
        prompt = str(content.get("prompt") or "").strip()
        image_url = str(content.get("image_url") or "").strip()
        if not prompt or not image_url:
            raise ValueError("生图作品必须保存提示词和生成结果地址")
        protocol = "image"
        message = "这是概念示意图，不作为精确事实或数字证据"
    return VisualizationArtifact(
        id=f"viz_{uuid.uuid4().hex}", kind=kind, title=title, description=description,
        alt_text=alt_text, render_protocol=protocol, content=content, source=source,
        unit=unit, source_updated_at=str(payload.get("source_updated_at") or ""),
        validation_status="validated", validation_message=message,
        created_at=datetime.now(timezone.utc).isoformat(), session_id=session_id,
        model=str(payload.get("model") or ""),
    )
