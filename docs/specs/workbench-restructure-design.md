# 「标注星图」工作台彻底改造设计（Workbench Restructure）

> 状态: 设计已获用户批准
> 日期: 2026-08-02

---

## 1. 背景与目标

DeepTutor fork 被改造成「数据标注教学平台」。此前功能为**增量叠加**（annotation-coach persona + 14 个教学工具 + 知识图谱 + 对话可视化 + 困难检测介入），但产品外壳仍是通用 DeepTutor 工作台——侧边栏 11 项导航、7 个通用 capability、4 个 persona、品牌「DeepTutor」。

**本次改造目标**：彻底移除无关通用功能代码，把产品外壳重塑为「**标注星图**」数据标注教学 Agent 产品——启动即进入标注教学，仅保留教学相关页面/能力/角色，品牌更名。

**借鉴来源**（GitHub 调研 + 本地 skill）：
- `AccurateDataAnnotator/accurate-data-annotator` — 标注训练平台流程（注册→筛选→训练→证书→资源库），专注式布局
- `CAHLR/OATutor`、`HugeCatLab/ChatTutor` — 教学应用 UI
- `exampass` skill — 双 tab 布局 + kc_mastery 掌握度可视化
- DeepTutor 自身 — Home(会话)/Annotation(标注)/Progress(进度/图谱)/Memory(三层记忆)

**关键结论**：GitHub 无成熟的「标注教学专用工作台」开源项目——本设计为原创。内置通用能力（deep_solve/visualize/mastery_path 等）面向通用 AI 教学，对标注教学适用性低，且已有自建替代（chart_cards/course_plan/annotation_check）；内置 **chat 底座**（agentic loop/streaming/记忆/RAG/工具调度）必须复用。

## 2. 设计决策汇总（已确认）

| # | 维度 | 决策 |
|---|------|------|
| 1 | 实现方式 | 彻底裁剪（非可配置开关）：删除 9 个路由目录 + 导航裁剪 + UI 入口裁剪 + 品牌重塑；**被保留页面依赖的共享组件代码保留**（避免 ts 崩溃） |
| 2 | 前端保留页面 | Home / Annotation / Progress / Memory / Settings + 认证页(login/register) + admin(管理后台) |
| 3 | 前端移除页面 | book / co-writer / partners / playground / space / agents / knowledge / notebook / profile |
| 4 | 后端 capability | 只保留 `chat`，移除 6 个通用能力注册 |
| 5 | 工具 | 全部保留（含 web_search/brainstorm/paper_search/reason——reason 是 struggle_detect 依赖） |
| 6 | persona | 只留 `annotation-coach`，固定为默认（不可切换） |
| 7 | 默认路由 | 登录/启动后 → `/home` |
| 8 | 品牌 | 改产品名「标注星图」，替换 i18n 文案；logo 保留现有或后续换 |

## 3. 前端改造

### 3.1 路由移除

**删除目录**（Next.js App Router route groups）：

```
web/app/(workspace)/book/
web/app/(workspace)/co-writer/
web/app/(workspace)/partners/
web/app/(workspace)/playground/
web/app/(utility)/agents/
web/app/(utility)/knowledge/
web/app/(utility)/notebook/
web/app/(utility)/space/
web/app/(utility)/profile/
```

**保留目录**：

```
web/app/(workspace)/home/
web/app/(workspace)/annotation/
web/app/(workspace)/progress/
web/app/(utility)/memory/
web/app/(utility)/settings/
web/app/(auth)/login/  web/app/(auth)/register/
web/app/(admin)/admin/
```

**约束**：删除路由目录前，先 grep 被保留页面/共享组件对这些目录的引用，确保无断裂导入。共享组件（components/ 下）仅删除被移除页面独占的部分，其余保留。

**重要发现（决定裁剪粒度）**：保留页面（Home/Memory）深度依赖待移除功能的共享组件——`ChatComposer`/`ChatMessages` 引用 book/space/notebook/agents/partners 选择器；`MemorySection` 渲染这些实体跳转。因此裁剪策略为：**删除路由目录（页面不可达）+ 导航裁剪 + 保留页面内 UI 入口裁剪 + 品牌重塑，共享组件代码保留**。

### 3.1a 保留页面内的 UI 入口裁剪

- `MemorySection.tsx`（Memory 页）：移除 co-writer/book/partners/space/knowledge 实体跳转分支（保留 session/home 相关）
- `SessionActivityPanel.tsx`（Home 会话活动面板）：移除 space 路由链接
- `ChatComposer`/`ChatMessages`：移除 book/space/notebook/agents/partners 选择器入口（ChatSpaceMenu/MyAgentsPicker/BookReferencePicker/QuestionBankPicker），教学会话不需要附加上下文选择
- 共享组件文件本身保留（不物理删除，避免破坏其他引用），仅停止在 UI 中渲染/引用

### 3.2 侧边栏导航

`web/components/sidebar/SidebarShell.tsx`：

- `PRIMARY_NAV` 只留: `/home`(House) `/annotation`(Tag) `/progress`(TrendingUp)
- `SECONDARY_NAV` 只留: `/memory`(Brain) `/settings`(Settings)
- 删除 Partners/My Agents/Co-Writer/Book/Learning Space/Memory→副导航调整 等条目
- 移除 `requires: "llm"` 门控逻辑可保留（仅 Home 用），或简化——实现时按最小改动保留现有门控结构

### 3.3 默认路由

- 登录成功后跳转 `/home`（认证回调逻辑）
- 未登录访问受保护页 → `/login`
- 访问已移除路由 → 404（Next.js 自动，因目录已删）或重定向 `/home`（可选，实现时验证）

### 3.4 品牌「标注星图」

**i18n 文案替换**（机械批量）：
- `web/locales/zh/app.json` + `web/locales/en/app.json`：所有含 "DeepTutor" 的 value 替换为「标注星图」（zh）/ "Annotation Star Map"（en）
- **保留 i18n key 不变**（key 是英文原文，只改 value），避免破坏 `t()` 引用
- 只替换面向用户的主要文案；技术配置类文案（如"DeepTutor 服务进程"）可保留或替换——实现时以"用户可见品牌文案必须替换，技术内部文案可保留"为原则

**其他品牌位置**：
- `web/app/layout.tsx`：`title: "DeepTutor"` → `"标注星图"`
- 登录页 `(auth)/login`：欢迎文案/logo alt
- `SidebarShell` banner/logo alt、footer 链接（Docs/GitHub 保留可访问性）
- `(admin)/admin/users/page.tsx`："DeepTutor Admin · User Management" → "标注星图 管理后台 · 用户管理"
- favicon/apple-touch-icon/logo：保留现有图片（后续可换）

## 4. 后端改造

### 4.1 capability 白名单

`deeptutor/runtime/bootstrap/builtin_capabilities.py`：

```python
BUILTIN_CAPABILITY_CLASSES: dict[str, str] = {
    "chat": "deeptutor.agents.chat.capability:ChatCapability",
}
```

移除 `deep_solve` / `deep_question` / `deep_research` / `math_animator` / `visualize` / `mastery_path` 六个注册项。

**约束**：
- 六个能力类**文件保留**（避免大范围删除破坏依赖），仅移除注册
- 先 grep 后端对这六个 capability 名的引用（CLI 默认、前端 capability 选择、tests），确保移除注册不破坏现有功能
- 若 tests 依赖这些 capability 注册（如 CLI 测试跑 deep_solve），调整测试或保留其可用性——实现时评估

### 4.2 persona 白名单

`deeptutor/services/persona/presets/`：

- 只保留 `annotation-coach/` 目录，删除 `peer/` `research-assistant/` `teacher/`
- 默认 persona 固定为 `annotation-coach`（服务层默认值 + 前端 persona 选择 UI 移除/固定）

**约束**：
- grep 对 `peer`/`research-assistant`/`teacher` persona 的引用（前端 space/personas 页面将被移除，但后端可能有默认值）
- 保留 `annotation-coach` 在 workspace 的运行时副本（`data/user/workspace/personas/annotation-coach/`）——该副本含规则 12（struggle_detect），若存在必须保留

### 4.3 工具

全部保留，不改注册。`reason` 是 `struggle_detect` LLM 解释层的依赖，不可移除。

## 5. 风险与边界

| 风险 | 缓解 |
|------|------|
| 删除路由目录破坏共享组件导入 | 先 grep 引用再删；tsc 校验 |
| 移除 capability 注册破坏后端引用/tests | 先 grep 依赖；保留类文件；回归测试 |
| i18n 大量替换不完整/不一致 | 替换后 grep 残留 "DeepTutor" 校验 |
| persona 删除影响 workspace 运行时副本 | 保留 annotation-coach 副本 |
| 前端中间件/重定向逻辑依赖移除路由 | 实现时验证 404/redirect |
| ChatComposer/Memory 裁剪破坏保留页交互 | 小步编辑 + tsc + 手动冒烟 |

## 6. 验证策略

1. 前端 `cd web; npx tsc --noEmit` 通过（0 错误）
2. 前端构建 `npm run build`（可选，慢）
3. 后端全量测试回归 `python -m pytest tests/ -q`（或受影响子集）
4. 手动冒烟：启动服务 → 登录 → 默认进 /home → 侧边栏仅 4 项 → 访问移除路由 404
5. grep 品牌残留："DeepTutor" 仅剩技术内部文案（可接受清单）

## 7. 实施任务划分（供 writing-plans 细化）

1. 前端路由移除（9 个目录）+ 共享组件引用清理
2. 侧边栏导航裁剪（SidebarShell）
3. 默认路由 + 认证跳转
4. i18n 品牌替换 + layout title + 登录页 + admin
5. 后端 capability 白名单（builtin_capabilities.py）+ 依赖检查
6. 后端 persona 白名单 + 默认固定
7. 全量回归 + 前端 tsc + 手动冒烟
8. 文档同步（README/fork-features/交接文档更新产品名）
