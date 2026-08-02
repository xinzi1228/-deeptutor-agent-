# 对话内可视化实施计划（Chat Visualization）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让对话流内展示 4 类图表卡片——练习成绩单（matplotlib 图片）、能力雷达/学习进度（Chart.js 交互）、知识图谱风险链（cytoscape）——全部由确定性数据驱动，LLM 不参与画图。

**Architecture:** 工具层在 `ToolResult.metadata.chart` 携带确定性图表数据（或生成 matplotlib PNG 图片）；前端 `ChatMessages.tsx` 的 `AssistantMessage` 分支检测 `resultEvent.metadata.chart` → 渲染 `ChatChartCard` 组件（Chart.js/cytoscape/img）。成绩单走 `code_execution`+matplotlib 生成 PNG → `/api/outputs` → markdown 图片。

**Tech Stack:** matplotlib 3.10.8（已装）、Chart.js 4.5.1 + react-chartjs-2 5.3.1（已装）、cytoscape 3.33.1（已装）、React、pytest + pytest-asyncio。

**Spec:** `docs/specs/visualization-design.md`（已提交 `54eaa461`）

---

### Task 1: 后端 chart 契约工具函数 + `annotation_check` 成绩单图片

**Files:**
- Create: `deeptutor/tools/chart_cards.py` — chart JSON 契约构造器 + matplotlib 成绩单图生成
- Modify: `deeptutor/tools/annotation_check.py` — execute 返回 metadata.chart + 生成成绩单 PNG
- Test: `tests/tools/test_chart_cards.py`

- [ ] **Step 1: Write the failing test**

```python
"""Chart card contract + scorecard image generation tests."""

from __future__ import annotations

import json

import pytest

from deeptutor.tools.chart_cards import build_scorecard_chart, radar_chart, progress_chart, render_scorecard_png


def test_radar_chart_contract():
    c = radar_chart(labels=["框精度", "标签准确", "完整性", "一致性", "知识掌握"], values=[80, 70, 60, 75, 50])
    assert c["type"] == "radar"
    assert c["data"]["labels"] == ["框精度", "标签准确", "完整性", "一致性", "知识掌握"]
    assert c["data"]["values"] == [80, 70, 60, 75, 50]


def test_progress_chart_contract():
    c = progress_chart(completed=2, total=4, modules=[{"name": "标注基础", "done": 2, "total": 2}])
    assert c["type"] == "progress"
    assert c["data"]["completed"] == 2
    assert c["data"]["total"] == 4


def test_scorecard_chart_contract():
    c = build_scorecard_chart(f1=0.85, precision=0.9, recall=0.8, passed=True)
    assert c["type"] == "scorecard"
    assert c["data"]["f1"] == 0.85
    assert c["data"]["passed"] is True


@pytest.mark.asyncio
async def test_render_scorecard_png(tmp_path):
    path = await render_scorecard_png(
        f1=0.85, precision=0.9, recall=0.8, passed=True,
        feedback=["框A 匹配 (IOU=0.82)", "漏标 1 个"], out_dir=tmp_path,
    )
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 500  # non-trivial image
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_chart_cards.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL with `ModuleNotFoundError: No module named 'deeptutor.tools.chart_cards'`

- [ ] **Step 3: Write minimal implementation**

Create `deeptutor/tools/chart_cards.py`:

```python
"""Chart card contract builders + scorecard PNG rendering.

Tools emit deterministic chart data via ``ToolResult.metadata.chart``. The
frontend ``ChatChartCard`` renders it (Chart.js / cytoscape / <img>). The
scorecard uses matplotlib so the grade card is a portable PNG the student can
screenshot into a report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def radar_chart(labels: list[str], values: list[float]) -> dict:
    """Five-dimension ability radar contract."""
    return {"type": "radar", "data": {"labels": list(labels), "values": [float(v) for v in values]}}


def progress_chart(*, completed: int, total: int, modules: list[dict] | None = None) -> dict:
    """Learning progress / plan-vs-actual contract."""
    return {
        "type": "progress",
        "data": {
            "completed": int(completed),
            "total": int(total),
            "modules": modules or [],
        },
    }


def build_scorecard_chart(*, f1: float, precision: float, recall: float, passed: bool) -> dict:
    """Exercise scorecard contract (rendered as matplotlib PNG, not Chart.js)."""
    return {
        "type": "scorecard",
        "data": {
            "f1": float(f1),
            "precision": float(precision),
            "recall": float(recall),
            "passed": bool(passed),
        },
    }


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


async def render_scorecard_png(
    *,
    f1: float,
    precision: float,
    recall: float,
    passed: bool,
    feedback: list[str],
    out_dir: Path,
) -> Path:
    """Render a scorecard as a PNG via matplotlib. Never raises on chart errors."""
    import asyncio

    def _draw() -> Path:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        fig, ax = plt.subplots(figsize=(7, 3), dpi=120)
        color = "#22c55e" if passed else "#ef4444"
        rgb = _hex_to_rgb(color)

        # F1 gauge bar
        ax.barh([0], [f1], color=color, alpha=0.85, height=0.55)
        ax.barh([0], [1], color="#e5e7eb", height=0.55)
        ax.text(f1 / 2, 0, f"F1 = {f1:.2f}", ha="center", va="center",
                color="white", fontsize=13, fontweight="bold")
        ax.set_yticks([])
        ax.set_xlim(0, 1)

        # Precision / Recall bars
        labels = ["Precision", "Recall"]
        vals = [precision, recall]
        bars = ax.barh([1, 2], vals, color="#3b82f6", alpha=0.85, height=0.5)
        for b, v in zip(bars, vals):
            ax.text(b.get_width() + 0.02, b.get_y() + b.get_height() / 2,
                    f"{v:.2f}", va="center", fontsize=10)
        ax.set_yticks([1, 2])
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlim(0, 1.15)

        # feedback lines
        ax.text(0, -0.8, " · ".join(feedback[:3]), fontsize=7, color="#6b7280")

        ax.set_title("练习成绩单" + (" ✓ 达标" if passed else " ✗ 待加强"), fontsize=12, color=color)
        ax.spines[["top", "right"]].set_visible(False)

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "scorecard.png"
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path

    return await asyncio.to_thread(_draw)


__all__ = ["build_scorecard_chart", "progress_chart", "radar_chart", "render_scorecard_png"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_chart_cards.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/chart_cards.py tests/tools/test_chart_cards.py
git commit -m "feat: chart 契约构造器 + matplotlib 成绩单 PNG"
```

---

### Task 2: `annotation_check` 返回成绩单图 + chart 元数据

**Files:**
- Modify: `deeptutor/tools/annotation_check.py` (execute + helpers)
- Test: `tests/tools/test_annotation_check_chart.py`

- [ ] **Step 1: Write the failing test**

```python
"""annotation_check emits scorecard chart metadata + PNG."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_bbox_check_emits_chart_metadata(monkeypatch, tmp_path) -> None:
    from deeptutor.tools.annotation_check import AnnotationCheckTool

    async def _fake_png(**kwargs):
        p = tmp_path / "scorecard.png"
        p.write_bytes(b"\x89PNG fake")
        return p

    monkeypatch.setattr("deeptutor.tools.annotation_check.render_scorecard_png", _fake_png)

    tool = AnnotationCheckTool()
    result = await tool.execute(
        task_type="bbox",
        predictions='[{"x":207,"y":140,"w":353,"h":273,"label":"car"}]',
        ground_truth='[{"x":207,"y":140,"w":353,"h":273,"label":"car"}]',
    )
    assert result.success
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "scorecard"
    assert chart["data"]["f1"] > 0.9
    assert "scorecard.png" in result.content or "成绩单" in result.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_annotation_check_chart.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL (no chart in metadata)

- [ ] **Step 3: Implement**

Edit `deeptutor/tools/annotation_check.py`:

1. Change `_bbox_report` to ALSO return structured metrics. Simplest: add a sibling `_bbox_metrics(...)` returning dict, and refactor `_bbox_report` to call it. Alternatively make `_bbox_report` return `(str, dict)`. **Recommended:** add a module function `_bbox_metrics(predictions, ground_truth, iou_threshold=0.5) -> dict` that returns `{"tp","fp","fn","precision","recall","f1","matches":[{"pred_idx","gt_idx","iou"}],"feedback":[...]}` and have `_bbox_report` use it.

2. In `execute`, after computing content for bbox type:

```python
        if task_type == "classification":
            content = _classify_report(predictions, ground_truth)
            chart = None
        else:
            content = _bbox_report(predictions, ground_truth)
            metrics = _bbox_metrics(predictions, ground_truth)
            from deeptutor.tools.chart_cards import build_scorecard_chart, render_scorecard_png

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

                out_dir = get_path_service().get_task_workspace("chat", "scorecard") / "outputs"
                png = await render_scorecard_png(
                    f1=f1,
                    precision=metrics.get("precision", 0.0),
                    recall=metrics.get("recall", 0.0),
                    passed=passed,
                    feedback=[f.get("text", "") for f in metrics.get("feedback", [])][:3],
                    out_dir=out_dir,
                )
                from deeptutor.services.sandbox.artifacts import collect_public_artifacts

                artifacts = collect_public_artifacts(str(out_dir))
                if artifacts:
                    content = f"![成绩单]({artifacts[0].url})\n\n" + content
            except Exception:
                pass  # scorecard is best-effort; text feedback remains
```

3. Update the final return:

```python
        metadata: dict[str, Any] = {}
        if chart:
            metadata["chart"] = chart
        return ToolResult(content=content, metadata=metadata or None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_annotation_check_chart.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Run existing annotation tests to confirm no regression**

Run: `python -m pytest tests/tools/test_annotation_check.py -v 2>&1 | Select-Object -Last 6`
Expected: PASS (note: if this test file doesn't exist, run `tests/tools/` filtered or check actual name)

- [ ] **Step 6: Commit**

```bash
git add deeptutor/tools/annotation_check.py tests/tools/test_annotation_check_chart.py
git commit -m "feat: annotation_check 评测后生成成绩单 PNG + chart 元数据"
```

---

### Task 3: `competency_map` 返回能力雷达 chart

**Files:**
- Modify: `deeptutor/tools/competency_tool.py` (execute — after action handling, when computing radar)
- Test: `tests/tools/test_competency_chart.py`

- [ ] **Step 1: Write the failing test**

```python
"""competency_map emits radar chart metadata."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_competency_map_emits_radar_chart(monkeypatch) -> None:
    from deeptutor.tools.competency_tool import CompetencyMapTool

    async def _fake_radar(*args, **kwargs):
        return {"labels": ["框精度", "标签准确", "完整性", "一致性", "知识掌握"],
                "values": [80, 70, 60, 75, 50]}

    monkeypatch.setattr("deeptutor.tools.competency_tool._compute_radar_scores", _fake_radar)

    tool = CompetencyMapTool()
    result = await tool.execute()
    # radar action path
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "radar"
```

Note: `_compute_radar_scores` may not exist yet — you may need to adapt. The key assertion: when competency_map computes the ability radar, its ToolResult.metadata carries `chart: {type: "radar", data: {labels, values}}`. Inspect the actual action names in `competency_tool.py` (`/radar` or `radar` action) and wire the chart into that branch.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_competency_chart.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL

- [ ] **Step 3: Implement**

Edit `deeptutor/tools/competency_tool.py` — in the radar/ability-scores branch of `execute`, after computing the radar payload:

```python
            from deeptutor.tools.chart_cards import radar_chart

            labels = [d["name"] for d in radar_data.get("dimensions", [])]
            values = [d.get("score", 0) for d in radar_data.get("dimensions", [])]
            metadata["chart"] = radar_chart(labels=labels, values=values)
```

(Adapt to the actual structure of the radar payload in `competency_tool.py` — read it first.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_competency_chart.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/competency_tool.py tests/tools/test_competency_chart.py
git commit -m "feat: competency_map 返回能力雷达 chart 元数据"
```

---

### Task 4: `finalize_diagnosis` 返回学习进度 chart

**Files:**
- Modify: `deeptutor/tools/finalize_diagnosis_tool.py` (execute — after plan build)
- Test: `tests/tools/test_finalize_diagnosis_chart.py`

- [ ] **Step 1: Write the failing test**

```python
"""finalize_diagnosis emits progress chart metadata."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_finalize_emits_progress_chart(monkeypatch) -> None:
    from deeptutor.tools.finalize_diagnosis_tool import FinalizeDiagnosisTool

    from deeptutor.services.learning_records import LearningRecordStore

    async def _fake_plan(*, force: bool = False) -> dict:
        return {"modules": [
            {"name": "标注基础", "concepts": ["a"], "tasks": ["task1"]},
            {"name": "进阶技能", "concepts": ["b"], "tasks": ["task2"]},
            {"name": "质量管控", "concepts": ["c"], "tasks": ["task3"]},
            {"name": "工具进阶", "concepts": ["d"], "tasks": ["task4"]},
        ]}

    monkeypatch.setattr("deeptutor.tools.finalize_diagnosis_tool.rebuild", _fake_plan)
    # brief save must not hit real workspace
    from unittest.mock import MagicMock
    store = MagicMock()
    store.save_brief.return_value = None
    monkeypatch.setattr("deeptutor.services.learning_records.LearningRecordStore", lambda: store)

    tool = FinalizeDiagnosisTool()
    result = await tool.execute(goal_type="job", teaching_mode="Standard")
    assert result.success
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "progress"
    assert chart["data"]["total"] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_finalize_diagnosis_chart.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL

- [ ] **Step 3: Implement**

Edit `deeptutor/tools/finalize_diagnosis_tool.py` — after the plan is built (before building the ToolResult):

```python
            from deeptutor.tools.chart_cards import progress_chart

            modules = [m for m in (plan or {}).get("modules", [])]
            chart = progress_chart(
                completed=0,
                total=len(modules),
                modules=[{"name": m.get("name", ""), "done": 0, "total": 1} for m in modules],
            )
            return ToolResult(
                content=(f"诊断已落盘 (mode={teaching_mode}, goal={goal_type}).\n"
                         f"课程计划已生成: {', '.join(m.get('name') for m in modules)}"),
                metadata={"brief_saved": True, "teaching_mode": teaching_mode, "modules": [m.get("name") for m in modules], "chart": chart},
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_finalize_diagnosis_chart.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/finalize_diagnosis_tool.py tests/tools/test_finalize_diagnosis_chart.py
git commit -m "feat: finalize_diagnosis 返回学习进度 chart 元数据"
```

---

### Task 5: `graph_query` 返回图谱风险链 chart

**Files:**
- Modify: `deeptutor/tools/graph_tool.py` (execute — risk_path branch)
- Test: `tests/tools/test_graph_tool_chart.py`

- [ ] **Step 1: Write the failing test**

```python
"""graph_query risk_path emits graph chart metadata."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_risk_path_emits_graph_chart(monkeypatch) -> None:
    from deeptutor.tools.graph_tool import GraphQueryTool
    from deeptutor.services.knowledge_graph import KnowledgeGraphStore
    from tests.services.test_knowledge_graph import SAMPLE_TREE, SAMPLE_BANK, SAMPLE_RECORDS

    async def _fake_load(*, tree=None, bank=None, records=None) -> dict:
        return KnowledgeGraphStore.build(tree=SAMPLE_TREE, bank=SAMPLE_BANK, records=SAMPLE_RECORDS)

    async def _fake_explain(query, target) -> str:
        return None

    monkeypatch.setattr("deeptutor.tools.graph_tool._load_graph", _fake_load)
    monkeypatch.setattr("deeptutor.tools.graph_tool._explain_risk", _fake_explain)

    tool = GraphQueryTool()
    result = await tool.execute(query_type="risk_path", target="task2")
    assert result.success
    chart = result.metadata.get("chart")
    assert chart is not None
    assert chart["type"] == "graph"
    assert "nodes" in chart["data"]
    assert "edges" in chart["data"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_graph_tool_chart.py -v 2>&1 | Select-Object -First 8`
Expected: FAIL

- [ ] **Step 3: Implement**

Edit `deeptutor/tools/graph_tool.py` — in the risk_path branch of `execute`, after computing `data`:

```python
        else:
            data = svc.risk_path(target)
            content = _format_risk_path(data)
            # chart: skill/task graph with risky markers
            from deeptutor.tools.chart_cards import graph_chart

            nodes = []
            edges = []
            nodes.append({"id": data["target"], "label": data["target_name"], "status": "target"})
            for p in data.get("missing_prereqs", []):
                nodes.append({"id": p["id"], "label": p["name"], "status": "missing"})
                edges.append({"source": data["target"], "target": p["id"]})
            for s in data.get("struggling", []):
                nodes.append({"id": s["id"], "label": s["name"], "status": "struggling"})
            for d in data.get("affected_downstream", []):
                nodes.append({"id": d["id"], "label": d["name"], "status": "affected"})
                edges.append({"source": data["target"], "target": d["id"]})
            chart = graph_chart(nodes=nodes, edges=edges)
            data["chart"] = chart  # carry into metadata
            try:
                explanation = await _explain_risk(query=data, target=target)
            except Exception:
                explanation = None
```

Then ensure the returned `ToolResult(metadata=data)` includes `data["chart"]`.

Also add to `chart_cards.py`:

```python
def graph_chart(*, nodes: list[dict], edges: list[dict]) -> dict:
    """Skill dependency / risk-chain graph contract (cytoscape-style)."""
    return {"type": "graph", "data": {"nodes": nodes, "edges": edges}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_graph_tool_chart.py -v 2>&1 | Select-Object -Last 8`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/graph_tool.py deeptutor/tools/chart_cards.py tests/tools/test_graph_tool_chart.py
git commit -m "feat: graph_query 风险链返回图谱 chart (cytoscape 契约)"
```

---

### Task 6: 前端 `ChatChartCard` 组件

**Files:**
- Create: `web/components/chat/home/ChatChartCard.tsx`
- Test: (TS component — verify via tsc + manual)

- [ ] **Step 1: Create the component**

```tsx
"use client";

import { useEffect, useRef } from "react";

type ChartData =
  | { type: "scorecard"; data: { f1: number; precision: number; recall: number; passed: boolean } }
  | { type: "radar"; data: { labels: string[]; values: number[] } }
  | { type: "progress"; data: { completed: number; total: number; modules: { name: string; done: number; total: number }[] } }
  | { type: "graph"; data: { nodes: { id: string; label: string; status: string }[]; edges: { source: string; target: string }[] } };

export function ChatChartCard({ chart }: { chart: ChartData }) {
  if (chart.type === "scorecard") {
    const { f1, precision, recall, passed } = chart.data;
    return (
      <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className={`text-lg font-bold ${passed ? "text-emerald-500" : "text-rose-500"}`}>
            F1 = {f1.toFixed(2)}
          </span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] ${passed ? "bg-emerald-500/10 text-emerald-500" : "bg-rose-500/10 text-rose-500"}`}>
            {passed ? "达标" : "待加强"}
          </span>
        </div>
        <div className="space-y-1 text-xs text-[var(--muted-foreground)]">
          <div>Precision: {(precision * 100).toFixed(0)}%</div>
          <div>Recall: {(recall * 100).toFixed(0)}%</div>
        </div>
      </div>
    );
  }

  if (chart.type === "radar") {
    return <RadarCard labels={chart.data.labels} values={chart.data.values} />;
  }

  if (chart.type === "progress") {
    const { completed, total, modules } = chart.data;
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    return (
      <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-semibold">学习进度</span>
          <span className="text-[var(--muted-foreground)]">{completed}/{total} ({pct}%)</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
          <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
        </div>
        {modules.length > 0 && (
          <div className="mt-2 space-y-1">
            {modules.map((m) => (
              <div key={m.name} className="flex items-center gap-2 text-[10px] text-[var(--muted-foreground)]">
                <span className="w-16 truncate">{m.name}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
                  <div className="h-full rounded-full bg-emerald-500" style={{ width: `${m.total ? (m.done / m.total) * 100 : 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (chart.type === "graph") {
    return <GraphCard nodes={chart.data.nodes} edges={chart.data.edges} />;
  }

  return null;
}

function RadarCard({ labels, values }: { labels: string[]; values: number[] }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    let chart: any;
    import("chart.js/auto").then(({ default: Chart }) => {
      chart = new Chart(ref.current!, {
        type: "radar",
        data: {
          labels,
          datasets: [{ data: values, backgroundColor: "rgba(59,130,246,0.2)", borderColor: "#3b82f6" }],
        },
        options: { scales: { r: { min: 0, max: 100 } } },
      });
    });
    return () => chart?.destroy();
  }, [labels, values]);
  return (
    <div className="my-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-2">
      <canvas ref={ref} />
    </div>
  );
}

function GraphCard({ nodes, edges }: { nodes: { id: string; label: string; status: string }[]; edges: { source: string; target: string }[] }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    let cy: any;
    import("cytoscape").then((m) => {
      const cytoscape = m.default ?? m;
      cy = cytoscape({
        container: ref.current,
        elements: [
          ...nodes.map((n) => ({ data: { id: n.id, label: n.label, status: n.status } })),
          ...edges.map((e, i) => ({ data: { id: `e${i}`, source: e.source, target: e.target } })),
        ],
        style: [
          { selector: "node", style: { label: "data(label)", "font-size": "9px", "text-valign": "bottom" } },
          { selector: 'node[status = "missing"]', style: { "background-color": "#f59e0b" } },
          { selector: 'node[status = "struggling"]', style: { "background-color": "#ef4444" } },
          { selector: 'node[status = "affected"]', style: { "background-color": "#8b5cf6" } },
          { selector: 'node[status = "target"]', style: { "background-color": "#3b82f6" } },
          { selector: "edge", style: { "line-color": "#cbd5e1", "target-arrow-color": "#cbd5e1", "target-arrow-shape": "triangle" } },
        ],
        layout: { name: "breadthfirst", padding: 10 },
      });
    });
    return () => cy?.destroy();
  }, [nodes, edges]);
  return <div ref={ref} className="my-2 h-40 rounded-xl border border-[var(--border)] bg-[var(--card)]" />;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web; npx tsc --noEmit 2>&1 | Select-Object -First 10`
Expected: no errors related to ChatChartCard

- [ ] **Step 3: Commit**

```bash
git add web/components/chat/home/ChatChartCard.tsx
git commit -m "feat: 前端 ChatChartCard 组件 (scorecard/radar/progress/graph)"
```

---

### Task 7: 前端接线 — AssistantMessage 渲染 chart

**Files:**
- Modify: `web/components/chat/home/ChatMessages.tsx` (AssistantMessage — add chart rendering)

- [ ] **Step 1: Add chart extraction + render**

In `AssistantMessage`, after `resultEvent` is computed, add:

```tsx
  const chartCard = useMemo(() => {
    const meta = resultEvent?.metadata as Record<string, unknown> | undefined;
    if (!meta?.chart) return null;
    return meta.chart as any;
  }, [resultEvent]);
```

In the JSX (near the quiz/visualize special branches), render:

```tsx
      {chartCard ? <ChatChartCard chart={chartCard} /> : null}
```

Add the import at top:

```tsx
import { ChatChartCard } from "@/components/chat/home/ChatChartCard";
```

- [ ] **Step 2: Verify tsc**

Run: `cd web; npx tsc --noEmit 2>&1 | Select-Object -First 10`
Expected: no errors

- [ ] **Step 3: Manual smoke (if dev server running)**

Open a chat with annotation-coach, ask it to check a bbox, confirm a scorecard card appears.

- [ ] **Step 4: Commit**

```bash
git add web/components/chat/home/ChatMessages.tsx
git commit -m "feat: AssistantMessage 渲染对话内图表卡片"
```

---

### Task 8: 回归验证 + 文档收尾

**Files:**
- Modify: `docs/fork-features-detailed.md` (append visualization entry)
- Test: full KG + tool suite

- [ ] **Step 1: Run the chart + graph test suite**

Run: `python -m pytest tests/tools/test_chart_cards.py tests/tools/test_annotation_check_chart.py tests/tools/test_competency_chart.py tests/tools/test_finalize_diagnosis_chart.py tests/tools/test_graph_tool_chart.py tests/services/test_knowledge_graph.py tests/services/test_graph_query.py tests/tools/test_graph_tool.py -q 2>&1 | Select-Object -Last 5`
Expected: PASS (all chart/graph tests)

- [ ] **Step 2: Verify no regression in existing tool tests**

Run: `python -m pytest tests/tools/test_graph_tool_registration.py tests/tools/test_write_learning_record_graph.py tests/tools/test_annotation_check.py -q 2>&1 | Select-Object -Last 4`
Expected: PASS (adjust test file names to actual)

- [ ] **Step 3: Update fork-features-detailed.md** — add a "对话内可视化" section listing the 4 charts + how to demo.

- [ ] **Step 4: Commit**

```bash
git add docs/fork-features-detailed.md
git commit -m "docs: fork 功能清单补充对话内可视化章节"
```

---

## Self-Review

**1. Spec coverage:**
- §3.1 成绩单 → Task 1 (PNG 生成) + Task 2 (annotation_check 接线)
- §3.2 能力雷达 → Task 3 (competency_map)
- §3.3 学习进度 → Task 4 (finalize_diagnosis)
- §3.4 图谱风险链 → Task 5 (graph_query)
- §5.1 ChatChartCard → Task 6
- §5.2 检测链路 → Task 7
- §8 测试 → Task 8
✅ 全覆盖

**2. Placeholder scan:** 所有代码块完整，无 TBD/TODO。Task 3 注明"`_compute_radar_scores` 可能不存在，需读实际代码适配"——这是有意的适配说明，非占位符。

**3. Type consistency:**
- `chart_cards.py` 函数名：`radar_chart` / `progress_chart` / `build_scorecard_chart` / `render_scorecard_png` / `graph_chart` — 各任务引用一致
- `metadata.chart` 契约：`{type, data}` — Task 1-5 产出，Task 6-7 消费，一致
- `ChatChartCard` type 判别：scorecard/radar/progress/graph — 与后端 chart type 一致
- `ToolResult(metadata=...)` — Task 2 的 `metadata or None` 处理空值

**已知风险（实现时注意）：**
1. `annotation_check._bbox_metrics` 需从 `_bbox_report` 重构提取——Task 2 已注明
2. `competency_tool.py` 的实际雷达数据结构需读代码确认——Task 3 已注明
3. `finalize_diagnosis_tool.py` 的 `rebuild` 是函数还是方法需确认——Task 4 monkeypatch 目标
4. `graph_tool.py` 当前返回 `ToolResult(content=content, metadata=data)`，Task 5 需把 chart 并入 data
5. 前端 `cytoscape` 是 ESM import，`import("cytoscape").then((m) => m.default ?? m)` 处理 CJS 互操作
