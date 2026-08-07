# 议题④ Phase 3b + 3c 实现计划：评分端点 + 能力路径进度条

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `POST /api/v1/annotation/check` 评分 HTTP 端点（薄封装既有 `annotation_check` 的 `_*_dict` 系列，供前端/Coach 实时反馈），并在 annotation 页加能力路径 + 掌握度进度条（纯读展示，无 iframe 冲突）。

**Architecture:** 3b = FastAPI router 薄封装 `deeptutor/tools/annotation_check.py` 的纯函数（无 IO、可 import、全部同步），复用 `_bbox_dict`/`_classify_dict`/`_judgment_dict`/`_standard_dict`/`_error_case_dict`/`_audio_event_dict`/`_audio_transcription_dict`/`_video_tracking_dict`/`_video_event_dict`/`_ner_dict`。3c = 前端 `AnnotationProgress` 组件读 `GET /api/v1/profile/teaching-flow` + `/skill-tree` 展示。

**Tech Stack:** Python 3.11+ FastAPI / pytest（TestClient，仿 `tests/api/test_memory_buckets.py`）/ TypeScript React。

---

## 背景（已核实）

- `deeptutor/tools/annotation_check.py`：10 种 task_type（bbox/classification/judgment/standard/error_case/audio_event/audio_transcription/video_tracking/video_event/ner），全部有 `_*_dict` 纯函数（如 `_bbox_dict` L487-497）返回 metrics dict。**可直接 import 调用，无副作用**。
- 主 API 注册模式：`deeptutor/api/main.py` 的 `_auth = [Depends(require_auth)]`，`app.include_router(router, prefix="/api/v1/...", dependencies=_auth)`。
- **iframe 归属**：`annotation_tool*.html` 由另一会话所有，**本轮不侵入**。3b 只做后端端点；前端实时反馈接入留待 iframe 归属确认后（Coach 气泡展示可作为无侵入过渡）。
- annotation 页：`web/app/(workspace)/annotation/page.tsx`，5 tab，`<AnnotationCoach />` 已挂载（3a 完成）。
- profile 端点：`GET /api/v1/profile/teaching-flow`（`profile.py:222`）、`GET /api/v1/profile/skill-tree`（`profile.py:69`）已存在。

## 任务分解

### Task 1: 后端——`POST /api/v1/annotation/check` 评分端点

**Files:**
- Create: `deeptutor/api/routers/annotation.py`
- Modify: `deeptutor/api/main.py`（import + include_router）
- Test: `tests/api/test_annotation_check_router.py`

- [ ] **Step 1: 写失败测试**——仿 `tests/api/test_memory_buckets.py` 模式（独立 FastAPI app + include_router）

创建 `tests/api/test_annotation_check_router.py`：

```python
"""Annotation grading endpoint — POST /api/v1/annotation/check.

Thin HTTP wrapper over the pure ``annotation_check._*_dict`` metrics so the
annotation tools / Coach / frontend can grade a submission without routing
through the chat loop. No Label Studio dependency.
"""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip("fastapi")

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient

annotation_router = importlib.import_module("deeptutor.api.routers.annotation").router

API = "/api/v1/annotation"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(annotation_router, prefix=API)
    return TestClient(app)


def test_check_bbox(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "bbox",
            "predictions": [
                {"x": 10, "y": 10, "w": 50, "h": 50, "label": "cat"},
                {"x": 90, "y": 90, "w": 50, "h": 50, "label": "cat"},
            ],
            "ground_truth": [{"x": 10, "y": 10, "w": 50, "h": 50, "label": "cat"}],
            "image_size": "500x500",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "precision" in data["metrics"]
    assert "recall" in data["metrics"]
    assert "f1" in data["metrics"]
    assert data["metrics"]["f1"] > 0


def test_check_classification(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "classification",
            "predictions": [{"id": 1, "label": "positive"}],
            "ground_truth": [{"id": 1, "label": "positive"}, {"id": 2, "label": "negative"}],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["accuracy"] == 0.5
    assert data["metrics"]["correct"] == 1
    assert data["metrics"]["total"] == 2


def test_check_ner(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "ner",
            "predictions": [{"start": 0, "end": 4, "label": "PER"}],
            "ground_truth": [{"start": 0, "end": 4, "label": "PER"}, {"start": 9, "end": 13, "label": "LOC"}],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["f1"] > 0


def test_check_invalid_task_type(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "bogus",
            "predictions": [],
            "ground_truth": [],
        },
    )
    assert res.status_code == 400


def test_check_invalid_json(client: TestClient) -> None:
    res = client.post(
        f"{API}/check",
        json={
            "task_type": "bbox",
            "predictions": "not-json",
            "ground_truth": "[]",
        },
    )
    assert res.status_code == 400
```

- [ ] **Step 2: 运行确认失败**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_annotation_check_router.py -q
```

Expected: FAIL（ModuleNotFoundError / 404）。

- [ ] **Step 3: 创建 router**——`deeptutor/api/routers/annotation.py`：

```python
"""Annotation grading router — HTTP wrapper over annotation_check metrics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from deeptutor.tools import annotation_check

router = APIRouter()

# task_type -> (dict_metrics_fn, report_fn)
_SCORERS = {
    "bbox": annotation_check._bbox_dict,
    "classification": annotation_check._classify_dict,
    "judgment": annotation_check._judgment_dict,
    "standard": annotation_check._standard_dict,
    "error_case": annotation_check._error_case_dict,
    "audio_event": annotation_check._audio_event_dict,
    "audio_transcription": annotation_check._audio_transcription_dict,
    "video_tracking": annotation_check._video_tracking_dict,
    "video_event": annotation_check._video_event_dict,
    "ner": annotation_check._ner_dict,
}


def _load_json_list(raw: Any, field: str) -> list[dict]:
    import json

    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"{field} 不是合法 JSON: {exc}") from exc
        if isinstance(parsed, list):
            return parsed
    raise HTTPException(status_code=400, detail=f"{field} 必须是 JSON 数组")


@router.post("/check")
async def check_annotation(body: dict[str, Any]) -> dict[str, Any]:
    """Grade a single annotation submission against ground truth.

    Body: ``{task_type, predictions, ground_truth, image_size?}``.
    Returns ``{task_type, metrics, report}``. ``task_type`` defaults to ``bbox``.
    """
    task_type = str(body.get("task_type") or "bbox").strip()
    if task_type not in _SCORERS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 task_type: {task_type}（可选: {', '.join(sorted(_SCORERS))}）",
        )
    predictions = _load_json_list(body.get("predictions"), "predictions")
    ground_truth = _load_json_list(body.get("ground_truth"), "ground_truth")

    metrics = _SCORERS[task_type](predictions, ground_truth)

    report = ""
    if task_type == "bbox":
        report, _ = annotation_check._bbox_report(predictions, ground_truth)
    elif task_type == "classification":
        report = annotation_check._classify_report(predictions, ground_truth)
    elif task_type == "ner":
        report = annotation_check._ner_report(predictions, ground_truth)
    elif task_type == "audio_event":
        report = annotation_check._audio_event_report(predictions, ground_truth)
    elif task_type == "video_event":
        report = annotation_check._video_event_report(predictions, ground_truth)
    elif task_type == "video_tracking":
        report = annotation_check._video_tracking_report(predictions, ground_truth)

    return {"task_type": task_type, "metrics": metrics, "report": report}
```

> 说明：`_SCORERS` 已映射全部 10 种 `_*_dict`，`bbox`/`audio_event`/`video_event` 的 scorer 接受 `iou_threshold`/`tiou_threshold` 可选参数（当前用默认值）。

- [ ] **Step 4: 注册到 main.py**——在 `deeptutor/api/main.py` 的 router import 列表加 `annotation`（L307-340 import 块内），并在其他 `include_router` 附近加：

```python
app.include_router(
    annotation.router,
    prefix="/api/v1/annotation",
    tags=["annotation"],
    dependencies=_auth,
)
```

（`_auth` 定义于 L353，`include_router` 需在其后——放在 `profile.router` 行附近。）

- [ ] **Step 5: 运行确认通过**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_annotation_check_router.py -v
```

Expected: 5 passed。

- [ ] **Step 6: Commit**

```bash
git add deeptutor/api/routers/annotation.py deeptutor/api/main.py tests/api/test_annotation_check_router.py
git commit -m "feat: 新增 POST /api/v1/annotation/check 评分端点 (④ 3b)"
```

---

### Task 2: 后端——router 覆盖 10 种 task_type 全量测试

**Files:**
- Test: `tests/api/test_annotation_check_router.py`（追加）

- [ ] **Step 1: 追加参数化测试**——覆盖剩余 task_type（judgment/standard/error_case/audio_event/audio_transcription/video_tracking/video_event），确保 `_SCORERS` 映射完整、无 KeyError

```python
@pytest.mark.parametrize(
    "task_type, predictions, ground_truth, metric_key",
    [
        ("judgment", [{"id": 1, "label": "true"}], [{"id": 1, "answer": True}], "accuracy"),
        ("standard", [{"x": 1, "y": 2, "w": 3, "h": 4, "label": "cat"}], [{"required_fields": ["x", "y", "w", "h", "label"], "labels": ["cat"]}], "compliance_rate"),
        ("error_case", [{"id": 1, "flagged": True}], [{"id": 1, "is_error": True}], "accuracy"),
        ("audio_event", [{"label": "knock", "start_time": 0.0, "end_time": 1.0}], [{"label": "knock", "start_time": 0.0, "end_time": 1.0}], "f1"),
        ("audio_transcription", [{"id": 1, "text": "hello world"}], [{"id": 1, "text": "hello world"}], "accuracy"),
        ("video_tracking", [{"frame": 0, "boxes": [{"x": 0, "y": 0, "w": 5, "h": 5, "label": "a"}]}], [{"frame": 0, "boxes": [{"x": 0, "y": 0, "w": 5, "h": 5, "label": "a"}]}], "f1"),
        ("video_event", [{"label": "run", "start_time": 0.0, "end_time": 2.0}], [{"label": "run", "start_time": 0.0, "end_time": 2.0}], "f1"),
    ],
)
def test_check_other_task_types(client, task_type, predictions, ground_truth, metric_key):
    res = client.post(f"{API}/check", json={"task_type": task_type, "predictions": predictions, "ground_truth": ground_truth})
    assert res.status_code == 200
    data = res.json()
    assert data["task_type"] == task_type
    assert metric_key in data["metrics"]
```

- [ ] **Step 2: 运行确认通过**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_annotation_check_router.py -q
```

Expected: 12 passed（5 + 7 参数化）。

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_annotation_check_router.py
git commit -m "test: annotation/check 全 10 种 task_type 覆盖 (④ 3b)"
```

---

### Task 3: 前端——`AnnotationProgress` 能力路径 + 掌握度进度条（3c）

**Files:**
- Create: `web/components/annotation/AnnotationProgress.tsx`
- Modify: `web/app/(workspace)/annotation/page.tsx`（挂载 1 行）

- [ ] **Step 1: 创建组件**——`web/components/annotation/AnnotationProgress.tsx`（"use client"，读 `GET /api/v1/profile/teaching-flow` + `/skill-tree`）

> 数据契约（已核实 `services/learning_records.py:673-708`）：`skill-tree` 返回 `{"tree": {"name", "id", "level", "mastered_count", "total_leaves", "children": [...]}}`；level-4 叶子节点有 `mastered`(bool)。**无 0-1 mastery 字段**——掌握度用根节点的 `mastered_count / total_leaves` 计算。

```tsx
"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { MapPin } from "lucide-react";

interface FlowState {
  has_flow: boolean;
  task_id?: string;
  current_step?: string;
  steps?: Record<string, unknown>;
}

interface SkillTreeNode {
  id?: string;
  name?: string;
  level?: number;
  mastered?: boolean;
  mastered_count?: number;
  total_leaves?: number;
}

interface SkillTree {
  tree?: SkillTreeNode;
}

export default function AnnotationProgress() {
  const { t } = useTranslation();
  const [flow, setFlow] = useState<FlowState | null>(null);
  const [tree, setTree] = useState<SkillTreeNode | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [flowRes, skillRes] = await Promise.all([
          fetch("/api/v1/profile/teaching-flow"),
          fetch("/api/v1/profile/skill-tree"),
        ]);
        if (cancelled) return;
        if (flowRes.ok) setFlow((await flowRes.json()) as FlowState);
        if (skillRes.ok) {
          const data = (await skillRes.json()) as SkillTree;
          setTree(data.tree ?? null);
        }
      } catch {
        // 静默失败：教学进度展示为可选增强
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const masteredCount = tree?.mastered_count ?? 0;
  const totalLeaves = tree?.total_leaves ?? 1;
  const pct = Math.round((masteredCount / totalLeaves) * 100);

  if (!flow?.has_flow && !tree) return null;

  return (
    <div className="flex items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-2 text-xs">
      <MapPin className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
      <span className="text-[var(--muted-foreground)]">
        {t("annotation.currentTask", "当前任务在能力树位置")}
      </span>
      {tree?.name && (
        <span className="font-medium text-[var(--foreground)]">{tree.name}</span>
      )}
      {tree && (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-28 overflow-hidden rounded-full bg-[var(--border)]">
            <div
              className="h-full rounded-full bg-[var(--primary)]"
              style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
            />
          </div>
          <span className="text-[var(--muted-foreground)]">
            {masteredCount}/{totalLeaves}
          </span>
        </div>
      )}
      {flow?.current_step && (
        <span className="ml-auto rounded-full border border-[var(--border)] px-2 py-0.5 text-[var(--muted-foreground)]">
          {t("annotation.flowStep", "教学流程")}: {flow.current_step}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 挂载到 annotation 页**——在 `web/app/(workspace)/annotation/page.tsx` import 处加：

```tsx
import AnnotationProgress from "@/components/annotation/AnnotationProgress";
```

在 `<header>` 之后、`<div className="flex-1">` 之前加：

```tsx
      <AnnotationProgress />
```

- [ ] **Step 3: 补 i18n key**——查 `web/locales/zh/app.json` 是否已有 `annotation.currentTask`/`annotation.flowStep`；若无则按文件字母序添加 `"currentTask": "当前任务在能力树位置"` 与 `"flowStep": "教学流程"`（en 对应 `"currentTask": "Current task position"`/`"flowStep": "Flow step"`）。若组件用 default 值兜底、不强依赖 i18n 也行——但按项目约定补全。

- [ ] **Step 4: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误（预存在错误不算）。

- [ ] **Step 5: Commit**

```bash
git add web/components/annotation/AnnotationProgress.tsx web/app/\(workspace\)/annotation/page.tsx web/locales/zh/app.json web/locales/en/app.json
git commit -m "feat: annotation 页能力路径 + 掌握度进度条 (④ 3c)"
```

---

## 验证
- 后端：`python -m pytest tests/api/test_annotation_check_router.py -v`（12 passed）+ 回归 `python -m pytest tests/api/ -q`（允许预存在失败）
- `ruff check deeptutor/api/routers/annotation.py deeptutor/api/main.py`
- 前端：`cd web && npx tsc --noEmit`（清代理）
- 冒烟（可选）：`start_all.bat` 后 curl POST `/api/v1/annotation/check`（bbox 样例）→ 200 返回 metrics；annotation 页顶部出现进度条

## 提交（仅 commit，不 push）
- 按 Task 拆 3 个 commit，大版本完成后等用户指示统一 push。**不触碰 `annotation_tool*.html`**（另一会话所有）。
