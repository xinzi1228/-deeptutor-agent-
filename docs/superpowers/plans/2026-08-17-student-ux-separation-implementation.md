# 学生端易用性改造实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现学生端与教师/管理员端分离（AUTH 关闭时身份视图切换）、设置页学生简化、标注台任务记忆与布局优化、文件解析子 Agent。

**Architecture:** 新增前端 `view-identity` 模块统一"当前身份"（student/staff），AUTH 关闭时由 localStorage 决定、AUTH 开启时回退到现有 admin 判断。所有 `studentMode` 计算点（3 处 sidebar + home + SettingsHub + StudentRouteGate）统一改用 `useViewIdentity()`。标注台任务记忆用 localStorage 按档案键存储。文件子 Agent 复用现有 `DelegateExpertTool` 新增 file-analyst 专家卡。

**Tech Stack:** Next.js (React 18), TypeScript, Tailwind, localStorage, 现有 delegate 系统 (Python)。

**参考**：设计文档 `docs/superpowers/specs/2026-08-17-student-ux-separation-design.md`。

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `web/lib/view-identity.ts` | 身份视图核心：类型 + localStorage 读写 + hook | 新建 |
| `web/tests/view-identity.test.ts` | view-identity 单测 | 新建 |
| `web/components/sidebar/WorkspaceSidebar.tsx:32` | studentMode 计算 | 修改 |
| `web/components/sidebar/UtilitySidebar.tsx:25` | studentMode 计算 | 修改 |
| `web/app/(workspace)/home/[[...sessionId]]/page.tsx:235` | studentMode 计算 | 修改 |
| `web/components/settings/SettingsHub.tsx:45` | studentMode 计算 | 修改 |
| `web/components/access/StudentRouteGate.tsx:15` | 学生路由白名单判断 | 修改 |
| `web/lib/student-experience.ts` | STUDENT_ALLOWED_ROUTES（可能扩展） | 修改 |
| `web/app/(auth)/login/page.tsx` | AUTH 关闭时显示身份选择 | 修改 |
| `web/app/(auth)/register/page.tsx` | 首个用户注册流程兼容 | 修改（可选） |
| `web/components/settings/SettingsHub.tsx` | 学生隐藏状态面板/迁移横幅 | 修改 |
| `web/app/(workspace)/annotation/page.tsx` | 任务记忆 | 修改 |
| `web/components/annotation/UnifiedAnnotationWorkbench.tsx:345-351,435-441` | 视频/对象列表布局 | 修改 |
| `deeptutor/tools/delegate_expert_tool.py` | 新增 file-analyst 白名单 | 修改 |
| `deeptutor/skills/builtin/annotation-coach-flows/references/experts/file-analyst.md` | 新专家卡 | 新建 |
| `deeptutor/tools/builtin/__init__.py` | 若需注册（通常不需要，专家卡为配置） | 检查 |

---

## Task 1: view-identity 模块

**Files:**
- Create: `web/lib/view-identity.ts`
- Test: `web/tests/view-identity.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
// web/tests/view-identity.test.ts
import assert from "node:assert/strict";
import { test, beforeEach, afterEach } from "node:test";
import { getViewIdentity, setViewIdentity, isStudentView, type ViewIdentity } from "../lib/view-identity";

const KEY = "deeptutor_view_identity";

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

test("默认身份为学生（AUTH 关闭场景）", () => {
  assert.equal(getViewIdentity(), "student");
});

test("setViewIdentity 持久化", () => {
  setViewIdentity("staff");
  assert.equal(localStorage.getItem(KEY), "staff");
  assert.equal(getViewIdentity(), "staff");
});

test("isStudentView 正确判断", () => {
  assert.equal(isStudentView("student"), true);
  assert.equal(isStudentView("staff"), false);
});

test("非法值回退到学生", () => {
  localStorage.setItem(KEY, "banana");
  assert.equal(getViewIdentity(), "student");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd web && npx tsx --test tests/view-identity.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```ts
// web/lib/view-identity.ts
"use client";

export type ViewIdentity = "student" | "staff";

const VIEW_IDENTITY_KEY = "deeptutor_view_identity";
const VALID: readonly ViewIdentity[] = ["student", "staff"];

/**
 * 当前界面身份（前端视图层）。
 *
 * - AUTH 关闭时：由 localStorage 决定，默认学生（登录页可选）。
 * - AUTH 开启时：调用方应传入真实角色决定（本模块不读 auth，保持职责单一）。
 *
 * 注意：这只是演示/本地单机的视图身份，不替代后端 deeptutor/services/authorization/policy.py。
 */
export function getViewIdentity(): ViewIdentity {
  if (typeof window === "undefined") return "student";
  const raw = window.localStorage.getItem(VIEW_IDENTITY_KEY);
  return VALID.includes(raw as ViewIdentity) ? (raw as ViewIdentity) : "student";
}

export function setViewIdentity(identity: ViewIdentity): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(VIEW_IDENTITY_KEY, identity);
}

export function isStudentView(identity: ViewIdentity): boolean {
  return identity === "student";
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd web && npx tsx --test tests/view-identity.test.ts`
Expected: PASS（4 项）

- [ ] **Step 5: Commit**

```bash
git add web/lib/view-identity.ts web/tests/view-identity.test.ts
git commit -m "feat: 新增 view-identity 前端身份视图模块"
```

---

## Task 2: useViewIdentity hook（统一 studentMode 来源）

**Files:**
- Modify: `web/lib/view-identity.ts`
- Test: `web/tests/view-identity.test.ts`

- [ ] **Step 1: 扩展 view-identity.ts 增加 hook**

在 `web/lib/view-identity.ts` 末尾追加：

```ts
import { useEffect, useState } from "react";

/**
 * 返回当前界面身份。AUTH 关闭时由 localStorage 驱动（可响应变更），
 * AUTH 开启时由调用方传入的 authEnabled/isAdmin 决定。
 */
export function useViewIdentity(options?: {
  authEnabled?: boolean;
  isAdmin?: boolean;
}): { identity: ViewIdentity; studentMode: boolean } {
  const [identity, setIdentity] = useState<ViewIdentity>(() =>
    getViewIdentity(),
  );

  useEffect(() => {
    if (options?.authEnabled === true) {
      // AUTH 开启：由真实角色决定（admin → staff，否则 student）。
      setIdentity(options.isAdmin ? "staff" : "student");
      return;
    }
    // AUTH 关闭：监听 localStorage（如登录页写入后）。
    setIdentity(getViewIdentity());
    const onStorage = () => setIdentity(getViewIdentity());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [options?.authEnabled, options?.isAdmin]);

  return { identity, studentMode: identity === "student" };
}
```

注意：`"use client"` 已置于文件顶部；`import` 必须放文件顶部（ESM 规范），将 `import { useEffect, useState } from "react"` 移到文件第一行 import 区。

- [ ] **Step 2: 增加 hook 测试**

```ts
// 追加到 web/tests/view-identity.test.ts
test("useViewIdentity: AUTH 关闭时默认学生", () => {
  const { studentMode } = useViewIdentity({ authEnabled: false });
  assert.equal(studentMode, true);
});

test("useViewIdentity: AUTH 开启时按角色", () => {
  const staff = useViewIdentity({ authEnabled: true, isAdmin: true });
  assert.equal(staff.studentMode, false);
  const student = useViewIdentity({ authEnabled: true, isAdmin: false });
  assert.equal(student.studentMode, true);
});
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd web && npx tsx --test tests/view-identity.test.ts`
Expected: PASS（6 项）

- [ ] **Step 4: Commit**

```bash
git add web/lib/view-identity.ts web/tests/view-identity.test.ts
git commit -m "feat: useViewIdentity hook 统一 studentMode 来源"
```

---

## Task 3: 替换 3 处 studentMode 计算

**Files:**
- Modify: `web/components/sidebar/WorkspaceSidebar.tsx:32`
- Modify: `web/components/sidebar/UtilitySidebar.tsx:25`
- Modify: `web/app/(workspace)/home/[[...sessionId]]/page.tsx:235`

- [ ] **Step 1: WorkspaceSidebar**

当前第 32 行：`const studentMode = auth.loading || (auth.enabled && !auth.isAdmin);`

改为：
```tsx
const { studentMode } = useViewIdentity({
  authEnabled: auth.enabled,
  isAdmin: auth.isAdmin,
});
```
并在 import 区加 `import { useViewIdentity } from "@/lib/view-identity";`。保留 `auth`（footer/其他仍用）。

- [ ] **Step 2: UtilitySidebar**

当前第 25 行同样替换，加 import。保留 `auth` 变量（可能用于其他渲染）。

- [ ] **Step 3: home/page.tsx**

当前第 235 行：`const studentMode = auth.loading || (auth.enabled && !auth.isAdmin);`

替换为：
```tsx
const { studentMode } = useViewIdentity({
  authEnabled: auth.enabled,
  isAdmin: auth.isAdmin,
});
```
加 import。

- [ ] **Step 4: 验证**

Run: `cd web && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/sidebar/WorkspaceSidebar.tsx web/components/sidebar/UtilitySidebar.tsx "web/app/(workspace)/home/[[...sessionId]]/page.tsx"
git commit -m "feat: 三处 studentMode 改用 useViewIdentity (支持 AUTH 关闭身份视图)"
```

---

## Task 4: SettingsHub 学生视角

**Files:**
- Modify: `web/components/settings/SettingsHub.tsx:45,79,115,127,131`

- [ ] **Step 1: 改用 useViewIdentity**

当前第 45 行：`const studentMode = auth.enabled && !auth.isAdmin;`

改为：
```tsx
const { studentMode } = useViewIdentity({
  authEnabled: auth.enabled,
  isAdmin: auth.isAdmin,
});
```
加 import `useViewIdentity`。注意此组件原来用 `auth` 变量——保留 auth 的 `enabled`/`isAdmin` 用法传给 hook，其余 `auth` 引用保持。

- [ ] **Step 2: 验证学生隐藏管理 UI**

现有代码已对 `studentMode` 隐藏：`SettingsStatusPanel`（第 131 行）、`MigrationBanner`（第 115 行）、Tour（第 127 行）。改用新 hook 后自动生效。验证第 108 行 `zh: studentMode`（语言切换 label）逻辑不变。

- [ ] **Step 3: 验证 + commit**

Run: `cd web && npx tsc --noEmit`
Expected: PASS

```bash
git add web/components/settings/SettingsHub.tsx
git commit -m "feat: SettingsHub 学生视角按 view-identity 驱动"
```

---

## Task 5: StudentRouteGate 支持 AUTH 关闭时的学生身份

**Files:**
- Modify: `web/components/access/StudentRouteGate.tsx:15`
- Modify: `web/lib/student-experience.ts`（如需扩展白名单）

- [ ] **Step 1: 修改 StudentRouteGate**

当前第 15 行：`const blocked = !auth.loading && auth.enabled && !auth.isAdmin && !isStudentRouteAllowed(pathname);`

改为：
```tsx
const { studentMode } = useViewIdentity({ authEnabled: auth.enabled, isAdmin: auth.isAdmin });
const blocked = !auth.loading && studentMode && !isStudentRouteAllowed(pathname);
```
加 import `useViewIdentity`。

- [ ] **Step 2: 扩展学生白名单（可选）**

若学生"我的"页需要 `/settings`（已允许）之外的入口（如 `/settings/appearance` 已有）。检查 `STUDENT_ALLOWED_ROUTES` 已含 `/settings/appearance`；无需改动，除非需求新增。

- [ ] **Step 3: 验证 + commit**

Run: `cd web && npx tsc --noEmit && npx tsx --test tests/student-navigation.test.ts`
Expected: PASS

```bash
git add web/components/access/StudentRouteGate.tsx
git commit -m "feat: StudentRouteGate 按 view-identity 判断学生白名单"
```

---

## Task 6: 登录页身份选择

**Files:**
- Modify: `web/app/(auth)/login/page.tsx`

- [ ] **Step 1: AUTH 关闭时显示身份选择**

在 `LoginPageContent` 中：
1. 从 `fetchAuthStatus()` 获取 `enabled`；若 `enabled === false`，显示身份选择卡片（两个 radio 卡片："学生" / "教师或管理员"），默认"学生"。
2. 提交时：若 AUTH 关闭，`setViewIdentity(selectedIdentity)` 后跳转（学生 → `/home`，教师管理员 → `/admin`）。
3. 若 AUTH 开启，保持现有表单登录逻辑（身份选择不显示）。

```tsx
// 在 LoginPageContent 顶部增加状态
const [identity, setIdentity] = useState<"student" | "staff">("student");
const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);

// 在现有 useEffect 的 fetchAuthStatus 回调里记录 enabled
setAuthEnabled(status?.enabled ?? true);

// 提交逻辑：AUTH 关闭时
if (authEnabled === false) {
  setViewIdentity(identity);
  router.replace(identity === "student" ? "/home" : "/admin");
  return;
}
```

UI（放在表单上方，仅 `authEnabled === false` 时渲染）：
```tsx
{authEnabled === false && (
  <div className="mb-5">
    <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">选择身份进入</p>
    <div className="grid grid-cols-2 gap-2">
      {(["student", "staff"] as const).map((id) => (
        <button key={id} type="button" onClick={() => setIdentity(id)}
          className={`rounded-xl border px-3 py-2.5 text-sm transition-colors ${
            identity === id ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
              : "border-[var(--border)] hover:bg-[var(--muted)]"}`}>
          {id === "student" ? "学生" : "教师或管理员"}
        </button>
      ))}
    </div>
  </div>
)}
```

注意：登录页现有表单（用户名/密码）在 AUTH 关闭时无意义——身份选择应替换表单。建议：`authEnabled === false` 时只显示身份选择 + 进入按钮；`authEnabled === true` 时显示现有表单。

- [ ] **Step 2: 验证 + commit**

Run: `cd web && npx tsc --noEmit`
Expected: PASS

```bash
git add web/app/(auth)/login/page.tsx
git commit -m "feat: 登录页 AUTH 关闭时身份选择 (学生/教师管理员)"
```

---

## Task 7: 标注台任务记忆

**Files:**
- Modify: `web/app/(workspace)/annotation/page.tsx`

- [ ] **Step 1: 任务记忆逻辑**

在 `annotation/page.tsx`：

```tsx
// 模块常量
const LAST_TASK_KEY_PREFIX = "deeptutor_last_annotation_task";
const lastTaskKeyFor = (profileId: string) => `${LAST_TASK_KEY_PREFIX}.${profileId}`;
```

从 `useCurrentLearningTask()` 获取当前档案 id（检查该 hook 是否暴露 profileId；若没有，可用 `getAnnotationBrowserSessionId()` 或现有 profile 上下文）。若档案 id 不可得，退化为全局键。

在 `chooseTask` 成功后（`setSelectedTaskData(task)` 之后）：
```tsx
try {
  window.localStorage.setItem(lastTaskKeyFor(currentProfileId), taskId);
} catch { /* ignore */ }
```

挂载恢复（在 `useEffect` 加载 tasks 之后）：
```tsx
useEffect(() => {
  if (tasks.length === 0) return;
  const saved = window.localStorage.getItem(lastTaskKeyFor(currentProfileId));
  if (!saved) return;
  const exists = tasks.some((task) => task.id === saved);
  if (exists) void chooseTask(saved);
}, [tasks.length]); // 注意 chooseTask 依赖，需用 ref 或包含在 deps
```

切换档案/退出时清除：
```tsx
// ProfileLockBanner 或 CurrentLearningTaskContext 档案变化时
window.localStorage.removeItem(lastTaskKeyFor(previousProfileId));
```

- [ ] **Step 2: 验证**

Run: `cd web && npx tsc --noEmit`
Expected: PASS。手工：选 task1 → 刷新 → 自动加载 task1。

- [ ] **Step 3: Commit**

```bash
git add web/app/(workspace)/annotation/page.tsx
git commit -m "feat: 标注台记住上次任务并自动恢复"
```

---

## Task 8: 视频与对象列表布局

**Files:**
- Modify: `web/components/annotation/UnifiedAnnotationWorkbench.tsx:345-351,435-441`

- [ ] **Step 1: 视频尺寸**

`Media` 组件第 348 行：
```tsx
if (task.modal === "video" && task.media_url) return <video controls src={task.media_url} className="max-h-[400px] w-full rounded-xl bg-black" />;
```
改为：
```tsx
if (task.modal === "video" && task.media_url)
  return (
    <div className="relative w-full">
      <video controls src={task.media_url} className="max-h-[70vh] min-h-[280px] w-full rounded-xl bg-black" />
    </div>
  );
```

- [ ] **Step 2: 对象列表窄屏浮层**

`BBoxEditor` 第 437-441 行。宽屏并排保持；窄屏（`xl:hidden`）的 `<details>` 改为**底部固定抽屉**（不占画布纵向空间）：

```tsx
<div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_220px]">
  <BboxCanvas ... />
  <aside className="hidden max-h-[600px] overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 xl:block">... 对象列表（宽屏）...</aside>
</div>
{/* 窄屏：右下角浮动按钮，点开浮层，不占画布空间 */}
<details className="fixed bottom-4 right-4 z-40 w-72 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-lg xl:hidden">
  <summary className="flex cursor-pointer items-center justify-between px-3 py-2 text-xs font-medium">
    对象列表（{state.boxes.length}）
  </summary>
  <div className="max-h-64 overflow-y-auto p-2">
    <BboxObjectList boxes={state.boxes} labels={labels} selectedId={state.selectedId} issues={issues}
      onSelect={(id) => dispatch({ type: "select", id })} onLabelChange={changeLabel} onDelete={deleteBox} />
  </div>
</details>
```

这样窄屏时对象列表是浮动抽屉，不占据画布下方的纵向空间，图片完整可见。

- [ ] **Step 3: 验证 + commit**

Run: `cd web && npx tsc --noEmit`
Expected: PASS

```bash
git add web/components/annotation/UnifiedAnnotationWorkbench.tsx
git commit -m "fix: 视频显示更大 + 窄屏对象列表改浮动抽屉不遮挡画布"
```

---

## Task 9: 文件解析子 Agent

**Files:**
- Create: `deeptutor/skills/builtin/annotation-coach-flows/references/experts/file-analyst.md`
- Modify: `deeptutor/tools/delegate_expert_tool.py`

- [ ] **Step 1: 新增 file-analyst 专家卡**

创建 `deeptutor/skills/builtin/annotation-coach-flows/references/experts/file-analyst.md`：

```markdown
---
name: file-analyst
description: 文件解析专家。解析学生上传的文件（文档/图片/表格/PDF），提取结构、总结要点、指出可标注实体与标注建议。
color: indigo
emoji: 📄
vibe: 严谨的档案员，逐页拆解，先事实后建议
---

## Identity & Memory
你是文件解析专家，服务于数据标注学习教练。只解析学生明确提供的文件，不臆造内容。

## Core Mission
把上传文件转化为对学生有用的结构化解析：
1. 文件类型与结构
2. 关键内容要点
3. 可作为标注对象的实体/边界框候选
4. 标注建议与常见陷阱

## Critical Rules
- 只输出文件中的事实，不编造数字、结构或结论
- 不修改、不删除、不移动学生文件
- 只执行只读解析命令（读取、提取文本、列出结构），不执行写操作
- 明确区分"文件原文"与"你的解读/建议"
- 遇到无法解析的格式，如实说明并建议替代方式

## Core Capabilities
- 读取文件内容（文本、表格、结构化数据）
- 提取文档要点
- 识别图片中可能的标注对象（结合图像描述）
- 生成结构化 Markdown 摘要

## Processes & Deliverables
输出格式：
```markdown
## 文件解析结果
- 文件：<文件名> · <类型>
- 结构：<章节/字段/对象概览>
### 要点
- <关键内容 1>
### 可标注对象建议
- <实体/边界框候选与依据>
### 风险与建议
- <解析局限、标注注意点>
```
```

- [ ] **Step 2: 添加专家白名单**

在 `deeptutor/tools/delegate_expert_tool.py`：
1. `EXPERT_IDS` 追加 `"file-analyst"`。
2. `EXPERT_TOOL_WHITELISTS` 追加：
```python
"file-analyst": ("read_file", "exec_tool", "kb_search"),
```
注意：`exec_tool` 需限制为只读（解析命令）。检查 `EXPERTS_DIR` 目录存在 `file-analyst.md`。

- [ ] **Step 3: 测试专家卡存在性**

运行现有专家卡测试（查找 `tests/` 中校验 experts 目录与 manifest 双向一致的测试）：
```powershell
python -m pytest tests/ -k "expert or delegate" -q
```
Expected: PASS（若存在 manifest 校验，file-analyst 已自动纳入）。

- [ ] **Step 4: 检查 manifest 是否需要更新**

若 `experts_manifest.json` 存在且是 source of truth，将 file-analyst 条目加入（name/description/file 对齐）。检查 `EXPERT_ROUTE` 是否需要为 file-analyst 加路由（通常 delegate 是显式调用，无需路由）。

- [ ] **Step 5: 验证 + commit**

```powershell
python -m pytest tests/ -k "expert or delegate" -q
cd web && npx tsc --noEmit
```

```bash
git add deeptutor/skills/builtin/annotation-coach-flows/references/experts/file-analyst.md deeptutor/tools/delegate_expert_tool.py
git commit -m "feat: 文件解析子agent (file-analyst 专家卡 + 白名单)"
```

---

## Task 10: 整体验证

**Files:** 无新增

- [ ] **Step 1: 全量前端检查**

```powershell
cd web
npx tsc --noEmit
npx eslint <本次修改的 TS/TSX 文件> --quiet
npm run test:node
npm run build
```

Expected: tsc PASS、test:node 通过、build 成功。

- [ ] **Step 2: 后端检查**

```powershell
python -m ruff check deeptutor/tools/delegate_expert_tool.py deeptutor/skills
python -m pytest tests/ -k "expert or delegate" -q
```

Expected: ruff PASS、pytest PASS。

- [ ] **Step 3: 浏览器冒烟（Playwright）**

覆盖：
1. AUTH 关闭：登录页显示身份选择 → 选学生 → 侧栏四入口（学习/实训/成长/我的），无能力中心/记忆/规范/定时任务
2. 学生设置页：仅"外观"，无系统状态面板
3. 学生访问 `/memory`、`/teacher` → 跳转 `/home`
4. 重新登录选"教师或管理员" → 完整管理侧栏 + 全部设置
5. 标注台：选 task → 刷新 → 自动恢复；视频任务显示完整；窄屏对象列表浮动不遮挡
6. 控制台无 `Canvas is already in use`

- [ ] **Step 4: 汇总提交**

若冒烟发现小问题，逐个修复提交。确认全部通过后，向用户汇报。

---

## 自审清单

- [ ] 覆盖设计文档 3.1（身份模型）→ Task 1-6
- [ ] 覆盖设计文档 3.2（设置简化）→ Task 4
- [ ] 覆盖设计文档 3.3（任务记忆）→ Task 7
- [ ] 覆盖设计文档 3.4（视频/对象列表）→ Task 8
- [ ] 覆盖设计文档 3.5（文件子 Agent）→ Task 9
- [ ] 覆盖测试要求（设计文档 §6）→ Task 1/10
- [ ] 无 TBD/占位符
- [ ] 类型一致（ViewIdentity / studentMode / useViewIdentity 命名统一）
