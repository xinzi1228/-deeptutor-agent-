# 标注体验修复与档案隔离设计（7 项）

> 日期：2026-08-18
> 状态：设计（待用户审批）
> 关联：`docs/superpowers/specs/2026-08-17-learning-training-ux-v2-design.md`（v2，已完成）

---

## 1. 背景与目标

用户发现 7 项 bug/体验问题，经代码调查确认根因后逐项确定方案。本设计聚焦：档案隔离、专业模式联动、任务自动保存/恢复、对象列表折叠、教练实时状态、身份引导、实践题筛选。

## 2. 决策汇总（已与用户确认）

| # | 问题 | 方案 |
|---|------|------|
| 1 | 新档案残留旧对话 | migration 只在首次复制账号级旧库，之后新档案从空开始 |
| 2 | 专业模式未就绪 | preload 联动 state + 未解锁引导 + preload 失败重试 |
| 3 | 切页后不恢复任务 | 切页/切任务自动保存 + 记住最后模态 + 各模态记忆恢复 |
| 4 | 对象列表阻挡图片 | 对象列表可折叠（中等宽度折叠为按钮） |
| 5 | 教练滞后/实时性 | 前端共享状态（零延迟）+ 轮询兜底 + 缺漏推导 |
| 6 | 看不到登录页 | 首次访问引导 /login 选身份；已有身份直接进对应端 |
| 7 | 理论题混入标注台 | 后端 `/tasks?practice_only=true` 过滤实践题 |

## 3. 设计

### 3.1 档案隔离修复（问题 1）

**文件**：`deeptutor/services/learning_profiles/migration.py`

- 当前 `_sources()` 每次 create_profile 都返回账号级旧库（chat_history.db + memory）→ `migrate()` 整份复制。
- **修复**：迁移改为"仅首次"——在账号级库存在且新档案目标库为空时执行；新档案已有数据（或账号级库为空）则跳过。
- 实现：`migrate()` 前检查目标档案的 `sessions/chat_history.db` 是否已存在且非空；若存在则视为"已初始化"，不复制账号级数据。
- 补充：保留迁移标记文件（如 `profile_root/.migration-v1`），首次迁移后写入，后续 create 检测到即跳过。
- 测试：创建档案 A（复制账号旧库）→ 创建档案 B（不复制，空开始）→ 断言 B 的会话为空。

### 3.2 专业模式 preload 联动（问题 2）

**文件**：`web/app/(workspace)/annotation/page.tsx`

1. **preload 成功更新 state**：`POST /preload` 成功后 `setLabelStudio(current => ({...current, ready: data.ready, prepared_count: data.prepared, task_urls: data.task_urls}))`（不再 fire-and-forget 丢弃）。
2. **preload 失败重试 1 次**：失败后延时 2s 重试一次，仍失败保留失败状态。
3. **未解锁引导**：`/status` 返回 423 时（前端 catch），pro 面板文案改为"请先在左侧解锁学习档案"而非"尚未就绪"。
4. **进入 pro 时状态联动**：mode 切到 pro 时重拉 `/status`（已有），并把 preload 的 task_urls 用于隐藏 iframe 预载（已有 preloadSrc，补充：preload 成功后即挂载隐藏 iframe）。

### 3.3 任务自动保存 + 模态记忆（问题 3）

**文件**：`web/app/(workspace)/annotation/page.tsx`、`web/lib/annotation-mode-memory.ts`

1. **自动保存增强**：
   - 现有 650ms 防抖草稿保存保留。
   - 切任务/切模态/切页面（beforeunload + 路由离开）时强制 flush 草稿（调 `saveOwnedCheckpoint` 或现有草稿保存）。
   - 恢复时读取后端草稿（已有 draft 读取逻辑，确认链路完整）。

2. **记住最后模态**：
   - `annotation-mode-memory.ts` 新增 `deeptutor_last_annotation_mode.<profileId>` 键（存 `image/text/audio/video/pro`）。
   - 切换模态时写入；页面重进时初始 mode 从该键读取（而非硬编码 `image`）。
   - 恢复优先级：URL query mode > 最后模态记忆 > 默认 image。

3. **pro 模式记忆**：
   - `chooseProfessionalTask` 成功后写模态记忆（`pro` 键存 taskId）——当前不写。
   - 重进 pro 时恢复（若 `mode=pro` 且记忆存在）。

### 3.4 对象列表可折叠（问题 4）

**文件**：`web/components/annotation/UnifiedAnnotationWorkbench.tsx`（BBoxEditor 布局）

- 中等宽度（lg 区间 1024~1279px）：对象列表 aside 改为**可折叠**——默认收起为右侧小按钮，点击展开覆盖（或内联展开）。
- 宽屏（xl 1280px+）：保持常驻右侧。
- 实现：`useState` `objListCollapsed`，lg 区间时默认 true（收起），按钮切换；xl 区间忽略折叠始终显示。
- 窄屏（<lg）：保持浮动抽屉（已有）。

### 3.5 教练实时状态（问题 5）

**文件**：新建 `web/components/annotation/AnnotationLiveStateContext.tsx`（共享 store）

1. **前端共享状态**：
   - 新建 React Context（`AnnotationLiveStateProvider`）持有一个 `liveState` 对象：`{ taskId, annotationCount, labels, selectedObjectId, currentLabel, tool, missingObjects }`。
   - `UnifiedAnnotationWorkbench`（或 annotation page）每次状态变化（`onLiveState`/`reportLiveState`）时更新 context。
   - `AnnotationCoach` 订阅 context，实时显示当前任务/框数/标签/缺漏，无需轮询。

2. **缺漏推导**：
   - `UnifiedAnnotationWorkbench` 已知 ground_truth（task.ground_truth），可计算"已标标签 vs 应有标签"的差集 → `missingObjects` 供教练提示。

3. **轮询兜底**：
   - 现有 30s 轮询保留（struggle 介入 + 断线兜底），但任务切换时教练面板立即从 context 读到新状态（零延迟）。

### 3.6 首次访问引导登录（问题 6）

**文件**：`web/app/(workspace)/page.tsx`（`/` 重定向）、`web/lib/view-identity.ts`

- `/` 根页：检查 `getViewIdentity()` 是否显式设置过。若 localStorage **无身份键**（首次访问）→ `router.replace("/login")`（显示身份选择）；若已有身份 → 直接进对应端（student→/home，staff→/admin）。
- `view-identity.ts` 加 `hasChosenIdentity()`（检测键是否存在）。
- 侧栏（可选）加"切换身份"入口回 /login。

### 3.7 实践题筛选（问题 7）

**文件**：`deeptutor/api/routers/annotation.py`（`/tasks`）、`web/app/(workspace)/annotation/page.tsx`

1. 后端 `/tasks` 支持 `?practice_only=true`：
   - practice 类型白名单：`bbox, audio_event, audio_transcription, video_event, video_tracking, ner`（可操作的标注任务）。
   - 理论类型排除：`classification, judgment, standard, error_case`。
2. 前端标注台 `/api/v1/annotation/tasks?practice_only=true` 请求。
3. 保留 `/tasks` 全量返回（其它消费方/测试不受影响）。
4. 理论题后续由对话/测验承载（本设计不涉及对话改造）。

## 4. 数据与存储

- localStorage：
  - `deeptutor_last_annotation_mode.<profileId>`（新，最后模态）
  - 现有 `deeptutor_last_annotation_task.<profileId>.<modal>` 复用
- 档案迁移：`profile_root/.migration-v1` 标记文件（新）。
- 无其它新持久化。

## 5. 明确不做

- 不引入 WebSocket 后端转发（问题 5 用前端共享状态，体验更好且无后端改动）。
- 不把理论题放进对话（问题 7 只做标注台过滤，对话承载后续专项）。
- 不改 AUTH 开启时的登录流程（问题 6 只在 AUTH 关闭场景引导）。

## 6. 测试

| 层 | 测试 |
|----|------|
| 后端 | migration 仅首次迁移（创建 A 复制/B 空）；`/tasks?practice_only` 过滤 |
| 前端单测 | 最后模态记忆、对象列表折叠状态 |
| 前端类型 | `npx tsc --noEmit` |
| 构建 | `npm run build` |
| 冒烟 | Playwright：新档案无旧会话；pro 解锁后可用；切页恢复任务；折叠对象列表；教练实时状态；首次访问出 /login；标注台无理论题 |

## 7. 实施顺序

1. 3.1 档案隔离（后端）
2. 3.7 实践题筛选（后端）
3. 3.2 专业模式联动（前端）
4. 3.3 任务自动保存 + 模态记忆（前端）
5. 3.6 首次访问引导（前端）
6. 3.4 对象列表折叠（前端）
7. 3.5 教练实时状态（前端，共享 store）

每阶段独立提交，不 push，直到用户确认。
