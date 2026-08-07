# 议题④ Phase 3b 前端反馈接入：home 页评分卡（无侵入 iframe）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 home 页把 iframe 标注工具提交的结果（经既有 `localStorage` 桥接 `annotation_last_result`）用新评分端点 `POST /api/v1/annotation/check` 二次评分，渲染即时评分卡（F1/精/召/教学提示），并把结构化指标附加到发给 Coach 的消息上——**完全不改 iframe，无侵入**。

**Architecture:** 复用 home 页既有 `annotation_pending_message` auto-send 钩子（`web/app/(workspace)/home/[[...sessionId]]/page.tsx:698-714`）。在其旁新增：读 `annotation_last_result`（含 `taskId`/`boxes`/`f1`），用 `taskId` 从 task_bank 取 ground_truth（新增轻量后端端点或前端直读——见 Task 2 决策），POST 到 `/api/v1/annotation/check`，把返回 metrics 渲染为评分卡组件；同时把结构化指标拼接进 `pendingMsg` 让 Coach 收到完整数据。

**Tech Stack:** TypeScript React / Next.js App Router / FastAPI（后端端点）/ task_bank.json（数据源）。

---

## 背景（已核实）

- iframe 提交时写 `localStorage.annotation_last_result = {taskId, taskTitle, f1, precision, recall, tp, total, boxes, message, time}` + `annotation_pending_message`，然后 `window.parent.location.href = '/home'`（`annotation_tool.html:313-336`）。
- home 页 `page.tsx:698-714`：读 pendingMsg，30 秒内 auto-send 给 Coach，随后 removeItem。
- 评分端点 `POST /api/v1/annotation/check` 已就绪（Task 1-2），`task_type` 默认 `bbox`，接受 `predictions`/`ground_truth`，返回 `{task_type, metrics, report}`。
- `data/user/workspace/task_bank.json`：22 任务，每任务含 `ground_truth`（bbox 数组）+ `type` + `modal`。
- **iframe 归属**：`annotation_tool*.html` 属另一会话，**本轮不触碰**。

## 任务分解

### Task 1: 后端——暴露 task_bank 单任务 ground_truth 端点

**Files:**
- Modify: `deeptutor/api/routers/annotation.py`（加 `GET /ground-truth/{task_id}`）
- Test: `tests/api/test_annotation_check_router.py`

前端需要按 `taskId` 拿 ground_truth（否则得读 data 文件，跨层）。加一个轻量端点。

- [ ] **Step 1: 写失败测试**——追加到 `tests/api/test_annotation_check_router.py`：

```python
def test_get_ground_truth_by_task_id(client: TestClient) -> None:
    import json
    from deeptutor.services.path_service import get_path_service

    bank_path = get_path_service().get_workspace_dir() / "task_bank.json"
    if not bank_path.exists():
        pytest.skip("task_bank.json not present")

    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    task_id = next(iter(bank))  # 顶层字典键即任务 id（如 "task1"）

    res = client.get(f"{API}/ground-truth/{task_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["task_id"] == task_id
    assert isinstance(data["ground_truth"], list)
    assert len(data["ground_truth"]) > 0

    res_missing = client.get(f"{API}/ground-truth/does-not-exist")
    assert res_missing.status_code == 404
```

> 已核实 task_bank 顶层为 `{"task1": {...}, ...}`，键即任务 id。

- [ ] **Step 2: 运行确认失败**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_annotation_check_router.py -q
```

Expected: FAIL（404）。

- [ ] **Step 3: 实现**——在 `deeptutor/api/routers/annotation.py` 加：

```python
@router.get("/ground-truth/{task_id}")
async def ground_truth(task_id: str) -> dict[str, Any]:
    """Look up a task's ground truth by task id (from task_bank.json)."""
    from deeptutor.services.path_service import get_path_service

    bank_path = get_path_service().get_workspace_dir() / "task_bank.json"
    if not bank_path.exists():
        raise HTTPException(status_code=404, detail="task_bank 不存在")
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    if task_id in bank:
        return {"task_id": task_id, "ground_truth": bank[task_id].get("ground_truth", [])}
    raise HTTPException(status_code=404, detail=f"找不到任务 {task_id}")
```

> 已核实：task_bank.json 顶层是 `{"task1": {...}, ...}` 字典，**键即任务 id**（`task1`/`task2`…），与 iframe 的 `currentTask` 完全一致；每任务含 `ground_truth`（bbox 数组）。`get_path_service().get_workspace_dir()` = `<user_data_dir>/workspace`。`json`/`Any` 已在文件顶部 import。**Lazy import 防循环**。

- [ ] **Step 4: 运行确认通过**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/api/test_annotation_check_router.py -q
```

Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add deeptutor/api/routers/annotation.py tests/api/test_annotation_check_router.py
git commit -m "feat: 新增 /annotation/ground-truth/{task_id} 端点 (④ 3b)"
```

---

### Task 2: 前端——`AnnotationResultCard` 评分卡组件

**Files:**
- Create: `web/components/annotation/AnnotationResultCard.tsx`

渲染 `POST /api/v1/annotation/check` 返回的 metrics + report（F1/精/召 + 教学提示）。纯展示组件，输入为评分响应。

- [ ] **Step 1: 创建组件**

```tsx
"use client";

import { useTranslation } from "react-i18next";
import { CheckCircle2, XCircle, AlertCircle } from "lucide-react";

interface CheckMetrics {
  precision?: number;
  recall?: number;
  f1?: number;
  accuracy?: number;
  correct?: number;
  total?: number;
  [key: string]: number | undefined;
}

interface AnnotationResultCardProps {
  metrics: CheckMetrics;
  report?: string;
}

function pct(value?: number): string {
  if (typeof value !== "number") return "—";
  return `${Math.round(value * 100)}%`;
}

export default function AnnotationResultCard({ metrics, report }: AnnotationResultCardProps) {
  const { t } = useTranslation();

  const f1 = typeof metrics.f1 === "number" ? metrics.f1 : null;
  const accuracy = typeof metrics.accuracy === "number" ? metrics.accuracy : null;
  const score = f1 ?? accuracy;

  let tone: "good" | "ok" | "bad" | "none" = "none";
  let Icon = AlertCircle;
  if (score !== null) {
    if (score >= 0.8) {
      tone = "good";
      Icon = CheckCircle2;
    } else if (score >= 0.6) {
      tone = "ok";
      Icon = AlertCircle;
    } else {
      tone = "bad";
      Icon = XCircle;
    }
  }

  const toneClass =
    tone === "good"
      ? "border-[var(--primary)]/40 text-[var(--primary)]"
      : tone === "bad"
        ? "border-[var(--destructive)]/40 text-[var(--destructive)]"
        : "border-[var(--border)] text-[var(--muted-foreground)]";

  return (
    <div className={`rounded-lg border p-3 text-xs ${toneClass}`}>
      <div className="mb-1 flex items-center gap-2 font-medium">
        <Icon className="h-4 w-4" />
        <span>{t("annotation.resultCard.title", "本次标注评分")}</span>
      </div>
      <div className="flex flex-wrap gap-4">
        {f1 !== null && (
          <span>{t("annotation.resultCard.f1", "F1")}: <b>{pct(f1)}</b></span>
        )}
        {metrics.precision !== undefined && (
          <span>{t("annotation.resultCard.precision", "精确率")}: <b>{pct(metrics.precision)}</b></span>
        )}
        {metrics.recall !== undefined && (
          <span>{t("annotation.resultCard.recall", "召回率")}: <b>{pct(metrics.recall)}</b></span>
        )}
        {accuracy !== null && (
          <span>{t("annotation.resultCard.accuracy", "准确率")}: <b>{pct(accuracy)}</b></span>
        )}
        {typeof metrics.correct === "number" && typeof metrics.total === "number" && (
          <span>
            {t("annotation.resultCard.correct", "正确")}: {metrics.correct}/{metrics.total}
          </span>
        )}
      </div>
      {report && (
        <div className="mt-2 max-h-28 overflow-auto border-t border-[var(--border)]/40 pt-2 text-[var(--muted-foreground)]">
          {report}
        </div>
      )}
    </div>
  );
}
```

> 风格对齐 `AnnotationProgress.tsx` / `AnnotationCoach.tsx`。已核实：`--destructive` 存在（globals.css:40），`--success` **不存在**——good tone 用 `--primary`。

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/annotation/AnnotationResultCard.tsx
git commit -m "feat: AnnotationResultCard 评分卡组件 (④ 3b)"
```

---

### Task 3: 前端——home 页读 annotation_last_result → 调评分端点 → 渲染评分卡 + 增强 Coach 消息

**Files:**
- Modify: `web/app/(workspace)/home/[[...sessionId]]/page.tsx`（`annotation_pending_message` 钩子附近）

- [ ] **Step 1: 读现有钩子并扩展**——`page.tsx:698-714` 的 `annotationAutoSendRef` 钩子。扩展逻辑（保留原 auto-send，新增评分卡 + 增强消息）：

```tsx
  // Detect pending annotation results from the annotation tool page
  const annotationAutoSendRef = useRef(false);
  const [annotationResult, setAnnotationResult] = useState<{
    metrics: Record<string, number | undefined>;
    report?: string;
  } | null>(null);
  useEffect(() => {
    if (annotationAutoSendRef.current) return;
    if (!state.sessionId) return;
    if (state.isStreaming) return;
    try {
      const pendingMsg = localStorage.getItem("annotation_pending_message");
      const pendingTime = Number(localStorage.getItem("annotation_pending_time") || "0");
      if (pendingMsg && Date.now() - pendingTime < 30000) {
        annotationAutoSendRef.current = true;
        localStorage.removeItem("annotation_pending_message");
        localStorage.removeItem("annotation_pending_time");
        // 评分卡：读最近结果 → 调评分端点 → 渲染
        const rawResult = localStorage.getItem("annotation_last_result");
        localStorage.removeItem("annotation_last_result");
        if (rawResult) {
          let enriched = pendingMsg;
          try {
            const result = JSON.parse(rawResult) as {
              taskId?: string;
              boxes?: unknown;
              f1?: number;
            };
            if (result.taskId && Array.isArray(result.boxes) && result.boxes.length > 0) {
              const gtRes = await fetch(
                `/api/v1/annotation/ground-truth/${encodeURIComponent(result.taskId)}`,
                { cache: "no-store" },
              );
              if (gtRes.ok) {
                const gtData = (await gtRes.json()) as { ground_truth?: unknown[] };
                const checkRes = await fetch("/api/v1/annotation/check", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    task_type: "bbox",
                    predictions: result.boxes,
                    ground_truth: gtData.ground_truth ?? [],
                  }),
                });
                if (checkRes.ok) {
                  const checkData = (await checkRes.json()) as {
                    metrics: Record<string, number | undefined>;
                    report?: string;
                  };
                  setAnnotationResult({
                    metrics: checkData.metrics,
                    report: checkData.report,
                  });
                  enriched = `${pendingMsg}\n\n（后端自动评分附在下方评分卡中，请结合评分给出针对性反馈）`;
                }
              }
            }
          } catch {
            // 评分卡失败不影响原 auto-send
          }
          void sendMessage(enriched);
        } else {
          void sendMessage(pendingMsg);
        }
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.sessionId, state.isStreaming, sendMessage]);
```

> 注意：原实现 `sendMessage(pendingMsg)` 无 `void`；扩展后统一 `void sendMessage(...)`。钩子内出现 `await`（fetch）——原钩子非 async，需改为 async（回调内 try/catch 已包裹，安全）。

- [ ] **Step 2: 渲染评分卡**——在 home 页消息区上方（或自动消息气泡前）挂 `<AnnotationResultCard metrics={...} report={...} />`（`annotationResult` 非空时）。**具体挂载位置由实现者判断**——建议作为消息流里的一条特殊卡片（auto-send 后紧邻），或页面顶部临时条。选择最贴近现有消息渲染结构的方式，并说明。

```tsx
import AnnotationResultCard from "@/components/annotation/AnnotationResultCard";
...
{annotationResult && (
  <AnnotationResultCard
    metrics={annotationResult.metrics}
    report={annotationResult.report}
  />
)}
```

- [ ] **Step 3: 补 i18n key**——`annotation.resultCard.title/f1/precision/recall/accuracy/correct`，zh/en 均补（仿 Task 3 上轮格式）。

- [ ] **Step 4: 验证 tsc + eslint**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 5: Commit**

```bash
git add web/app/\(workspace\)/home/\[\[...sessionId\]\]/page.tsx web/components/annotation/AnnotationResultCard.tsx web/locales/zh/app.json web/locales/en/app.json
git commit -m "feat: home 页标注评分卡 + 增强 Coach 消息 (④ 3b)"
```

---

## 验证
- 后端：`python -m pytest tests/api/test_annotation_check_router.py -q` + 回归 `tests/api/ -q`
- `ruff check deeptutor/api/routers/annotation.py`
- 前端：`cd web && npx tsc --noEmit`（清代理）
- 冒烟（可选）：`start_all.bat` → annotation 页提交 bbox → home 页出现评分卡 + Coach 收到增强消息

## 提交（仅 commit，不 push）
- 按 Task 拆 3 个 commit，大版本完成后等用户指示统一 push。**不触碰 `annotation_tool*.html`**。
