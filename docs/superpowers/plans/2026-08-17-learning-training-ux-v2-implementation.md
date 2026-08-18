# 学习页与实训体验改造 v2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现学习页输入框间距、继续按钮携带 taskId、按模态记住任务、专业模式预加载、小助手侧边栏 5 项体验改造。

**Architecture:** 前端改造为主：学习页间距（CSS）、继续按钮（query 传 taskId）、模态记忆（localStorage 按 modal 扩展）、小助手侧边栏（AnnotationCoach 定位改造）。专业模式预加载涉及后端（preload 接口 + status 增强）+ 前端（隐藏 iframe 预载）。设置保留项（问题 2）和标注台全类型对齐 LS（问题 7）为独立待办，不在本计划。

**Tech Stack:** Next.js (React 18), TypeScript, Tailwind, localStorage, Python (FastAPI label_studio_gateway)。

**参考**：设计文档 `docs/superpowers/specs/2026-08-17-learning-training-ux-v2-design.md`。

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `web/app/(workspace)/home/[[...sessionId]]/page.tsx` | 学生首屏间距 | 修改（CSS） |
| `web/components/student-shell/StudentHomeSummary.tsx` | 继续按钮携带 taskId | 修改 |
| `web/app/(workspace)/annotation/page.tsx` | 读 query + 模态记忆 + pro 预加载 | 修改（主要） |
| `deeptutor/api/routers/label_studio_gateway.py` | preload 接口 + status 增强 | 修改 |
| `deeptutor/services/label_studio_gateway/client.py` | ensure_task 幂等支持 | 修改 |
| `web/components/annotation/AnnotationCoach.tsx` | 小助手侧边栏 | 修改 |
| `web/tests/annotation-mode-memory.test.ts` | 模态记忆单测 | 新建 |
| `tests/api/test_label_studio_gateway_preload.py` | preload 接口测试 | 新建 |

---

## Task 1: 学习页输入框间距

**Files:**
- Modify: `web/app/(workspace)/home/[[...sessionId]]/page.tsx`

- [ ] **Step 1: 定位学生首屏容器**

读 `web/app/(workspace)/home/[[...sessionId]]/page.tsx` 第 1627 行附近：
```tsx
className={`flex w-full flex-1 min-h-0 justify-center animate-fade-in px-6 ${studentMode ? "items-center overflow-y-auto py-8" : "items-end pb-14"}`}
```

- [ ] **Step 2: 增大摘要区与输入框间距**

学生模式容器 padding 从 `py-8` 改为 `py-12`（顶部留 48px，底部 48px 给输入框呼吸空间）：

```tsx
${studentMode ? "items-center overflow-y-auto py-12" : "items-end pb-14"}
```

- [ ] **Step 3: 验证 + commit**

Run: `cd web && npx tsc --noEmit`
Expected: PASS

```bash
git add "web/app/(workspace)/home/[[...sessionId]]/page.tsx"
git commit -m "fix: 学生首屏摘要区与输入框间距调大"
```

---

## Task 2: 继续按钮携带 taskId

**Files:**
- Modify: `web/components/student-shell/StudentHomeSummary.tsx`
- Modify: `web/app/(workspace)/annotation/page.tsx`

- [ ] **Step 1: 修改 continueLearning 携带 task_id**

`web/components/student-shell/StudentHomeSummary.tsx` 第 40-50 行改为：

```tsx
const continueLearning = () => {
  if (task?.mode === "teaching_annotation" && task.task_id) {
    router.push(`/annotation?task=${encodeURIComponent(task.task_id)}&mode=teaching`);
    return;
  }
  if (task?.mode === "professional_annotation" && task.task_id) {
    router.push(`/annotation?task=${encodeURIComponent(task.task_id)}&mode=professional`);
    return;
  }
  onStartChat();
};
```

`task.task_id` 字段确认存在（`CurrentLearningTask` 类型 `task_id: string`）。

- [ ] **Step 2: annotation 页读取 query**

`web/app/(workspace)/annotation/page.tsx`：
1. import `useSearchParams` from "next/navigation"。
2. 组件内：
```tsx
const searchParams = useSearchParams();
const queryTask = searchParams.get("task");
const queryMode = searchParams.get("mode");
```
3. 初始化 mode 从 queryMode 读取（若合法）：
```tsx
const [mode, setMode] = useState<"image" | "text" | "audio" | "video" | "pro">(() => {
  const m = queryMode;
  if (m === "teaching" || m === "professional") return "pro";
  return (m as "image" | "text" | "audio" | "video" | undefined) && ["image", "text", "audio", "video"].includes(m as string) ? (m as "image" | "text" | "audio" | "video") : "image";
});
```
注意：`?mode=teaching` 表示教学模式（对应 pro 以外的模态），`?mode=professional` 表示专业模式（对应 pro）。这里语义需谨慎——看现有 `chooseTask` 用 `"teaching"` 编辑模式、`chooseProfessionalTask` 用 `"professional"`。设计上：`?mode=teaching` → 教学模式（非 pro，需要任务），`?mode=professional` → 专业模式（pro）。

4. 新增 useEffect 处理 queryTask（在 tasks 加载后）：
```tsx
useEffect(() => {
  if (!queryTask || tasks.length === 0) return;
  const exists = tasks.some((t) => t.id === queryTask) || professionalTasks.some((t) => t.id === queryTask);
  if (!exists) return;
  if (queryMode === "professional") {
    void chooseProfessionalTask(queryTask);
  } else {
    void chooseTask(queryTask);
  }
  // 清除 query，避免刷新重复触发（history.replaceState）
  window.history.replaceState({}, "", "/annotation");
}, [queryTask, queryMode, tasks, professionalTasks]);
```
注意：chooseTask/chooseProfessionalTask 是 useCallback/普通函数，依赖需处理（用 ref 或包含在 deps）。chooseProfessionalTask 是普通 async 函数（非 useCallback），直接引用即可。

- [ ] **Step 3: 验证 + commit**

Run: `cd web && npx tsc --noEmit`
Expected: PASS

```bash
git add web/components/student-shell/StudentHomeSummary.tsx "web/app/(workspace)/annotation/page.tsx"
git commit -m "feat: 继续按钮携带 taskId 跳转对应任务"
```

---

## Task 3: 按模态记住任务

**Files:**
- Modify: `web/app/(workspace)/annotation/page.tsx`
- Create: `web/tests/annotation-mode-memory.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
// web/tests/annotation-mode-memory.test.ts
import assert from "node:assert/strict";
import { test, beforeEach, afterEach } from "node:test";
import {
  lastTaskKeyFor,
  readLastTaskFor,
  writeLastTaskFor,
  type AnnotationModeKey,
} from "../lib/annotation-mode-memory";

const PROFILE = "lp_test123";

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

test("lastTaskKeyFor 含 modal 后缀", () => {
  assert.equal(lastTaskKeyFor(PROFILE, "image"), "deeptutor_last_annotation_task.lp_test123.image");
  assert.equal(lastTaskKeyFor(PROFILE, "video"), "deeptutor_last_annotation_task.lp_test123.video");
});

test("write/read roundtrip", () => {
  writeLastTaskFor(PROFILE, "text", "task5");
  assert.equal(readLastTaskFor(PROFILE, "text"), "task5");
});

test("不同 modal 独立", () => {
  writeLastTaskFor(PROFILE, "image", "task1");
  writeLastTaskFor(PROFILE, "video", "task15");
  assert.equal(readLastTaskFor(PROFILE, "image"), "task1");
  assert.equal(readLastTaskFor(PROFILE, "video"), "task15");
  assert.equal(readLastTaskFor(PROFILE, "audio"), null);
});

test("无 profile 退化全局键", () => {
  assert.equal(lastTaskKeyFor("", "image"), "deeptutor_last_annotation_task.image");
});
```

- [ ] **Step 2: 写实现**

创建 `web/lib/annotation-mode-memory.ts`：

```ts
"use client";

export type AnnotationModeKey = "image" | "text" | "audio" | "video";

const KEY_PREFIX = "deeptutor_last_annotation_task";

export function lastTaskKeyFor(profileId: string, modal: AnnotationModeKey): string {
  return profileId ? `${KEY_PREFIX}.${profileId}.${modal}` : `${KEY_PREFIX}.${modal}`;
}

export function readLastTaskFor(profileId: string, modal: AnnotationModeKey): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(lastTaskKeyFor(profileId, modal));
  } catch {
    return null;
  }
}

export function writeLastTaskFor(profileId: string, modal: AnnotationModeKey, taskId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(lastTaskKeyFor(profileId, modal), taskId);
  } catch {
    /* ignore quota/security errors */
  }
}
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd web && npx tsx --test tests/annotation-mode-memory.test.ts`
Expected: PASS（4 项）。若 tsx 不可用，用 `npm run test:node`（遵循仓库现有测试方式，参考 web/tests/view-identity.test.ts）。

- [ ] **Step 4: annotation 页改用模态记忆**

`web/app/(workspace)/annotation/page.tsx`：
1. import `{ readLastTaskFor, writeLastTaskFor, type AnnotationModeKey }`。
2. 替换现有 `lastTaskKey` 常量，改为函数式读取：
```tsx
const lastTaskKey = profileId ? `deeptutor_last_annotation_task.${profileId}` : "deeptutor_last_annotation_task"; // 保留旧键兼容
```
3. `chooseTask` 成功后写入按模态键：
```tsx
try {
  writeLastTaskFor(profileId || "", task.modal as AnnotationModeKey, taskId);
} catch { /* ignore */ }
```
4. 恢复逻辑（restoredTaskRef）改为优先读 URL queryTask；无 queryTask 时读当前模态记忆：
```tsx
useEffect(() => {
  if (tasks.length === 0 || restoredTaskRef.current) return;
  restoredTaskRef.current = true;
  const saved = readLastTaskFor(profileId || "", mode as AnnotationModeKey) ?? localStorage.getItem(lastTaskKey);
  if (!saved) return;
  const exists = tasks.some((t) => t.id === saved);
  if (exists) void chooseTask(saved);
}, [tasks, chooseTask, mode, profileId]);
```
5. `switchMode` 中：切到目标模态时，读目标模态记忆并自动 chooseTask：
```tsx
// 在 setMode(nextMode) 之后，若 nextMode 非 pro 且有记忆任务：
const nextKey = readLastTaskFor(profileId || "", nextMode as AnnotationModeKey);
if (nextKey) {
  const exists = tasks.some((t) => t.id === nextKey);
  if (exists) void chooseTask(nextKey);
}
```
（放在 `setMode` 之后、空态清空逻辑附近。注意不要与空态清空冲突——只有没有兼容任务时才走空态。）

- [ ] **Step 5: 验证 + commit**

Run: `cd web && npm run test:node && npx tsc --noEmit`
Expected: PASS（含新增 4 项）

```bash
git add web/lib/annotation-mode-memory.ts web/tests/annotation-mode-memory.test.ts "web/app/(workspace)/annotation/page.tsx"
git commit -m "feat: 按模态记住标注任务并自动恢复"
```

---

## Task 4: 专业模式预加载（后端）

**Files:**
- Modify: `deeptutor/api/routers/label_studio_gateway.py`
- Modify: `deeptutor/services/label_studio_gateway/client.py`
- Create: `tests/api/test_label_studio_gateway_preload.py`

- [ ] **Step 1: 确认现有 prepare/status 流程**

读 `deeptutor/api/routers/label_studio_gateway.py`（prepare 端点、status 端点）、`deeptutor/services/label_studio_gateway/client.py`（ensure_task、LabelStudioClient）、`identity_map.py`（assigned 方法）。

- [ ] **Step 2: 写失败测试**

```python
# tests/api/test_label_studio_gateway_preload.py
# 前提：需要 mock LabelStudioClient。参考现有 test_label_studio_gateway 测试的 mock 方式。
# 目标：preload 端点在档案解锁且任务已分配时返回 ready=True，幂等可重复调用。
```

先读现有 `tests/` 下 label_studio_gateway 的测试文件确认 mock 模式，再写测试。核心断言：
1. `POST /api/v1/label-studio/preload`（档案已解锁）→ 200 `{ ready: true, prepared: N, task_urls: {...} }`
2. 重复调用 → 幂等，不重复创建项目
3. 档案未解锁 → 423

- [ ] **Step 3: 实现 preload 端点**

`deeptutor/api/routers/label_studio_gateway.py` 新增：

```python
@router.post("/label-studio/preload")
async def preload_label_studio_tasks(...):
    """为当前档案准备所有已分配专业任务（幂等）。"""
    context = _context(write=True)  # 解锁 + 档案权限校验
    mapping = _identity_mapping()
    assigned = mapping.assigned([])  # 或按权限读取已分配任务
    task_urls: dict[str, str] = {}
    for task_id in assigned:
        task = _task_bank().get(task_id)
        if not task:
            continue
        try:
            url = await _ensure_task_url(mapping, task_id, task, context)  # 复用现有 prepare 逻辑，幂等
            task_urls[task_id] = url
        except Exception:
            continue  # 单个失败不阻塞整体
    return {"ready": len(task_urls) == len(assigned), "prepared": len(task_urls), "task_urls": task_urls}
```

重构：把现有 `prepare` 端点里"ensure_task + 返回 workbench_url"的逻辑抽为 `_ensure_task_url(...)` 辅助函数，preload 与 prepare 都调用它。`ensure_task` 本身需幂等（已创建项目/已导入任务则跳过——确认 client.py 的 ensure_task 是否已如此，若未幂等则在 client 层加幂等检查）。

- [ ] **Step 4: 增强 status 端点**

`/status` 返回当前档案准备状态：
```python
@router.get("/label-studio/status")
async def label_studio_status(...):
    # 现有健康检查基础上，档案已解锁时补充：
    #   ready_count, total_count, prepared_tasks
```

- [ ] **Step 5: 验证 + commit**

Run:
```powershell
python -m pytest tests/api/test_label_studio_gateway_preload.py -q
python -m pytest tests/api/ -k "label_studio or ls_gateway" -q
python -m ruff check deeptutor/api/routers/label_studio_gateway.py deeptutor/services/label_studio_gateway/client.py
```

```bash
git add deeptutor/api/routers/label_studio_gateway.py deeptutor/services/label_studio_gateway/client.py tests/api/test_label_studio_gateway_preload.py
git commit -m "feat: 专业模式 preload 批量准备接口 + status 就绪状态"
```

---

## Task 5: 专业模式预加载（前端）

**Files:**
- Modify: `web/app/(workspace)/annotation/page.tsx`

- [ ] **Step 1: 档案解锁后自动 preload**

在 annotation 页（`profileId` 可用时）：
```tsx
useEffect(() => {
  if (!profileId) return;
  const controller = new AbortController();
  void apiFetch(apiUrl("/api/v1/label-studio/preload"), {
    method: "POST",
    signal: controller.signal,
  }).catch(() => undefined); // fire-and-forget，失败不阻塞
  return () => controller.abort();
}, [profileId]);
```

- [ ] **Step 2: 隐藏 iframe 预载**

`mode !== "pro"` 时，若已解锁且存在 ready URL，渲染隐藏 iframe 预加载 LS 前端：

```tsx
{mode !== "pro" && labelStudio?.available && readyUrls.length > 0 && (
  <iframe
    src={readyUrls[0]}
    className="pointer-events-none fixed -left-[10000px] top-0 h-[600px] w-[1200px] border-0 opacity-0"
    aria-hidden
    tabIndex={-1}
    title="Label Studio 预加载"
  />
)}
```

用 `readyUrls` state 保存 `/status` 返回的 prepared_tasks URL 列表。切到 pro 时主 iframe 直接用 `readyUrls[0]`（已缓存），秒开。

- [ ] **Step 3: 加载反馈优化**

`professionalLoading` 期间：
- 显示阶段提示（从 backend 或前端状态推断：准备项目/导入题目/加载工作台）。
- 加"取消"按钮：设置一个 `cancelProfessional` flag，中断 chooseProfessionalTask。
- 超过 15s 显示重试 + 诊断信息。

```tsx
const [preloadStage, setPreloadStage] = useState("准备 Label Studio 项目…");
const [preloadTimedOut, setPreloadTimedOut] = useState(false);

// chooseProfessionalTask 内：
setProfessionalLoading(true);
setPreloadStage("准备 Label Studio 项目…");
setPreloadTimedOut(false);
const timeoutTimer = setTimeout(() => setPreloadTimedOut(true), 15000);
// ... prepare 成功后 clearTimeout(timeoutTimer)
```

- [ ] **Step 4: 验证 + commit**

Run: `cd web && npx tsc --noEmit`
Expected: PASS

```bash
git add "web/app/(workspace)/annotation/page.tsx"
git commit -m "feat: 专业模式解锁后预加载 + 加载阶段反馈"
```

---

## Task 6: 标注小助手侧边栏

**Files:**
- Modify: `web/components/annotation/AnnotationCoach.tsx`

- [ ] **Step 1: 读取当前容器结构**

读 `web/components/annotation/AnnotationCoach.tsx` 第 640-830 行（容器 + 面板）。当前：
- 外层 `fixed z-50 flex flex-col items-end gap-3`，`right/bottom` 定位。
- 展开面板 `sm:static sm:h-[440px] sm:w-[340px]`。

- [ ] **Step 2: 新增"放大为侧边栏"状态**

添加 state `expanded`（boolean）：
```tsx
const [expanded, setExpanded] = useState(false);
```

面板头部加"放大"按钮（ChevronsRight 图标），点击 `setExpanded(true)`；侧边栏模式头部加"收起"按钮，点击 `setExpanded(false)`。

- [ ] **Step 3: 侧边栏布局**

当 `expanded && !isMobile` 时，容器改为右侧全高侧边栏：

```tsx
<div
  className={`fixed z-50 ${expanded ? "inset-y-0 right-0 w-[360px]" : "flex flex-col items-end gap-3"}`}
  style={expanded ? undefined : { right: position.right, bottom: position.bottom }}
>
  {/* expanded: 面板占满高度，隐藏小气泡 */}
  {expanded ? (
    <div className="flex h-full w-full flex-col border-l border-[var(--border)] bg-[var(--card)] shadow-xl">
      {/* 头部：标题 + 收起按钮 */}
      {/* 消息区 flex-1 overflow-y-auto */}
      {/* 快捷语 + 输入框 */}
    </div>
  ) : (
    /* 现有小气泡 + 340x440 面板 */
  )}
</div>
```

用 CSS transition（`transition-transform` 或 `animate-slide-in-right`）实现滑入动画。移动端保持现有全宽底部弹层（`sm:` 断点逻辑）。

- [ ] **Step 4: 处理 z 叠放**

与 `BboxObjectList` 窄屏浮动抽屉（`fixed bottom-4 right-4 z-40`）冲突：侧边栏 z-50 会盖住。检查是否可接受（侧边栏展开时对象列表被盖，可接受），或在 AnnotationCoach 侧边栏态时给对象列表更高 z。设计上可接受——用户展开小助手时优先看助手。

- [ ] **Step 5: 拖动逻辑**

`expanded` 时禁用位置拖动（`onPointerDown` 不生效）。代码：
```tsx
onPointerDown={expanded ? undefined : handlePointerDown}
```

- [ ] **Step 6: 验证 + commit**

Run: `cd web && npx tsc --noEmit && npm run test:node`
Expected: PASS

```bash
git add web/components/annotation/AnnotationCoach.tsx
git commit -m "feat: 标注小助手可放大右侧侧边栏"
```

---

## Task 7: 整体验证

**Files:** 无新增

- [ ] **Step 1: 前端全量检查**

```powershell
cd web
npx tsc --noEmit
npx eslint <本次修改的 TS/TSX 文件> --quiet
npm run test:node
npm run build
```

- [ ] **Step 2: 后端检查**

```powershell
python -m ruff check deeptutor/api/routers/label_studio_gateway.py deeptutor/services/label_studio_gateway/client.py
python -m pytest tests/api/test_label_studio_gateway_preload.py -q
python -m pytest tests/api/ -k "label_studio or ls_gateway" -q
```

- [ ] **Step 3: 浏览器冒烟**

覆盖：
1. 学生首屏：摘要区与输入框间距明显增大
2. 学习页点"继续"→ 跳转 annotation 并直接打开对应任务（不再显示空态）
3. 实训页：切到视频模态 → 自动恢复上次视频任务（若无则空态）
4. 专业模式：档案解锁后自动 preload，点进 pro 秒开（隐藏 iframe 已缓存）
5. 小助手：点放大按钮 → 右侧滑出侧边栏；收起回小面板
6. 控制台无 `Canvas is already in use`

- [ ] **Step 4: 汇总提交**

若冒烟发现小问题，逐个修复提交。全部通过后向用户汇报。

---

## 自审清单

- [ ] 覆盖设计 3.1（间距）→ Task 1
- [ ] 覆盖设计 3.2（继续 taskId）→ Task 2
- [ ] 覆盖设计 3.3（模态记忆）→ Task 3
- [ ] 覆盖设计 3.4（专业模式预加载）→ Task 4+5
- [ ] 覆盖设计 3.6（小助手侧边栏）→ Task 6
- [ ] 设计 3.5（标注台对齐 LS）→ 单独专项（明确不在本计划）
- [ ] 问题 2（设置保留项）→ 待办（明确不在本计划）
- [ ] 无 TBD/占位符
- [ ] 类型一致（AnnotationModeKey / readLastTaskFor / writeLastTaskFor / expanded）
