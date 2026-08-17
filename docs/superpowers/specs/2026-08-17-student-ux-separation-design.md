# 学生端易用性改造设计（角色分离 + 设置简化 + 标注台体验 + 文件子 Agent）

> 日期：2026-08-17
> 状态：设计已获用户批准
> 关联：`docs/superpowers/specs/2026-08-14-competition-optimization-design-index.md`（竞赛纵向优化）

---

## 1. 背景与目标

用户反馈 8 项体验问题，核心是**学生端与教师/管理员端没有完全分离**，以及标注台交互体验问题。经浏览器复现确认现状后，归类为三类：

| 类型 | 问题 |
|------|------|
| 架构：角色视图 | #1 学生能进入教师/管理界面（AUTH 关闭时所有人是 admin） |
| 架构：设置简化 | #2 学生看到全部管理设置（网络/模型/知识库/聊天/智能体/记忆） |
| 标注台体验 | #5 对象列表窄屏挤压图片 · #6 不记住上次任务 · #7 视频太小 |
| 架构：入口归属 | #8 能力中心/记忆/规范/定时任务出现在学生侧栏 |
| 增强 | #4 文件解析子 Agent（已有上传能力 + 子 Agent 专项解析） |

**明确不做**：#3 语音（已支持 STT/TTS，用户确认不动）。

## 2. 设计决策汇总（已与用户确认）

| # | 维度 | 决策 |
|---|------|------|
| 1 | 身份模型 | **方案 A**：引入"当前身份"概念，AUTH 关闭时也可切换学生/教师管理员 |
| 2 | 身份选择入口 | **仅登录页**：登录时选"学生 / 教师或管理员"，登录后固定身份 |
| 3 | 默认身份 | AUTH 关闭时默认**学生**（符合产品定位） |
| 4 | 切换身份 | **不提供登录后切换**（严格仅登录页），退出重登可换 |
| 5 | 教师/管理员 | **两个选项**："学生" / "教师或管理员"（/teacher 入口保留在管理侧栏） |
| 6 | AUTH 开启时 | **不变**：保留现有 admin/user 角色逻辑，登录页身份选择仅 AUTH 关闭时显示 |
| 7 | 文件子 Agent | **文件解析子 Agent**：上传后教练自动调用，返回结构化摘要与标注建议 |

## 3. 设计

### 3.1 身份模型（问题 1/8）

**核心**：AUTH 关闭时引入一个轻量"身份"选择，前端持久化，驱动导航与设置渲染。

- **登录页**（`web/app/(auth)/login/page.tsx`）：当 `fetchAuthStatus().enabled === false` 时，显示身份选择卡片："学生" / "教师或管理员"。选"学生"→ `/home`（学习空间）；选"教师或管理员"→ `/admin`（工作台）。身份写入 `localStorage`（键如 `deeptutor_view_identity`）。
- **身份存储**：`web/lib/view-identity.ts` 提供 `getViewIdentity(): "student" | "staff"`、`setViewIdentity(id)`。AUTH 开启时该模块返回 `"staff"`（或忽略，由真实角色决定）。
- **导航门禁**（`SidebarShell.tsx` / `StudentNavigation`）：
  - `view = "student"`：侧栏固定为学习/实训/成长/我的四入口，**移除**能力中心/记忆/标注规范/定时任务/设置管理入口。
  - `view = "staff"`：显示现有管理侧栏（含能力中心/记忆/规范/定时任务/设置）。
- **路由门禁**（`(workspace)/layout.tsx`、`(utility)/layout.tsx`、`RoleRouteGate`）：
  - 学生身份访问 `/memory`、`/standards`、`/tasks`、`/settings/*`（非外观）→ 跳转 `/home` 或显示拒绝页。
  - `/teacher` 已有登录门禁；学生身份下访问 → 跳转 `/home`。
- **关键**：这是**演示层身份**，不替代后端权限。后端 `policy.py` 仍是最终权威（竞赛边界不变）。AUTH 关闭时后端无真实用户，前端身份仅控制 UI 呈现。

### 3.2 设置页简化（问题 2）

- 学生身份下，`SettingsHub.tsx` 与 `settings-nav.ts` 的 `categoriesForRole("student")` 只返回**外观**（现状已如此），但需要确保：
  - 隐藏顶部 `SettingsStatusPanel`（系统状态卡）——仅 staff 显示。
  - 隐藏 `MigrationBanner`（"前往工作台"）——仅 staff 显示。
  - `(utility)/layout.tsx` 的 `StudentRouteGate` 已拦截非外观设置页；补充：学生身份访问 `/settings` 重定向 `/settings/appearance`。
- 学生"我的"页面改为简洁学生版：档案/PIN、外观、语音、提醒、退出（若该入口存在则精简）。

### 3.3 标注台任务记忆（问题 6）

`web/app/(workspace)/annotation/page.tsx`：

- **记住上次任务**：`useState` 初始化时从 `localStorage` 读取 `deeptutor_last_annotation_task`（键含当前档案 id，`getAnnotationBrowserSessionId` 风格）；`chooseTask` 成功时写入。
- 进入 `/annotation` 时：若有记住的任务且属于当前模态任务库 → 自动 `chooseTask` 加载，**不再显示"选择一项任务开始练习"占位**。
- 若记住的任务已不存在/不属于当前模态 → 回退占位。
- 清除：切换档案时清除该键。

### 3.4 标注台布局与视频尺寸（问题 5/7）

`web/components/annotation/UnifiedAnnotationWorkbench.tsx`：

- **视频**（`Media` 组件第 348 行）：`max-h-[400px]` → `max-h-[70vh] min-h-[280px]`，并给容器 `relative` 让视频居中显示完整。视频标注任务使用更大可视区，减少"显示不全"。
- **对象列表窄屏**（`BBoxEditor` 第 437-441 行）：将画布 `max-h-[600px]` 与折叠列表整合为**弹性布局**——画布区 `min-h-0` + `flex-1`，对象列表在窄屏以 `fixed` 底部抽屉或 `absolute` 右侧浮层呈现（不占画布纵向空间）。宽屏维持现有并排。
- 目标：任何窗口宽度下对象列表不遮挡图片主体。

### 3.5 文件解析子 Agent（问题 4）

复用现有 `DelegateExpertTool`（delegate 系统）+ 专家卡模式：

- **新增专家卡** `file-analyst`（`annotation-coach-flows/references/experts/file-analyst.md`）：负责解析上传文件——提取结构、总结要点、指出可标注实体/边界框候选、标注建议与陷阱。
- **工具链**：`EXPERT_TOOL_WHITELISTS` 给 `file-analyst` 开放受限工具：`read_file`、`exec_tool`（只读/解析）、`kb_search`（不开放写入/网络）。
- **触发**：教练对话中当学生上传文件/提到"分析这个文件/帮我看看这份文档"时，PERSONA 引导调用 `delegate_to_expert("file-analyst", ...)`。
- **输出**：结构化 Markdown 摘要（文件类型、结构、关键内容、可标注对象建议、风险项）。约束：不修改文件、不执行任意命令（仅解析命令白名单）。
- 学生上传体验保持现状（按钮/拖拽/粘贴），子 Agent 增强"看懂"层面。

### 3.6 身份与角色测试

- 后端无改动（身份是前端视图层）。
- 前端：`view-identity` 单测（默认学生、staff 切换、AUTH 开启忽略）；设置路由白名单测试；标注台任务记忆测试；`npx tsc --noEmit` + `npm run build`。

## 4. 数据与存储

- `localStorage`：
  - `deeptutor_view_identity`：`"student" | "staff"`（AUTH 关闭时使用）。
  - `deeptutor_last_annotation_task.<profileId>`：最近标注任务 id。
- 后端无数据迁移。

## 5. 明确不做

- 不做真实 parent 角色（share-design.md 的分享链接已覆盖"家长看成果"）。
- 不启用真实 AUTH 作为默认（保持本地单机便利）。
- 不替换 STT/TTS 引擎（问题 3 已确认）。
- 不在后端创建第二套角色判断（身份仅前端视图；后端 policy.py 不变）。

## 6. 测试

| 层 | 测试 |
|----|------|
| 前端单测 | `view-identity`（默认学生/staff/AUTH 开启忽略）、设置白名单、任务记忆 |
| 前端类型 | `npx tsc --noEmit` |
| 前端构建 | `npm run build` |
| 冒烟 | Playwright：AUTH 关闭选学生 → 侧栏四入口、设置仅外观、/teacher 拒绝；选教师 → 完整管理侧栏 |
| 标注台 | Playwright：选 task → 刷新 → 自动恢复上次任务；视频任务显示完整；窄屏对象列表不遮挡 |

## 7. 实施顺序

1. 身份模型（view-identity + 登录页选择 + 导航门禁）→ 3.1
2. 设置页简化（学生视角隐藏状态面板/迁移横幅）→ 3.2
3. 标注台任务记忆 → 3.3
4. 标注台布局（视频/对象列表）→ 3.4
5. 文件解析子 Agent → 3.5
6. 测试与验证

每阶段一个独立提交，不 push，直到用户确认。
