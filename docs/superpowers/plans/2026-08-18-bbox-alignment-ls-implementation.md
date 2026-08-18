# 自建标注台 bbox 对齐 Label Studio 实施计划（P0 核心）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把自建 bbox 标注台的核心交互对齐 Label Studio：标签面板+热键、快捷键补齐、多选、撤销重做修复、图像操作增强。

**Architecture:** 前端改造。先修 reducer 增量历史（基础），再补快捷键、标签面板、多选、图像操作。全部在 `web/components/annotation/bbox/` 内完成，非 bbox 类型不动。

**Tech Stack:** Next.js (React 18), TypeScript, Tailwind, useReducer。

**参考**：设计文档 `docs/superpowers/specs/2026-08-18-bbox-alignment-ls-design.md`。

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `web/components/annotation/bbox/bbox-reducer.ts` | 状态机：多选 + 增量历史 + freeze | 修改 |
| `web/components/annotation/bbox/bbox-geometry.ts` | Bbox 类型（加 selected 多选相关纯函数） | 修改 |
| `web/components/annotation/bbox/BboxToolbar.tsx` | 工具条 + 标签面板 + kbd 提示 | 修改 |
| `web/components/annotation/bbox/BboxCanvas.tsx` | 画布：多选 marquee、滚轮缩放、Shift+1/2 | 修改 |
| `web/components/annotation/bbox/BboxObjectList.tsx` | 多选支持 + 批量操作按钮 | 修改 |
| `web/components/annotation/bbox/BboxLabelPanel.tsx` | 新增：左侧色块标签面板 | 新建 |
| `web/components/annotation/UnifiedAnnotationWorkbench.tsx` | BBoxEditor：接入面板 + 快捷键 + 多选 | 修改 |
| `web/tests/bbox-reducer.test.ts` | reducer 增量历史 + 多选测试 | 新建 |
| `web/tests/bbox-label-panel.test.ts` | 标签面板 + 热键测试 | 新建 |

---

## Task 1: reducer 增量历史 + 多选

**Files:**
- Modify: `web/components/annotation/bbox/bbox-reducer.ts`
- Modify: `web/components/annotation/bbox/bbox-geometry.ts`
- Create: `web/tests/bbox-reducer.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
// web/tests/bbox-reducer.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";
import { createBboxState, reduceBboxState } from "../components/annotation/bbox/bbox-reducer";
import type { Bbox } from "../components/annotation/bbox/bbox-geometry";

const box = (id: string, label = "car"): Bbox => ({ id, x: 10, y: 10, width: 30, height: 30, label });

test("增量 add/update/delete 产生可撤销历史", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a") });
  s = reduceBboxState(s, { type: "add", box: box("b") });
  assert.equal(s.boxes.length, 2);
  assert.equal(s.past.length, 2);
  s = reduceBboxState(s, { type: "undo" });
  assert.equal(s.boxes.length, 1);
  s = reduceBboxState(s, { type: "redo" });
  assert.equal(s.boxes.length, 2);
});

test("undo 后保持选中", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a") });
  s = reduceBboxState(s, { type: "add", box: box("b") });
  s = reduceBboxState(s, { type: "select", id: "b" });
  s = reduceBboxState(s, { type: "undo" });
  assert.equal(s.selectedId, null); // undo 回退到只剩 a，b 被移除
  s = reduceBboxState(s, { type: "redo" });
  assert.equal(s.boxes.length, 2);
});

test("replace-external 只清历史当外部变化", () => {
  let s = createBboxState([box("a")], "car");
  s = reduceBboxState(s, { type: "add", box: box("b") });
  assert.equal(s.past.length, 1);
  // replace-external 语义：外部数据同步，清空历史
  s = reduceBboxState(s, { type: "replace-external", boxes: [box("a"), box("b"), box("c")] });
  assert.equal(s.past.length, 0);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd web && npx tsx --test tests/bbox-reducer.test.ts`（若 tsx 不可用，用 npm run test:node，参考仓库现有测试）
Expected: 现有 reducer 的 undo 可能因 commit 逻辑部分通过，但需确认测试覆盖了所需行为。若全过，说明当前实现已部分正确——但实际 BBoxEditor 用的是 replace-external（父级 commit 回调），需在 Task 3 改调用。

- [ ] **Step 3: 扩展 reducer 支持多选**

修改 `bbox-geometry.ts`：BboxState 的 `selectedId` → `selectedIds: string[]`（或保留 selectedId + 加 selectedIds）。建议改为 `selectedIds: string[]`：

```ts
export type BboxState = {
  boxes: Bbox[];
  selectedIds: string[];
  activeLabel: string;
  past: Bbox[][];
  future: Bbox[][];
  /** 拖拽/绘制中：连续 update 合并为一步 */
  frozen?: boolean;
};
```

action 扩展：
```ts
| { type: "select"; ids: string[] }
| { type: "select-toggle"; id: string }
| { type: "select-all" }
| { type: "clear-selection" }
| { type: "freeze" }
| { type: "unfreeze"; box: Bbox }   // 解冻时入栈当前快照
```

`commit` 加参数：合并连续 update（frozen 时替换 last past 而不新增）：
```ts
function commit(state, boxes, selectedIds, { freeze = false } = {}) {
  if (state.frozen) {
    // 冻结中：替换 past 最后一项（合并步骤）
    const prev = state.past.at(-1) ?? [];
    return { ...state, boxes: copy(boxes), selectedIds, past: [...state.past.slice(0, -1), prev] };
  }
  return { ...state, boxes: copy(boxes), selectedIds, past: [...state.past.slice(-39), copy(state.boxes)], future: [] };
}
```

批量操作 action：
```ts
| { type: "delete-selected" }  // 删除所有 selectedIds
| { type: "set-selected-label"; label: string }  // 给所有 selectedIds 改标签
```

- [ ] **Step 4: 更新测试 + 运行通过**

```ts
// 追加多选测试
test("多选 + 批量删除", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a") });
  s = reduceBboxState(s, { type: "add", box: box("b") });
  s = reduceBboxState(s, { type: "select", ids: ["a", "b"] });
  assert.deepEqual(s.selectedIds, ["a", "b"]);
  s = reduceBboxState(s, { type: "delete-selected" });
  assert.equal(s.boxes.length, 0);
});

test("批量改标签", () => {
  let s = createBboxState([], "car");
  s = reduceBboxState(s, { type: "add", box: box("a", "car") });
  s = reduceBboxState(s, { type: "add", box: box("b", "car") });
  s = reduceBboxState(s, { type: "select", ids: ["a", "b"] });
  s = reduceBboxState(s, { type: "set-selected-label", label: "person" });
  assert.ok(s.boxes.every((b) => b.label === "person"));
});
```

Run: `cd web && npm run test:node`（应含新增 reducer 测试）
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/annotation/bbox/bbox-reducer.ts web/components/annotation/bbox/bbox-geometry.ts web/tests/bbox-reducer.test.ts
git commit -m "feat: bbox reducer 增量历史 + 多选支持"
```

---

## Task 2: BBoxEditor 改用增量 commit（修复死代码）

**Files:**
- Modify: `web/components/annotation/UnifiedAnnotationWorkbench.tsx`

- [ ] **Step 1: 修改 BBoxEditor 的 commit 回调**

当前（约 402-406 行）：
```tsx
const commit = useCallback((boxes: Bbox[], selectedId: string | null) => {
  dispatch({ type: "replace-external", boxes });
  dispatch({ type: "select", id: selectedId });
  onChange(boxes);
}, [onChange]);
```

改为增量 dispatch（不再 replace-external 清历史）：
```tsx
const commit = useCallback((boxes: Bbox[], selectedIds: string[]) => {
  // 用 diff 推断动作：新增/删除/更新
  // 简化：dispatch update/add 由调用方决定更精确；这里提供包装
  dispatch({ type: "replace-boxes", boxes, selectedIds });  // 新增 action：保留历史（不 replace-external）
  onChange(boxes);
}, [onChange]);
```

更精确的方案：BBoxEditor 内部的操作（deleteBox/changeLabel/onCommit from canvas）改为直接派发语义 action：
- `deleteBox(id)` → `dispatch({ type: "delete-selected" })` 或按 id 删除（若单选）
- `changeLabel(id, label)` → `dispatch({ type: "update", box: {...} })`（单选）或 `set-selected-label`（多选）
- 画布 onCommit → 区分 add/update：新增框派发 `add`，移动/缩放派发 `update`

需要 BBoxEditor 传入的 onCommit 区分类型。建议 BboxCanvas 的 onCommit 改为 `(box, { isNew }) => void`，BBoxEditor 据此派发 `add` 或 `update`。

`replace-external` 只保留在外部 predictions 变化时（useEffect 398-400 行），且此时清历史是合理的（外部数据同步）。

- [ ] **Step 2: 验证**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add "web/app/(workspace)/annotation/page.tsx" "web/components/annotation/UnifiedAnnotationWorkbench.tsx"
git commit -m "fix: BBoxEditor 改用增量 commit 修复撤销历史死代码"
```

---

## Task 3: 快捷键补齐

**Files:**
- Modify: `web/components/annotation/bbox/BboxToolbar.tsx`
- Modify: `web/components/annotation/UnifiedAnnotationWorkbench.tsx`（BBoxEditor 的 keydown）

- [ ] **Step 1: 新建 useBboxHotkeys hook（或直接在 BBoxEditor 扩展 keydown）**

在 BBoxEditor 现有 keydown effect（约 411-423 行）基础上扩展：

```tsx
useEffect(() => {
  const onKeyDown = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement | null;
    const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.tagName === "SELECT";
    if (typing) return;
    // 已有
    if ((event.key === "Delete" || event.key === "Backspace") && state.selectedIds.length) { event.preventDefault(); deleteSelected(); }
    if (event.key.toLowerCase() === "v") setTool("select");
    if (event.key.toLowerCase() === "b" || event.key.toLowerCase() === "r") setTool("draw");  // R + B
    if (event.key.toLowerCase() === "h") setTool("pan");
    if (event.key.toLowerCase() === "u") dispatch({ type: "clear-selection" });
    if (event.key === "Escape") dispatch({ type: "clear-selection" });
    // 撤销/重做
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      if (event.shiftKey) onRedo(); else onUndo();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); onRedo(); }
    // 标签 1-9
    if (/^[1-9]$/.test(event.key)) {
      const idx = parseInt(event.key) - 1;
      if (idx < labels.length) {
        event.preventDefault();
        if (state.selectedIds.length === 1) {
          dispatch({ type: "update", box: { ...state.boxes.find(b => b.id === state.selectedIds[0])!, label: labels[idx] } });
        } else {
          dispatch({ type: "set-active-label", label: labels[idx] });
        }
      }
    }
    // 滚轮缩放
    // Ctrl+Plus / Ctrl+Minus
    if ((event.ctrlKey || event.metaKey) && (event.key === "+" || event.key === "=")) { event.preventDefault(); setZoom(z => Math.min(3, z + 0.25)); }
    if ((event.ctrlKey || event.metaKey) && event.key === "-") { event.preventDefault(); setZoom(z => Math.max(0.5, z - 0.25)); }
    // Shift+1 / Shift+2
    if (event.shiftKey && event.key === "1") { event.preventDefault(); onFit(); }
    if (event.shiftKey && event.key === "2") { event.preventDefault(); setZoom(1); }
  };
  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}, [deleteSelected, labels, onRedo, onUndo, onFit, setTool, state.selectedIds, state.boxes]);
```

注意：`deleteSelected` 现在是批量删除（Task 1 的 delete-selected）。`onFit` 是现有 `onFit={() => setZoom(1)}`。

- [ ] **Step 2: 工具栏 kbd 提示**

BboxToolbar 按钮加 kbd 子元素显示快捷键（V/R/H/Ctrl+Z 等），样式 `text-[10px] px-1 rounded bg-[var(--muted)]`。

- [ ] **Step 3: 验证 + Commit**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

```bash
git add "web/components/annotation/bbox/BboxToolbar.tsx" "web/components/annotation/UnifiedAnnotationWorkbench.tsx"
git commit -m "feat: bbox 快捷键对齐 LS (R/H/Shift+1-2/标签1-9/重做)"
```

---

## Task 4: 标签面板

**Files:**
- Create: `web/components/annotation/bbox/BboxLabelPanel.tsx`
- Modify: `web/components/annotation/UnifiedAnnotationWorkbench.tsx`

- [ ] **Step 1: 写测试**

```ts
// web/tests/bbox-label-panel.test.ts
// 若仓库无 React 渲染测试设施（renderHook），改为纯函数测试标签配色/编号
import assert from "node:assert/strict";
import { test } from "node:test";
import { labelColorFor, labelHotkeyFor } from "../components/annotation/bbox/label-style";

test("labelColorFor 对同一标签稳定", () => {
  assert.equal(labelColorFor("car"), labelColorFor("car"));
  assert.notEqual(labelColorFor("car"), labelColorFor("person"));
});

test("labelHotkeyFor 前 9 个标签分配 1-9", () => {
  assert.equal(labelHotkeyFor(0), "1");
  assert.equal(labelHotkeyFor(8), "9");
  assert.equal(labelHotkeyFor(9), null); // 10+ 无热键
});
```

- [ ] **Step 2: 新建 label-style.ts（配色 + 热键）**

```ts
// web/components/annotation/bbox/label-style.ts
// 稳定哈希色表（避免引入 pleasejs 依赖）
const PALETTE = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#F97316", "#EC4899", "#84CC16", "#0EA5E9"];

export function labelColorFor(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

export function labelHotkeyFor(index: number): string | null {
  return index < 9 ? String(index + 1) : null;
}
```

- [ ] **Step 3: 新建 BboxLabelPanel 组件**

```tsx
// web/components/annotation/bbox/BboxLabelPanel.tsx
"use client";
import { labelColorFor, labelHotkeyFor } from "./label-style";

export default function BboxLabelPanel({
  labels, activeLabel, selectedIds, onActiveLabelChange, onApplyToSelection,
}: {
  labels: string[];
  activeLabel: string;
  selectedIds: string[];
  onActiveLabelChange: (label: string) => void;
  onApplyToSelection: (label: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted-foreground)]">标签</div>
      {labels.map((label, index) => {
        const active = label === activeLabel;
        const color = labelColorFor(label);
        const hotkey = labelHotkeyFor(index);
        return (
          <button
            key={label}
            type="button"
            onClick={() => selectedIds.length ? onApplyToSelection(label) : onActiveLabelChange(label)}
            className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${active ? "border-transparent text-white" : "border-[var(--border)] hover:bg-[var(--muted)]"}`}
            style={{ backgroundColor: active ? color : "transparent" }}
          >
            <span className="h-3 w-3 rounded-sm border border-black/10" style={{ backgroundColor: color }} />
            <span className="flex-1 text-left">{label}</span>
            {hotkey && <kbd className="rounded bg-black/10 px-1 text-[10px]">{hotkey}</kbd>}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: BBoxEditor 接入面板**

- 布局改为三栏：`grid lg:grid-cols-[140px_minmax(0,1fr)_220px]`（标签面板 | 画布 | 对象列表）。
- 面板 props：`labels`、`activeLabel={state.activeLabel}`、`selectedIds={state.selectedIds}`、`onActiveLabelChange` → dispatch set-active-label、`onApplyToSelection` → dispatch set-selected-label（多选时）。
- 保留工具栏类别下拉（与面板同步，改任一处都更新 activeLabel）。

- [ ] **Step 5: 验证 + Commit**

Run: `cd web && npm run test:node` + `npx tsc --noEmit`
Expected: PASS

```bash
git add web/components/annotation/bbox/BboxLabelPanel.tsx web/components/annotation/bbox/label-style.ts web/tests/bbox-label-panel.test.ts "web/components/annotation/UnifiedAnnotationWorkbench.tsx"
git commit -m "feat: bbox 左侧标签面板 (色块+1-9热键+改选中标签)"
```

---

## Task 5: 多选画布交互

**Files:**
- Modify: `web/components/annotation/bbox/BboxCanvas.tsx`
- Modify: `web/components/annotation/bbox/BboxObjectList.tsx`

- [ ] **Step 1: BboxCanvas 支持 marquee 框选**

- select 工具下拖拽空白 → 画 marquee（虚线矩形），选中覆盖到的框。
- Ctrl+点击 → toggle 选中。
- 现有 `onSelect(id)` 扩展为 `onSelect(ids: string[])` 或保留 onSelect + 加 `onToggleSelect`。

**实现要点**（BboxCanvas）：
```tsx
// 状态
const [marquee, setMarquee] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
const marqueeStart = useRef<{ x: number; y: number } | null>(null);

// select 工具 + 点击空白开始 marquee
const onPointerDown = (e) => {
  if (tool === "select" && !clickedBox(e)) {
    marqueeStart.current = { x: e.clientX, y: e.clientY };
    setMarquee({ x: e.clientX, y: e.clientY, w: 0, h: 0 });
  }
};
// pointermove 更新 marquee
// pointerup: 计算覆盖框，调 onSelect(覆盖的 ids)；清 marquee
```

需要把画布内框的屏幕坐标暴露给 marquee 计算（boxes 已有相对坐标，加上容器偏移）。

- [ ] **Step 2: BboxObjectList 支持多选 + 批量**

- 行点击：普通点击单选；Ctrl+点击 toggle；Shift+点击区间。
- 选中行高亮（多行）。
- 顶部加"全选"按钮（可选）。

- [ ] **Step 3: 验证 + Commit**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

```bash
git add web/components/annotation/bbox/BboxCanvas.tsx web/components/annotation/bbox/BboxObjectList.tsx "web/components/annotation/UnifiedAnnotationWorkbench.tsx"
git commit -m "feat: bbox 多选 (框选/ctrl加选/批量删除改标签)"
```

---

## Task 6: 图像操作

**Files:**
- Modify: `web/components/annotation/bbox/BboxCanvas.tsx`

- [ ] **Step 1: 滚轮缩放**

在画布容器加 `onWheel`：
```tsx
const handleWheel = (e: React.WheelEvent) => {
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 0.9;
  setZoom(z => Math.min(3, Math.max(0.5, z * factor)));
};
```
注意：滚轮缩放需要以鼠标位置为中心（可选，先做简单版），并 `preventDefault` 阻止页面滚动。

- [ ] **Step 2: 适配/原始尺寸**

- `onFit`（Shift+1）：改为自适应视口（计算 image 到容器宽高的 fit 比例），当前是 `setZoom(1)`。
- Shift+2：`setZoom(1)`（原始 100%）。

区分：
```tsx
const fitToViewport = () => {
  const container = containerRef.current;
  if (!container || !bounds) return;
  const scaleX = (container.clientWidth - 16) / bounds.width;
  const scaleY = (container.clientHeight - 16) / bounds.height;
  setZoom(Math.min(scaleX, scaleY));
};
```

- [ ] **Step 3: H 平移工具**

pan 工具已存在（BboxToolbar 有 pan 按钮）。加 H 键绑定（Task 3 已做）。确认 pan 工具下拖拽能平移画布（现有实现如已有则保留）。

- [ ] **Step 4: 验证 + Commit**

Run: `cd web && npx tsc --noEmit` + `npm run test:node`
Expected: PASS

```bash
git add web/components/annotation/bbox/BboxCanvas.tsx "web/components/annotation/UnifiedAnnotationWorkbench.tsx"
git commit -m "feat: bbox 图像操作 (滚轮缩放/适配/原始尺寸)"
```

---

## Task 7: 整体验证

**Files:** 无新增

- [ ] **Step 1: 前端全量检查**

```powershell
cd web
npx tsc --noEmit
npx eslint <本次修改文件> --quiet
npm run test:node
npm run build
```

- [ ] **Step 2: 浏览器冒烟**

覆盖：
1. 标签面板：色块显示、1-9 热键切换、选中框后点标签改标签
2. 画框 R 键（+B 兼容）
3. 多选：V 框选 + Ctrl 加选 + Delete 批量删除
4. 撤销重做：画两个框 → Ctrl+Z 撤销一个 → Ctrl+Shift+Z 重做
5. 滚轮缩放、Shift+1 适配、Shift+2 原始尺寸
6. H 平移
7. 控制台无 `Canvas is already in use`

- [ ] **Step 3: 汇总提交**

若冒烟发现小问题，逐个修复提交。全部通过后向用户汇报。

---

## 自审清单

- [ ] 覆盖设计 3.1（标签面板）→ Task 4
- [ ] 覆盖设计 3.2（快捷键）→ Task 3
- [ ] 覆盖设计 3.3（多选）→ Task 1 + 5
- [ ] 覆盖设计 3.4（撤销重做）→ Task 1 + 2
- [ ] 覆盖设计 3.5（图像操作）→ Task 6
- [ ] 设计 3.6（对象列表增强）→ 可选，未含（标注为 P1 后续）
- [ ] 无 TBD/占位符
- [ ] 类型一致（selectedIds / onApplyToSelection / set-selected-label / labelColorFor）
