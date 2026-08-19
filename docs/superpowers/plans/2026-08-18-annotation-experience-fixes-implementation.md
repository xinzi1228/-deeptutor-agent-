# 标注体验修复与档案隔离实施计划（7 项）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 7 项标注体验 bug：档案隔离、专业模式联动、任务自动保存/恢复、对象列表折叠、教练实时状态、身份引导、实践题筛选。

**Architecture:** 前端为主（专业模式联动、自动保存、对象列表折叠、教练共享状态、身份引导、实践题筛选前端过滤）+ 后端小改（migration 仅首次迁移、/tasks practice_only 过滤）。

**Tech Stack:** Next.js (React 18), TypeScript, FastAPI, localStorage, React Context。

**参考**：设计文档 `docs/superpowers/specs/2026-08-18-annotation-experience-fixes-design.md`。

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `deeptutor/api/routers/learning_profiles.py` | 首次迁移判断 | 修改 |
| `deeptutor/services/learning_profiles/migration.py` | 迁移标记（已有 marker 机制，补充逻辑） | 修改 |
| `deeptutor/api/routers/annotation.py` | /tasks practice_only 过滤 | 修改 |
| `web/app/(workspace)/annotation/page.tsx` | pro 联动 + 自动保存 + 模态记忆 + 实践题筛选 | 修改（主要） |
| `web/lib/annotation-mode-memory.ts` | 最后模态键 | 修改 |
| `web/components/annotation/UnifiedAnnotationWorkbench.tsx` | 对象列表折叠 + liveState 上报 | 修改 |
| `web/components/annotation/AnnotationLiveStateContext.tsx` | 教练实时状态共享 store | 新建 |
| `web/components/annotation/AnnotationCoach.tsx` | 订阅 liveState | 修改 |
| `web/app/(workspace)/page.tsx` | 首次访问引导 /login | 修改 |
| `web/lib/view-identity.ts` | hasChosenIdentity | 修改 |
| `web/tests/annotation-mode-memory.test.ts` | 最后模态测试 | 修改 |
| `tests/api/test_learning_profiles.py` | 首次迁移测试 | 修改 |
| `tests/api/test_annotation_tasks.py` | practice_only 测试 | 新建 |

---

## Task 1: 档案隔离（仅首次迁移）

**Files:**
- Modify: `deeptutor/api/routers/learning_profiles.py:80-91`
- Modify: `deeptutor/services/learning_profiles/migration.py`
- Modify: `tests/api/test_learning_profiles.py`

- [ ] **Step 1: 写失败测试**

在 `tests/api/test_learning_profiles.py` 追加（先读现有测试的 setup/mock 模式）：
```python
def test_second_profile_does_not_migrate_legacy_data(client, ...):
    """第二个档案创建后不复制账号级旧库，保持空白。"""
    # 创建第一个档案 → 迁移账号级旧库
    # 创建第二个档案 → 不迁移（无 legacy_migration 复制）
    # 断言第二个档案的 sessions/chat_history.db 不存在或为空
```

- [ ] **Step 2: 修改 create_profile 仅首次迁移**

`deeptutor/api/routers/learning_profiles.py`：
```python
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_profile(body, _=Depends(require_auth)):
    store, _ = _stores()
    user = get_current_user()
    try:
        profile = store.create(user.id, body.name, body.pin, body.avatar)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # 仅当该账号还没有任何档案（第一个档案）时迁移账号级旧数据
    existing = store.list(user.id)
    if len(existing) == 1:  # 刚创建的这个
        from deeptutor.services.learning_profiles.migration import LearningProfileMigrator
        migration = LearningProfileMigrator(store.root.parent).migrate(profile.id)
        migration_status = migration["status"]
    else:
        migration_status = "skipped_not_first_profile"
    _audit(store, "profile_created", profile.id, metadata={"migration_status": migration_status})
    return {**profile.public_dict(), "legacy_migration": {"status": migration_status, "source_preserved": True}}
```

- [ ] **Step 3: migration.py 补充说明（可选）**

`migration.py` 已有 marker 机制（幂等）。不改核心逻辑，仅确认 marker 已防止重复迁移。若测试发现首次创建 B（第二个档案）仍复制，检查是否 store.list 时机问题（create 后 list 含新档案）。

- [ ] **Step 4: 验证 + Commit**

```powershell
python -m pytest tests/api/test_learning_profiles.py -q
python -m ruff check deeptutor/api/routers/learning_profiles.py
```

```bash
git add deeptutor/api/routers/learning_profiles.py tests/api/test_learning_profiles.py
git commit -m "fix: 新档案仅首次迁移账号级旧数据"
```

---

## Task 2: 实践题筛选

**Files:**
- Modify: `deeptutor/api/routers/annotation.py`（/tasks）
- Create: `tests/api/test_annotation_tasks.py`

- [ ] **Step 1: 读 /tasks 现状**

读 `deeptutor/api/routers/annotation.py` 的 `/tasks` 端点（约 531-544 行），确认参数解析方式和 task_bank 结构。

- [ ] **Step 2: 写失败测试**

```python
# tests/api/test_annotation_tasks.py
def test_tasks_practice_only_filters_theory():
    """practice_only=true 只返回实践操作题，排除 classification/judgment/standard/error_case。"""
    resp = client.get("/api/v1/annotation/tasks?practice_only=true")
    assert resp.status_code == 200
    types = {t["type"] for t in resp.json()["tasks"]}
    assert types <= {"bbox", "audio_event", "audio_transcription", "video_event", "video_tracking", "ner"}
    assert "classification" not in types

def test_tasks_default_returns_all():
    """不带 practice_only 返回全部题目（兼容）。"""
    resp = client.get("/api/v1/annotation/tasks")
    assert resp.status_code == 200
```

- [ ] **Step 3: 实现过滤**

`annotation.py` /tasks 加 query 参数：
```python
PRACTICE_TYPES = {"bbox", "audio_event", "audio_transcription", "video_event", "video_tracking", "ner"}

@router.get("/tasks")
async def list_tasks(practice_only: bool = False):
    from deeptutor.api.routers.annotation import _task_bank  # 若已在同文件直接引用
    tasks = []
    for task_id, task in _task_bank().items():
        t = task.get("type", "bbox")
        if practice_only and t not in PRACTICE_TYPES:
            continue
        tasks.append({... 现有字段 ...})
    return {"tasks": tasks}
```

- [ ] **Step 4: 验证 + Commit**

```powershell
python -m pytest tests/api/test_annotation_tasks.py -q
python -m ruff check deeptutor/api/routers/annotation.py
```

```bash
git add deeptutor/api/routers/annotation.py tests/api/test_annotation_tasks.py
git commit -m "feat: 标注台任务接口支持 practice_only 过滤实践题"
```

---

## Task 3: 专业模式 preload 联动

**Files:**
- Modify: `web/app/(workspace)/annotation/page.tsx`

- [ ] **Step 1: preload 成功更新 state**

当前 preload effect（约 204-213 行）fire-and-forget。改为：
```tsx
useEffect(() => {
  if (!profileId) return;
  let cancelled = false;
  const controller = new AbortController();
  const run = (attempt: number) => {
    apiFetch(apiUrl("/api/v1/label-studio/preload"), {
      method: "POST", signal: controller.signal,
    }).then((res) => {
      if (cancelled) return;
      if (res.ok) return res.json();
      throw new Error("preload failed");
    }).then((data) => {
      if (cancelled) return;
      setLabelStudio((current) => ({ ...(current || {}), ready: data?.ready, prepared_count: data?.prepared, task_urls: data?.task_urls }));
    }).catch(() => {
      // 失败重试 1 次（2s 后），cancelled 时跳过
      if (attempt < 1 && !cancelled) setTimeout(() => run(attempt + 1), 2000);
    });
  };
  run(0);
  return () => { cancelled = true; controller.abort(); };
}, [profileId]);
```

- [ ] **Step 2: 未解锁引导**

pro 面板渲染（约 519-523 行）——当前 `labelStudio?.available` false 时显示"尚未就绪"。改为区分：
```tsx
: !labelStudio?.available && labelStudio?.detail?.includes("解锁") ? (
  <div>请先在左侧解锁学习档案，专业模式需要档案已解锁。</div>
) : <div>Label Studio 专业模式尚未就绪... 检测信息：{labelStudio?.detail}</div>
```

- [ ] **Step 3: 验证 + Commit**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

```bash
git add "web/app/(workspace)/annotation/page.tsx"
git commit -m "feat: 专业模式 preload 联动状态 + 未解锁引导"
```

---

## Task 4: 最后模态记忆 + 自动保存

**Files:**
- Modify: `web/lib/annotation-mode-memory.ts`
- Modify: `web/tests/annotation-mode-memory.test.ts`
- Modify: `web/app/(workspace)/annotation/page.tsx`

- [ ] **Step 1: 写失败测试**

`web/tests/annotation-mode-memory.test.ts` 追加：
```ts
import { readLastModeFor, writeLastModeFor } from "../lib/annotation-mode-memory";

test("last mode 读写", () => {
  writeLastModeFor("lp_test", "video");
  assert.equal(readLastModeFor("lp_test"), "video");
  assert.equal(readLastModeFor(""), null);
});
```

- [ ] **Step 2: 实现最后模态键**

`annotation-mode-memory.ts` 加：
```ts
const MODE_KEY_PREFIX = "deeptutor_last_annotation_mode";

export function lastModeKeyFor(profileId: string): string {
  return profileId ? `${MODE_KEY_PREFIX}.${profileId}` : MODE_KEY_PREFIX;
}

export function readLastModeFor(profileId: string): "image" | "text" | "audio" | "video" | "pro" | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(lastModeKeyFor(profileId));
    return ["image", "text", "audio", "video", "pro"].includes(raw as string) ? raw as any : null;
  } catch { return null; }
}

export function writeLastModeFor(profileId: string, mode: string): void {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(lastModeKeyFor(profileId), mode); } catch { }
}
```

- [ ] **Step 3: annotation 页接入**

1. 初始 mode 从 `readLastModeFor` 读取（query mode > 最后模态 > image）：
```tsx
const [mode, setMode] = useState<...>(() => {
  const m = queryMode;
  if (m === "professional") return "pro";
  if (m && ["image", "text", "audio", "video"].includes(m)) return m;
  return readLastModeFor(profileId || "") ?? "image";
});
```
注意 profileId 初始化时可能未就绪（active 异步）——用 effect 在 profileId 就绪后修正，或用 localStorage 全局键兜底。

2. `switchMode` 时写 `writeLastModeFor(profileId, nextMode)`。

3. 恢复逻辑：restore effect 读 `readLastTaskFor(profileId, mode)`（mode 现在是最后模态）。

4. **自动保存**：切任务/切模态/路由离开时强制 flush 草稿：
```tsx
// beforeunload
useEffect(() => {
  const onUnload = () => { void saveOwnedCheckpoint(); };
  window.addEventListener("beforeunload", onUnload);
  return () => window.removeEventListener("beforeunload", onUnload);
}, [saveOwnedCheckpoint]);
```
`saveOwnedCheckpoint` 已有（保存草稿 + checkpoint）。

5. **pro 模式记忆**：`chooseProfessionalTask` 成功后：
```tsx
writeLastTaskFor(profileId || "", "pro" as any, taskId);
writeLastModeFor(profileId || "", "pro");
```
注意 `AnnotationModeKey` 不含 "pro"——扩展类型或单独处理。

- [ ] **Step 4: 验证 + Commit**

Run: `cd web && npm run test:node` + `npx tsc --noEmit`
Expected: PASS

```bash
git add web/lib/annotation-mode-memory.ts web/tests/annotation-mode-memory.test.ts "web/app/(workspace)/annotation/page.tsx"
git commit -m "feat: 记住最后模态 + 切页自动保存 + pro 任务记忆"
```

---

## Task 5: 首次访问引导登录

**Files:**
- Modify: `web/lib/view-identity.ts`
- Modify: `web/app/(workspace)/page.tsx`

- [ ] **Step 1: view-identity 加 hasChosenIdentity**

```ts
export function hasChosenIdentity(): boolean {
  if (typeof window === "undefined") return false;
  try { return window.localStorage.getItem(VIEW_IDENTITY_KEY) !== null; } catch { return false; }
}
```

- [ ] **Step 2: / 根页引导**

`web/app/(workspace)/page.tsx`（当前 `router.replace("/home")`）改为：
```tsx
useEffect(() => {
  // AUTH 关闭且首次访问（未选身份）→ 引导 /login 选身份
  if (!hasChosenIdentity()) {
    router.replace("/login");
    return;
  }
  router.replace(sessionId ? `/home/${sessionId}` : "/home");
}, [router, sessionId]);
```
注意：`/login` 页在 AUTH 关闭时显示身份选择；用户选择后 `setViewIdentity` + 跳转。已有身份则直接进对应端。

- [ ] **Step 3: 验证 + Commit**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

```bash
git add web/lib/view-identity.ts "web/app/(workspace)/page.tsx"
git commit -m "feat: 首次访问引导身份选择"
```

---

## Task 6: 对象列表可折叠

**Files:**
- Modify: `web/components/annotation/UnifiedAnnotationWorkbench.tsx`（BBoxEditor）

- [ ] **Step 1: 折叠 state**

BBoxEditor 加：
```tsx
const [objListCollapsed, setObjListCollapsed] = useState(false);
```

- [ ] **Step 2: 中等宽度折叠**

当前布局（约 513 行）：
```tsx
<div className="grid min-w-0 gap-3 lg:grid-cols-[140px_minmax(0,1fr)_220px]">
  <div className="hidden lg:block"><BboxLabelPanel/></div>
  <BboxCanvas/>
  <aside className="hidden max-h-[600px] ... lg:block"><BboxObjectList/></aside>
</div>
```

改为中等宽度（lg 区间）对象列表可折叠。方案：用 `hidden xl:block` 保持宽屏常驻 + 中等宽度用折叠按钮：

```tsx
<div className="grid min-w-0 gap-3 lg:grid-cols-[140px_minmax(0,1fr)_minmax(0,220px)] xl:grid-cols-[140px_minmax(0,1fr)_220px]">
  <div className="hidden lg:block"><BboxLabelPanel/></div>
  <BboxCanvas/>
  <aside className={`max-h-[600px] overflow-y-auto rounded-xl border bg-[var(--card)] p-3 ${objListCollapsed ? "hidden" : "hidden lg:block"}`}>
    <div className="flex items-center justify-between">
      <div className="text-[10px] font-semibold uppercase ...">对象列表 · {state.selectedIds.length}</div>
      <button onClick={() => setObjListCollapsed(true)} className="...">收起</button>
    </div>
    <BboxObjectList .../>
  </aside>
  {/* 折叠时显示展开按钮 */}
  {objListCollapsed && (
    <button onClick={() => setObjListCollapsed(false)} className="hidden lg:flex ...">对象列表 ▸</button>
  )}
</div>
```

**简化**：目标是在中等宽度（lg，无 xl）下对象列表不挤压画布。实现：
- 宽屏（xl+）：常驻右侧 220px。
- 中等（lg 但非 xl）：对象列表默认折叠为顶部小按钮，点击展开。
- 窄屏（<lg）：浮动抽屉（已有，不改）。

可用 CSS 媒体查询难以在 React state 里判断——用 `useMediaQuery`（仓库可能有）或简化：`objListCollapsed` 默认 false，但 `hidden xl:block` 控制宽屏常驻；中等宽度通过折叠按钮控制。

**建议最小实现**：把 aside 的 `hidden lg:block` 改为 `hidden xl:block`（中等宽度隐藏），加一个 `xl:hidden lg:block` 的折叠展开按钮（在画布上方或工具栏），点击弹出对象列表为覆盖层。这样中等宽度默认不显示对象列表（不阻挡），用户可点按钮查看。

- [ ] **Step 3: 验证 + Commit**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

```bash
git add "web/components/annotation/UnifiedAnnotationWorkbench.tsx"
git commit -m "feat: 对象列表中等宽度可折叠不阻挡画布"
```

---

## Task 7: 教练实时状态（共享 store）

**Files:**
- Create: `web/components/annotation/AnnotationLiveStateContext.tsx`
- Modify: `web/components/annotation/UnifiedAnnotationWorkbench.tsx`
- Modify: `web/components/annotation/AnnotationCoach.tsx`

- [ ] **Step 1: 新建共享 context**

```tsx
// web/components/annotation/AnnotationLiveStateContext.tsx
"use client";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type AnnotationLiveState = {
  taskId: string;
  annotationCount: number;
  labels: string[];
  selectedObjectId: string;
  currentLabel: string;
  tool: string;
  missingObjects: string[];
};

type Value = {
  liveState: AnnotationLiveState | null;
  updateLiveState: (state: Partial<AnnotationLiveState>) => void;
};

const Context = createContext<Value>({ liveState: null, updateLiveState: () => {} });

export function AnnotationLiveStateProvider({ children }: { children: ReactNode }) {
  const [liveState, setLiveState] = useState<AnnotationLiveState | null>(null);
  const updateLiveState = useCallback((state: Partial<AnnotationLiveState>) => {
    setLiveState((current) => ({ ...(current || { taskId: "", annotationCount: 0, labels: [], selectedObjectId: "", currentLabel: "", tool: "", missingObjects: [] }), ...state }));
  }, []);
  const value = useMemo(() => ({ liveState, updateLiveState }), [liveState]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAnnotationLiveState(): Value {
  return useContext(Context);
}
```

- [ ] **Step 2: Provider 挂载**

`web/app/(workspace)/annotation/page.tsx` 用 `AnnotationLiveStateProvider` 包裹工作台（或在 UnifiedAnnotationWorkbench 内部用）。

- [ ] **Step 3: 工作台上报 liveState**

`UnifiedAnnotationWorkbench.tsx` 的 `onLiveState` 回调（已上报 activity）同时调 `updateLiveState`。在 BBoxEditor 的 onInteractionState（已有上报）或 page 的 reportLiveState 里同步：
```tsx
// page.tsx reportLiveState 里
updateLiveState({
  taskId: String(state.task_id || selectedTask),
  annotationCount: Number(state.annotation_count || 0),
  labels: Array.isArray(state.labels) ? state.labels : [],
  selectedObjectId: String(state.selected_object_id || ""),
  currentLabel: String(state.current_label || ""),
  tool: String(state.tool || ""),
  missingObjects: computeMissing(state),  // 从 ground_truth 推导
});
```

**缺漏推导**：BBoxEditor 已有 `validateBoxes` 和 ground_truth（task.ground_truth）。在 BBoxEditor 里计算：
```ts
const missing = useMemo(() => {
  const gt = (task.ground_truth || []).map((r) => r.label || "object");
  const current = state.boxes.map((b) => b.label);
  return gt.filter((l) => !current.includes(l));  // 简化：标签差集
}, [task, state.boxes]);
```
把 missing 通过 onInteractionState 上报。

- [ ] **Step 4: 教练订阅**

`AnnotationCoach.tsx` 引入 `useAnnotationLiveState()`，在面板显示实时状态（当前任务、已标数、缺漏）：
```tsx
const { liveState } = useAnnotationLiveState();
// 面板头部或状态区显示：
{liveState && <div className="...">当前任务 {liveState.taskId} · 已标 {liveState.annotationCount} 框 · 待标 {liveState.missingObjects.join(", ")}</div>}
```

- [ ] **Step 5: 验证 + Commit**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

```bash
git add web/components/annotation/AnnotationLiveStateContext.tsx web/components/annotation/UnifiedAnnotationWorkbench.tsx web/components/annotation/AnnotationCoach.tsx "web/app/(workspace)/annotation/page.tsx"
git commit -m "feat: 标注教练实时获取标注状态 (共享 store + 缺漏推导)"
```

---

## Task 8: 整体验证

**Files:** 无新增

- [ ] **Step 1: 全量前端检查**

```powershell
cd web
npx tsc --noEmit
npx eslint <本次修改文件> --quiet
npm run test:node
npm run build
```

- [ ] **Step 2: 后端检查**

```powershell
python -m ruff check deeptutor/api/routers/learning_profiles.py deeptutor/api/routers/annotation.py
python -m pytest tests/api/test_learning_profiles.py tests/api/test_annotation_tasks.py -q
```

- [ ] **Step 3: 浏览器冒烟**

覆盖：
1. 创建新档案 → 无旧对话
2. pro 模式解锁后可用（preload 联动 + 引导文案）
3. 切页后恢复任务（最后模态 + 任务记忆 + 自动保存）
4. 中等宽度对象列表折叠
5. 教练面板显示实时状态（任务/框数/缺漏）
6. 首次访问（清 localStorage）→ /login 选身份
7. 标注台无理论题（classification 等不出现）

- [ ] **Step 4: 汇总提交**

---

## 自审清单

- [ ] 覆盖设计 3.1（档案隔离）→ Task 1
- [ ] 覆盖设计 3.2（专业模式联动）→ Task 3
- [ ] 覆盖设计 3.3（自动保存+模态记忆）→ Task 4
- [ ] 覆盖设计 3.4（对象列表折叠）→ Task 6
- [ ] 覆盖设计 3.5（教练实时）→ Task 7
- [ ] 覆盖设计 3.6（首次引导）→ Task 5
- [ ] 覆盖设计 3.7（实践题筛选）→ Task 2
- [ ] 无 TBD/占位符
- [ ] 类型一致（readLastModeFor/writeLastModeFor/hasChosenIdentity/liveState/AnnotationLiveState）
