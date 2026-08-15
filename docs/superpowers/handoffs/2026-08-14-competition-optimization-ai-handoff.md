# 标注星图竞赛纵向优化 AI 执行交接书

日期：2026-08-14

交接分支：`main`

编写时代码基线：`1abf9e7e`
用途：交给后续 AI 按阶段继续实现，不再依赖原聊天上下文

## 1. 接手前必读顺序

1. `../specs/2026-08-14-competition-optimization-design-index.md`
2. `../specs/2026-08-13-competition-readiness-vertical-optimization-design.md`
3. `../plans/2026-08-14-competition-readiness-vertical-optimization-implementation.md`
4. 当前任务对应的 2026-08-14 专项规格
5. 仓库根目录 `AGENTS.md` 及目标目录下更近的 `AGENTS.md`

不要从旧聊天、旧截图或更早计划推断当前能力。先运行 `git status --short`、`git log -15 --oneline`，再核对代码与测试。

## 2. 产品一句话

标注星图是面向职业教育数据标注学习的教学智能体：学生通过诊断、知识学习、教学标注/Label Studio 专业标注、教练反馈、评分订正和成长报告形成闭环；教师查看被分配学生并进行受审计的教学代管；管理员治理教材、AI、集成和系统。

## 3. 绝对边界

- 不重写项目，不更换 Next.js + FastAPI，不拆微服务。
- 不移除 Label Studio 专业模式，不长期维护 Label Studio 前端分叉。
- 不让学生登录 Label Studio 独立账号；管理员管理页和学生专业任务入口分开。
- 不允许 AI 自动发布教材、题目、评分规则或修改正式成绩。
- 不用前端隐藏代替后端权限，不允许 Agent 工具绕过 Store 授权。
- 不用模型生成或补齐图表数字，不用 Mock 结果冒充模型、Embedding 或 Label Studio 已连通。
- 不把密钥、PIN、Cookie、个人对话、标注正文写入日志、测试快照或提交。
- 不删除、移动、暂存不属于本任务的用户文件。

## 4. 当前已完成状态

| 阶段 | 结果 | 提交 |
|---|---|---|
| 0.1 性能基线 | 已实现匿名指标与测量基础 | `b98009b8` |
| 0.2 密钥与脱敏 | 已实现 secret 引用和脱敏基础 | `20630b50` |
| 0.3 内容治理 | 已实现来源、审核、版本基础 | `49cc4566` |
| 0.4 内容审校 | 已生成候选审校清单；人工终审不能视为完成 | `80e4a9b5` |
| 1.1–1.4 | 当前任务、前端上下文、四入口、聚合首屏 | `1819bb0b` 至 `8df87438` |
| 2.1–2.4 | 编辑权、矩形框、草稿/修订、评分订正 | `c4cc1e6b` 至 `5bde6619` |
| 3.1 | 教材转 Markdown 和结构化导入 | `7a633fde`、`d72de070` |
| 3.2 | 受限教材解析子 Agent | `b0e73cb2` |
| 3.3 | 混合检索与引用卡片 | `1abf9e7e` |
| 3.4 | 确定性对话编排与渐进回答 | `71b47835` |
| 3.5 | 可信可视化、40条标注教练评测集 | `d9b14c03` |
| 4.1 | 统一角色权限、30分钟代管与逐写审计 | `40ddb440` |
| 4.2 | 管理员五中心工作台、教师工作台与信息架构 | `98b2d2ca` |
| 4.3 | 初始化向导状态机与扩展白名单收口 | `163909f6` |
| 4.4 | 真实用户测试服务、报告与竞赛证据包 | `03dd8ef0` |

较早提交已实现可视化作品管理、生图模型选择、专家目录、教练会话隔离、专业模式桥接等基础能力。接手时必须重新核对代码；专项设计中列出的评测、可信数据、四入口共享和状态恢复仍以验收结果为准。

外部状态注意：代码“支持”不等于现场“已配置”。Embedding 的五项验收、生图真实付费调用、Label Studio 目标实例契约和真实用户测试需要在目标环境单独确认。

## 5. 剩余执行队列

### 任务 A：确定性对话编排

规格：`../specs/2026-08-14-deterministic-dialogue-progressive-answer-design.md`

重点文件：`deeptutor/agents/chat/agentic_pipeline.py`、新增 `deeptutor/services/teaching_orchestration/`、主对话前端和标注教练 persona。

交付：后端工具/时间预算、真实流式状态、取消重试、结构化渐进回答。禁止只改提示词。

### 任务 B：可信可视化与评测

规格：`../specs/2026-08-14-trusted-visualization-evaluation-design.md`

先审计现有 visualization/imagegen 提交，再补差距，避免创建第二套 Artifact。交付 40 条可重放案例、数据集哈希约束、完整作品生命周期、四入口一致消费和真实教练状态。

### 任务 C：统一权限与代管审计

规格：`../specs/2026-08-14-profile-authorization-impersonation-audit-design.md`

这是后续工作台与扩展市场的前置任务。必须覆盖 REST、WebSocket、Agent 工具、后台任务和 Store 直调。优先审计聊天、会话、记忆、收集箱、反思、笔记、题本、掌握路径、可视化和扩展写入口。

状态：已完成（`40ddb440`）。后续工作台必须复用 `deeptutor/services/authorization/policy.py`，不得在前端或新路由创建第二套角色判断。教师代管接口现在要求 `reason` 与 `scopes`；调用方必须显式提交，不得恢复无理由的一键代管。专项测试 62 项和学习档案 API 5 项通过。扩大回归的剩余失败属于可选依赖、Windows/POSIX 差异和旧基线，详见实施计划任务 4.1 末尾记录。

### 任务 D：角色工作台与初始化/扩展

规格：`../specs/2026-08-14-role-workspaces-onboarding-extension-design.md`

先后端授权，后前端导航。管理员五中心固定为内容治理、教学配置、AI 能力、扩展与集成、系统运维。学生不能自建、强制导入或任意执行工具。

状态：任务 4.2 已完成（`98b2d2ca`）、任务 4.3 已完成（`163909f6`）、任务 4.4 代码已完成（`03dd8ef0`），详情见本文件末尾交付记录。任务 4.4 的真实用户执行（2 名学生 + 1 名职教教师两轮测试）属人工验收，尚未进行。任务 5.1 至 5.3 尚未开始。

### 任务 E：真实用户测试

规格：`../specs/2026-08-14-user-testing-competition-evidence-design.md`

代码、协议与表单可由 AI 实现；参与者必须是真实的 2 名学生和 1 名职教教师。AI 不得代填原话、时间或评分。

### 任务 F：发布门禁

规格：`../specs/2026-08-14-release-readiness-gates-design.md`

补黄金 E2E、降级 E2E、竞赛体检、性能测量、全量回归和最终文档。最后在竞赛电脑连续跑三次主演示。

## 6. 每个任务的标准执行循环

1. 读取根与目标目录 AGENTS.md。
2. 查看工作树并列出用户已有改动；不覆盖、不清理。
3. 阅读对应专项规格和现有代码，写出差距清单。
4. 先补失败测试或可重复验收脚本。
5. 以最小文件范围实现，不顺手重构无关模块。
6. 运行专项测试、相关回归、格式与类型检查。
7. 检查 `git diff --check` 和敏感信息。
8. 只精确暂存本任务文件，独立提交。
9. 更新本交接书的状态表或新建任务交付记录，写明真实测试结果与未验证外部条件。

阶段验收门未过，不开始依赖它的下一任务。

## 7. 工作树保护

编写本交接书时存在以下未跟踪内容，视为用户资产，默认不得暂存、删除、移动或改名：

- `.playwright-mcp/`
- `.superpowers/`
- `annotation-pre-annotation.png`
- `coze_teach.txt`
- `scripts/analyze_coze.py`
- `工具开发/`
- `研究与学习/`
- `标注星图_团队分工与周报模板_v5.5.docx`

提交前使用精确路径 `git add`，不要使用 `git add .`、`git add -A` 或清理命令。

## 8. 数据与迁移规则

- 所有学生私有数据的键必须包含账号与学习档案。
- 原始对话、标注、初次成绩和测试原始记录不可覆盖，只能追加修订。
- 历史数据保留 ID 映射并迁入“原有学习档案”；迁移可重复执行并输出数量校验。
- 教材原文件是受控输入，结构化 Markdown 是解析事实，候选知识/题目不是正式内容。
- 正式内容以审核发布版本为准；缓存、图谱、报告和索引都可重建。
- 数字可视化以服务端数据集和哈希为准；展示层可重建但不得改变事实。

## 9. 外部服务停止条件

以下情况不要自行假设，明确记录为外部阻塞或受限状态：

- 没有真实模型密钥或用户未授权付费测试；
- Embedding 五项验收未通过；
- Label Studio 地址、管理员令牌或项目映射不可用；
- 缺少目标用户，无法完成真实用户测试；
- 教材版权或公开范围未确认；
- 需要删除正式数据或轮换生产密钥。

其余产品分歧按设计索引的推荐方案执行，不反复要求用户确认。

## 10. 全局测试建议

专项测试以各规格为准。阶段性至少运行：

```powershell
python -m ruff check deeptutor tests
python -m pytest -q
cd web
npx tsc --noEmit
npm run test:node
npm run build
```

构建可能重写 `web/next-env.d.ts`；若只是工具生成噪声且不属于任务，核对后恢复，不要混入提交。不要把开发服务器仍在运行当成构建成功。

## 11. 单任务交付模板

后续 AI 每次交付必须写：

```text
任务：
对应规格：
实现结果：
修改文件：
数据迁移：
测试命令与结果：
人工验收：
外部条件/未验证项：
安全与隔离检查：
提交号：
下一任务是否满足前置条件：
```

禁止用“应该可以”“基本完成”替代测试结果。没有运行的测试明确写“未运行”。

## 13. 任务 4.2 交付记录（2026-08-15）

```text
任务：4.2 管理员五中心与教师工作台（角色工作台的前端信息架构部分）
对应规格：docs/superpowers/specs/2026-08-14-role-workspaces-onboarding-extension-design.md
实现结果：
  - 管理员五中心路由：/admin/content（内容治理）、/admin/teaching（教学配置）、
    /admin/ai（AI 能力）、/admin/integrations（扩展与集成）、/admin/operations（系统运维）
  - /admin 工作台首页：聚合系统健康、初始化进度、统一任务中心（内容待审 / 教材导入
    失败 / 需复核）、五中心入口；保留七步初始化向导与脱敏报告下载
  - 教师工作台 /teacher：默认只读，仅展示被授权学生（teacher_view / impersonate）的
    当前任务、最近提交、问题与报告；无授权时显示解释性空态
  - (admin) 布局加入 RoleRouteGate 与 AdminNav：/admin/* 仅管理员，越权 URL 返回
    明确拒绝页；/teacher 仅要求已登录
  - 旧入口兼容：/capabilities、/settings/status 跳转 /admin；设置中心为管理员显示
    一次迁移提示；AdminLink 指向 /admin
  - capability-routes.ts 成为五中心、角色门禁、旧路由跳转与设置归类的唯一来源；
    settings-nav.ts 增加 center 归类
修改文件：
  - 新增 web/app/(admin)/admin/{content,teaching,ai,integrations,operations}/page.tsx、
    web/app/(admin)/admin/page.tsx、web/app/(admin)/teacher/page.tsx
  - 新增 web/components/admin/{AdminDashboard,AdminTaskCenter,AdminNav,AdminCenterShell,RoleRouteGate}.tsx、
    web/components/teacher/TeacherDashboard.tsx
  - 新增 web/tests/admin-information-architecture.test.ts
  - 修改 web/lib/capability-routes.ts、web/lib/settings-nav.ts、
    web/components/settings/SettingsHub.tsx、web/components/auth/AdminLink.tsx、
    web/app/(utility)/capabilities/page.tsx、web/app/(admin)/layout.tsx
数据迁移：无。教师工作台数据来自既有档案权限接口，未引入新的写入口。
测试命令与结果：
  - cd web; npm run test:node → 317 项通过（含新增信息架构测试 7 项）
  - npx tsc --noEmit → 通过
  - npx eslint <新增/修改前端文件> --quiet → 通过
  - npm run build → 编译成功；npm run perf:check → 全部在预算内
人工验收：未执行浏览器验收；需在目标环境确认五中心导航、越权 403、教师空态与迁移提示。
外部条件/未验证项：
  - 教师账号仍为 user 角色，后端没有“列出被分配学生”接口；教师工作台在无活跃
    teacher_view/impersonate cookie 时展示空态，不伪造数据
  - 内容治理、教材任务中心的实时计数依赖已存在的 admin API，未新增后端接口
  - Embedding 五项验收、生图真实调用与 Label Studio 契约需在目标环境单独确认
安全与隔离检查：
  - 前端门禁仅镜像后端角色策略；真实授权仍由 deeptutor/services/authorization/policy.py 执行
  - 任务中心只读取状态与计数，不读取对话正文、标注坐标或学生数据
  - 未暂存用户未跟踪文件；git diff --check 通过
提交号：98b2d2ca
下一任务是否满足前置条件：是。任务 4.3（初始化向导与白名单扩展收口）可在本工作台上叠加。
```

## 14. 任务 4.3 交付记录（2026-08-15）

```text
任务：4.3 初始化向导与白名单扩展收口
对应规格：docs/superpowers/specs/2026-08-14-role-workspaces-onboarding-extension-design.md
实现结果：
  - onboarding 升级为固定顺序可恢复状态机（deeptutor/services/onboarding）：
    账号安全/对话模型/Embedding/知识库/Label Studio/完整体检 6 个核心步骤 +
    生图/MCP/Skill 可选步骤；状态含 not_started/running/passed/failed/skipped/stale
  - 每步可 done/skip/resume/retest/dismiss；重启从第一个未通过/未跳过步骤继续；
    passed 记录依赖指纹，依赖配置变化自动降级 stale
  - capability_center 新增 GET/PUT /onboarding，兼容旧整数 payload，overview
    仍返回 onboarding；工作台初始化向导改用 step_key+action 协议
  - 扩展市场白名单收口：学生只能安装/启用 grants.extensions 白名单内扩展；
    安装新扩展为管理员操作；未审核扩展默认禁用、仅开发模式可用，竞赛模式只
    加载固定白名单与锁定版本（extension_policy.json）
  - 高风险变更需二次确认并记录版本/回滚：扩展安装/启用（confirmed）、MCP
    服务器变更（PUT confirmed + mcp_changes.jsonl）、allow_unverified Skill
    安装（confirmed + skill_changes.jsonl）
  - 前端 MCP 保存检测高风险变更并弹确认；onboarding-resume.ts 镜像后端状态机
修改文件：
  - 新增 deeptutor/services/onboarding/__init__.py
  - 修改 deeptutor/api/routers/{capability_center,mcp_settings,profile,skills}.py、
    deeptutor/multi_user/{grants,router}.py、deeptutor/services/extension_marketplace.py
  - 新增 web/lib/onboarding-resume.ts、web/tests/onboarding-resume.test.ts、
    web/tests/mcp-policy.test.ts；修改 web/lib/mcp-api.ts、
    web/app/(utility)/settings/mcp/page.tsx、web/components/admin/AdminDashboard.tsx
  - 新增 tests/api/test_onboarding_resume.py、tests/security/test_extension_marketplace_policy.py
数据迁移：无。onboarding 从 v1 整数 payload 迁移到 v2 状态机（legacy_int_to_key）。
测试命令与结果：
  - python -m pytest tests/api/test_onboarding_resume.py tests/security/test_extension_marketplace_policy.py -q → 35 项通过
  - 相关回归（capability/mcp/grants/profile/extension）103 项通过；
    全量 3713 passed / 12 skipped / 33 failed，33 项失败与基线完全一致（可选依赖、
    POSIX 专属、sandbox/win 差异），本任务未引入新失败
  - cd web; npm run test:node → 334 项通过（含 onboarding-resume 12 项、mcp-policy 5 项）
  - npx tsc --noEmit → 通过；eslint 新增文件 --quiet → 通过；npm run build → 编译成功；
    npm run perf:check → 全部在预算内
人工验收：未执行浏览器验收；需在目标环境确认向导步骤流转、高风险确认弹窗与
  白名单分配 UI（GrantEditor 的 extensions 字段）。
外部条件/未验证项：
  - extension_policy.json 竞赛模式与锁定版本需在目标环境配置后验证隔离
  - MCP / Skill 高风险确认需要真实服务器与 Hub 场景验证
  - 前端 GrantEditor 尚未暴露 extensions 白名单编辑（后端 grants 已支持）
安全与隔离检查：
  - 学生扩展写入按 grants.extensions 白名单执行；安装新扩展仅管理员
  - 未审核扩展默认禁用并隔离于竞赛配置；高风险变更强制二次确认
  - 日志/变更日志只记录扩展 id、动作、版本与前后快照，不含密钥或正文
  - 未暂存用户未跟踪文件；git diff --check 通过
提交号：163909f6
下一任务是否满足前置条件：是。任务 4.4（真实用户测试与竞赛证据包）可开始。
```

## 15. 任务 4.4 交付记录（2026-08-15）

```text
任务：4.4 真实用户测试与竞赛证据包（代码与服务部分）
对应规格：docs/superpowers/specs/2026-08-14-user-testing-competition-evidence-design.md
实现结果：
  - 新增 usability_study 服务：匿名参与者(S01/S02/T01)、知情同意
    (participate/screen_record/audio_record/quote/retention)、不可变 StudyRun、
    事件导入、人工修订历史(append-only)、删除请求审计
  - 确定性报告生成器：指标聚合、A/B 配对、中位数/范围、缺失值保留 null；
    拒绝规则覆盖非法参与者/缺同意/未知任务版本/事件时间倒序/指标引用不存在/
    哈希不匹配；草稿醒目标注“不可用于正式提交”
  - 删除后重算：排除参与者并升版本；人工修正保留原值/修正值/理由/操作者
  - 证据包导出：runs-index、metrics-summary、已批准原话、问题清单、源记录哈希，
    全部脱敏，录屏/录音不进入包内
  - 新增 /api/v1/usability-study 管理员路由（runs/events/corrections/deletions/
    issues/quotes/report/export）
  - 新增运维中心用户测试页 /admin/operations/usability（运行列表、报告摘要、
    草稿警告、证据包导出）
  - 新增竞赛文档：docs/competition/{usability-test-protocol,golden-demo-script,
    submission-checklist}.md
修改文件：
  - 新增 deeptutor/services/usability_study/{models,store,report,__init__}.py、
    deeptutor/api/routers/usability_study.py
  - 修改 deeptutor/api/main.py 挂载路由
  - 新增 tests/services/test_usability_report.py（10 项）
  - 新增 web/app/(admin)/admin/operations/usability/page.tsx；修改 operations 页
数据迁移：无。
测试命令与结果：
  - python -m pytest tests/services/test_usability_report.py -q → 10 项通过
  - 全量 3723 passed / 12 skipped / 33 failed；33 项失败与基线完全一致
    （可选依赖、POSIX/sandbox/win 差异），本任务未引入新失败
  - cd web; npx tsc --noEmit → 通过；eslint 新增/修改前端文件 --quiet → 通过；
    npm run test:node → 334 项通过；npm run build → 编译成功
人工验收：未执行。需真实完成 2 名学生 + 1 名职教教师的两轮测试，并随机抽查
  报告中的耗时、错误数和原话与事件记录及授权逐条核对。
外部条件/未验证项：
  - 真实参与者、知情同意签署与授权状态尚未录入
  - 录屏/录音文件与授权状态索引尚未建立
  - 竞赛电脑上的最终性能测量与三次黄金演示尚未执行（任务 5.x）
安全与隔离检查：
  - 仅存匿名编号；姓名/学号/学校/人脸不进默认证据包
  - 删除请求写入审计，报告重算并标记版本；原话仅导出已批准项
  - 路由 admin-gated；未暂存用户未跟踪文件；git diff --check 通过
提交号：03dd8ef0
下一任务是否满足前置条件：部分满足。代码/服务/文档就绪，但真实用户执行与
  证据录入是任务 4.4 的人工验收门，且任务 5.1 黄金演示 E2E 依赖竞赛环境。
```

## 12. 最终交付判断

最终完成不是“功能页面都存在”，而是：专业内容可信、学生主路径连续、教学和专业模式共享事实、AI 输出有来源和预算、权限不可绕过、三名真实用户证据完整、竞赛电脑连续三次完成黄金演示，并且文档准确说明外部依赖与已知限制。
