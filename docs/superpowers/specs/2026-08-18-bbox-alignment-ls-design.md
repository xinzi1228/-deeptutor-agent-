# 自建标注台 bbox 对齐 Label Studio 设计（P0 核心）

> 日期：2026-08-18
> 状态：设计（待用户审批）
> 关联：`docs/superpowers/specs/2026-08-17-learning-training-ux-v2-design.md` §3.5（标注台对齐 LS，专项）

---

## 1. 背景与目标

自建 React 标注台（`web/components/annotation/`）的 bbox 编辑器与 Label Studio 存在显著交互差距：标签无面板/颜色/热键、无多选、快捷键不齐、撤销重做实现是死代码、图像操作弱。目标是把自建台 bbox 的**核心交互手感对齐 LS**，提升教学标注效率与演示观感。

经调研（LS 前端源码 + 官方文档 + 自建台代码逐项对比）确认差距集中在 **P0 五类**。

## 2. 决策汇总（已与用户确认）

| # | 决策 |
|---|------|
| 1 | 画框快捷键**对齐 R**（LS 现行版 R 画框，B 是画笔）；保留现有 B 作为兼容 |
| 2 | 范围 **P0 bbox 核心**（非 bbox 类型后续单独议） |
| 3 | 标签面板 = **左侧独立色块面板** + 编号 kbd + 选中框后点标签改标签 |
| 4 | 撤销重做 = **修 reducer 增量历史**（不再被 replace-external 清空） |

## 3. 设计

### 3.1 标签面板（左侧独立）

**文件**：`web/components/annotation/bbox/BboxToolbar.tsx`、新建 `web/components/annotation/bbox/BboxLabelPanel.tsx`

- 新增 `BboxLabelPanel` 组件：垂直色块按钮列表，每个标签显示：
  - 色块（按标签名自动生成稳定色，用 `pleasejs`-style 或预置色表哈希）
  - 标签名
  - 编号 kbd（1-9 按顺序分配，对应 `1`~`9`）
- 交互：
  - 点击标签 = 选中为当前画框默认标签（高亮）
  - **先选中已有框再点标签 = 改该框标签**（LS 行为）
  - 快捷键 `1`-`9` 切换当前标签
- 布局：BBoxEditor 改为三栏（标签面板 | 画布 | 对象列表），窄屏标签面板折叠为工具栏内色块组
- 保留工具栏现有类别下拉作为兼容（与面板双向同步）

### 3.2 快捷键补齐（对齐 LS）

**文件**：`web/components/annotation/bbox/BboxToolbar.tsx`、`UnifiedAnnotationWorkbench.tsx`

| 动作 | 键 | 说明 |
|------|-----|------|
| 画框 | **R**（新增）+ B（兼容） | 对齐 LS |
| 平移 | **H** | 与现有 pan 工具绑定 |
| 撤销 | Ctrl+Z | 已有 |
| 重做 | **Ctrl+Shift+Z**（新增）+ Ctrl+Y（保留） | 对齐 LS |
| 适配画布 | **Shift+1** | 对齐 LS |
| 原始尺寸 | **Shift+2** | 对齐 LS |
| 缩放 | **滚轮缩放**（新增）、Ctrl+Plus / Ctrl+Minus | 对齐 LS |
| 删除 | Delete / Backspace | 已有 |
| 取消选中 | Escape / **u** | 新增 u |
| 标签 1-9 | `1`-`9` | 新标签面板 |
| 重复区域 | **Ctrl+D** | 对齐 LS（可选） |

实现：抽统一 `useBboxHotkeys` hook（集中 keydown 处理，INPUT 中不拦截），工具栏按钮显示 kbd 提示。

### 3.3 多选（V 工具框选）

**文件**：`web/components/annotation/bbox/BboxCanvas.tsx`、`bbox-reducer.ts`

- V 选择工具下：
  - 拖拽出 marquee 框选（`ImageSelection` 风格）
  - Ctrl+点击 加选/减选
  - Shift+点击对象列表 区间多选
- reducer 支持 `selectedIds: string[]`（当前单 `selectedId` 扩展）
- 批量操作：批量删除（Delete）、批量改标签（标签面板点标签）
- 选中态：多框同时高亮

### 3.4 撤销重做修复

**文件**：`web/components/annotation/bbox/bbox-reducer.ts`

- 当前 bug：`replace-external` 无条件清空 past/future → reducer 内部历史是死代码，靠父级整表快照（粒度粗）。
- 修复：`commit()` 不再先派发 `replace-external`，改为真正的增量 action：
  - `add-box` / `update-box` / `delete-box` 各自入栈到 past
  - `replace-external` 仅用于外部数据同步（保留清历史语义，但调用方改为只在外部变化时用）
  - 撤销后保持选区（恢复 selectedIds）
- 绘制/拖拽期间 freeze（连续 update 合并为一步），结束后入栈
- 保留父级整表快照作为兜底（两轨共存，父级仅在校验/提交时用）

### 3.5 图像操作

**文件**：`web/components/annotation/bbox/BboxCanvas.tsx`

- 滚轮缩放（0.5~3 区间，以鼠标为中心）——当前只有按钮缩放
- Shift+1 适配画布（改为自适应视口，非重置 zoom=1）
- Shift+2 原始尺寸（100%）
- H 平移工具（当前 pan 是按钮，需保留按钮 + 加 H 键）

### 3.6 对象列表增强（可选 P1，若时间允许）

- 行内"隐藏/锁定"按钮（eye/lock）
- hover 画布区域高亮联动 + 选中自动滚动
- 坐标数值化编辑（x/y/w/h 数字输入）

## 4. 数据与存储

- 无新持久化。bbox 坐标保持当前像素域（0..bounds）；若未来需与 LS 互操作再做百分比换算（本设计不涉及）。
- localStorage：无新增。

## 5. 明确不做（本设计）

- 非 bbox 类型（classification/judgment/ner/audio/video/json）对齐——后续专项。
- LS 的分组/排序树、关系（Relation）、评论、账号级热键——与教学定位冲突。
- 旋转手柄、预测框虚线样式（P1/P2）。
- 标签自动配色算法不引入 `pleasejs` 依赖（用内置哈希色表，避免新增 npm 包）。

## 6. 测试

| 层 | 测试 |
|----|------|
| reducer 单测 | 增量 add/update/delete 历史、undo/redo 恢复选区、freeze 合并 |
| 组件单测 | 标签面板渲染、1-9 热键、改标签、多选 |
| 前端类型 | `npx tsc --noEmit` |
| 构建 | `npm run build` |
| 冒烟 | Playwright：画框 R、多选框选、标签面板点标签改框、Ctrl+Shift+Z 重做、滚轮缩放；无 `Canvas is already in use` |

## 7. 实施顺序

1. 3.4 撤销重做修复（reducer，基础）
2. 3.2 快捷键补齐（依赖 reducer 稳定）
3. 3.1 标签面板（依赖快捷键）
4. 3.3 多选（依赖 reducer）
5. 3.5 图像操作
6. 3.6 对象列表增强（可选）
7. 测试与验证

每阶段独立提交，不 push，直到用户确认。
