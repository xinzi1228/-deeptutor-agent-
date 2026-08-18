# 学习页与实训体验改造设计 v2（布局/继续/专业模式预载/标注台对齐/小助手侧边栏）

> 日期：2026-08-17
> 状态：设计（待用户审批）
> 关联：`docs/superpowers/specs/2026-08-17-student-ux-separation-design.md`（v1，已完成）

---

## 1. 背景与目标

v1（角色分离/设置简化/标注台任务记忆/文件子 Agent）已完成。用户继续提出 8 项体验优化，经澄清确认范围。本设计聚焦学习页布局、继续按钮、模态记忆、专业模式深度接入、标注台对齐 LS、小助手侧边栏。

## 2. 决策汇总（已与用户确认）

| # | 问题 | 决策 |
|---|------|------|
| 1 | 学习页输入框拥挤 | 学生首屏摘要区与输入框间距调大（窄屏） |
| 2 | 设置页保留项 | **待办**（用户跳过，之后单独讨论） |
| 3 | 继续按钮跳不到任务 | 携带 taskId 跳转，annotation 页读 query |
| 4 | 身份选择 | ✅ 已实现（登录页卡片 + localStorage） |
| 5 | 模态切换显示空态 | 按模态记住任务，切回自动恢复 |
| 6 | 专业模式正在加载 | 解锁后自动预加载 + 加载反馈优化 + 仅正式提交互通 |
| 7 | 标注台对齐 LS | 全类型对齐（大工程，单独计划） |
| 8 | 标注小助手太小 | 保留现尺寸 + 可放大右侧侧边栏（参考星辰 agent 客服） |

## 3. 设计

### 3.1 学习页输入框间距（问题 1）

**文件**：`web/app/(workspace)/home/[[...sessionId]]/page.tsx`（学生首屏部分）

- 学生首屏 `StudentHomeSummary` 容器当前 `items-center overflow-y-auto py-8`。
- 增大与输入框的间距：容器底部 padding 从 `py-8` 增至 `py-12`（或加 `pb-16`），并在空态下（无消息时）给摘要区加 `mb-6`。输入框 `pb-5` 保持不变。
- 目标：窄屏下摘要区最后一项与输入框之间有明确呼吸空间。

### 3.2 继续按钮携带 taskId（问题 3）

**文件**：`web/components/student-shell/StudentHomeSummary.tsx`、`web/app/(workspace)/annotation/page.tsx`

- `StudentHomeSummary` 的 `continueLearning()` 改为携带当前任务 id：
  ```ts
  const continueLearning = () => {
    if (task?.mode === "teaching_annotation" && task.taskId) {
      router.push(`/annotation?task=${encodeURIComponent(task.taskId)}&mode=teaching`);
      return;
    }
    if (task?.mode === "professional_annotation" && task.taskId) {
      router.push(`/annotation?task=${encodeURIComponent(task.taskId)}&mode=professional`);
      return;
    }
    onStartChat();
  };
  ```
  需要确认 `task` 对象暴露 `taskId`（查 CurrentLearningTaskContext 的 Value 类型）。
- `annotation/page.tsx` 增加 `useSearchParams()`：
  - 初始化 `mode` 从 `?mode=` 读取（teaching/professional/image/text/audio/video）。
  - 新增 `useEffect`：若 `?task=` 存在 → 直接 `chooseTask`（或 `chooseProfessionalTask`）选中该任务，不再依赖 localStorage。
  - 优先级：URL taskId > localStorage 记忆 > 空态。

### 3.3 按模态记住任务（问题 5）

**文件**：`web/app/(workspace)/annotation/page.tsx`

- 扩展 localStorage 键：`deeptutor_last_annotation_task.<profileId>.<modal>`（modal 取 image/text/audio/video）。
- `chooseTask` 成功时写入当前模态的键。
- `switchMode` 切换时：从目标模态的键读取，若存在且任务存在 → 自动 `chooseTask`；否则保持空态。
- 兼容：保留旧键 `deeptutor_last_annotation_task.<profileId>` 作为默认（image 模态回退）。

### 3.4 专业模式深度接入（问题 6）

**目标**：解锁后自动预加载，点进专业模式秒开；两种标注台正式提交互通。

**3.4.1 后端：准备就绪状态 + 预加载接口**

- `deeptutor/api/routers/label_studio_gateway.py`：
  - `/status` 增强：返回当前档案的专业任务准备状态（`{ available, ready_count, total_count, prepared_tasks: [...] }`）。准备状态指该档案的 LS 项目已创建、题目已导入、URL 可访问。
  - 新增 `POST /api/v1/label-studio/preload`：为当前档案准备**所有**已分配任务（批量 ensure_task，幂等——已准备则跳过），返回 `{ ready: bool, task_urls: {...} }`。
  - 现有 `POST /prepare/{taskId}` 保留（单任务准备），改为优先返回已缓存 URL。

**3.4.2 前端：解锁后自动预加载**

- 档案解锁成功事件（ProfileLockBanner / CurrentLearningTaskContext 监听）后，annotation 页（或解锁流程）自动调 `POST /preload`（fire-and-forget，不阻塞 UI）。
- annotation 页 `mode === "pro"` 时：
  - 读取 `/status` 的 `ready_count`，已准备任务直接显示（含 URL），不再逐次 prepare。
  - 隐藏 iframe 预载：`mode !== "pro"` 时若已解锁且档案有任务，渲染一个 `<iframe src={firstReadyUrl} className="hidden" aria-hidden>` 预加载 LS 前端（main.js 等缓存到浏览器）；切到 pro 时隐藏 iframe 变为可见 iframe（复用同一 src），秒开。
- 加载反馈优化：
  - `professionalLoading` 期间显示阶段提示（"准备 Label Studio 项目…/导入题目…/加载工作台…"）。
  - 加"取消"按钮（取消本次 prepare，保留已完成的）。
  - 若 prepare 超过 15s → 显示重试 + 诊断信息（token/服务状态）。

**3.4.3 任务互通（仅正式提交）**

- 确认现有同步方向完整：
  - 自建台正式提交 → 写 attempts（`/api/v1/annotation/attempts`）。
  - LS 标注 → `POST /sync/{taskId}` 拉回 LS annotation → 写同一 attempts。
  - 两模式读同一 attempts 显示结果/评分。
- 补缺口：LS 正式提交后，自建台应能读到该提交（反之亦然）——确认 attempts store 是同一实例、评分规则一致。若 LS 提交后自建台旧草稿与新正式提交冲突，以正式提交为准（草稿标记 stale）。

### 3.5 标注台对齐 LS（问题 7）—— 单独计划

**范围**：全类型对齐（bbox 优先，其余类型跟进）。此为独立大工程，**本设计只列方向，不写实现细节**：

- 对齐维度：工具栏布局（左侧标签面板/顶部工具/中央画布）、快捷键体系、区域编辑（选中/移动/缩放）、标签颜色、撤销重做、图像缩放平移、对象列表样式。
- 建议拆为专项计划：`2026-08-17-annotation-alignment-ls-design.md`（单独 brainstorming + 计划）。

### 3.6 标注小助手侧边栏（问题 8）

**文件**：`web/components/annotation/AnnotationCoach.tsx`

- 保留现有"可拖动小气泡 + 340×440 面板"为**默认收起态**。
- 新增"放大为侧边栏"按钮（面板头部）：点击后从右侧滑出**全高侧边栏**（`fixed inset-y-0 right-0 w-[360px]`，带 translate-x 过渡动画，参考星辰 agent 客服）。
- 侧边栏模式下：隐藏小气泡，面板占满右侧高度，消息区自适应；再次点击收起图标回退小面板。
- 移动端：保持现有全宽底部弹层。
- 实现要点（已确认自包含组件，成本低）：
  - 容器定位从 `right/bottom` 改为 `inset-y-0 right-0`（侧边栏态）。
  - 与 `BboxObjectList` 窄屏浮动抽屉（`fixed bottom-4 right-4`）叠放：侧边栏 z-50 会盖住，需确认不冲突或提高对象列表 z。
  - 拖动逻辑在侧边栏态禁用。

## 4. 数据与存储

- localStorage：
  - `deeptutor_last_annotation_task.<profileId>.<modal>`（按模态）。
  - 旧键 `deeptutor_last_annotation_task.<profileId>` 兼容保留。
- 后端：无新持久化（LS 项目/任务映射已在 `annotation/label_studio_map.json`）。

## 5. 明确不做（本设计）

- 问题 2（设置保留项）——待办，后续单独讨论。
- 问题 7（全类型对齐 LS）——单独专项计划。
- 不启用真实 AUTH 作为默认。
- 不替换 LS 本身（仍经同源网关代理）。

## 6. 测试

| 层 | 测试 |
|----|------|
| 前端单测 | 模态任务记忆、继续按钮 taskId 逻辑 |
| 前端类型 | `npx tsc --noEmit` |
| 前端构建 | `npm run build` |
| 后端 | `pytest`（label_studio_gateway 预加载接口幂等） |
| 冒烟 | Playwright：继续按钮跳对应任务；切模态恢复任务；pro 秒开；小助手放大侧边栏；无 `Canvas is already in use` |

## 7. 实施顺序

1. 3.1 学习页间距（小）
2. 3.2 继续按钮 taskId（中）
3. 3.3 按模态记住任务（中）
4. 3.4 专业模式预加载（大，含后端+前端）
5. 3.6 小助手侧边栏（中）
6. 3.5 标注台对齐 LS → 单独计划
7. 问题 2 设置保留项 → 待办

每阶段一个独立提交，不 push，直到用户确认。
