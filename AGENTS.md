# 标注星图项目协作说明（AGENTS.md）

本仓库是 DeepTutor 的数据标注教学分支，产品名“标注星图”。主路径是：学生选择学习档案 → 与标注教练对话 → 理论学习/测验 → 教学或专业标注 → 统一评分、报告、提醒与记忆。

## 当前状态（2026-08-15）

- 运行时只注册 `chat` capability；主 Persona 为 `annotation-coach`。教学能力通过 always-on 工具和受控扩展挂入 Chat 管道。
- 学生一级入口固定为「学习、实训、成长、我的」；模型、Embedding、知识库引擎、MCP、Skill、服务地址、密钥和运行日志不出现在学生页面。
- 一个系统账号可创建多个学习档案。每个档案使用 PIN 解锁，并分别保存对话、记忆、知识库、学习记录、标注草稿/提交和报告；教师只读访问不会写入学生记录。
- 标注页保留两条路径：统一 React 教学标注台用同一套外壳支持图片、文本、音频、视频和 9 类任务，草稿自动保存到当前档案；专业模式通过标注星图后端同源网关连接 Label Studio 1.23，不把服务 Token、隐藏身份密码或 LS Cookie 发给浏览器。**不再使用共享管理员账号或直接裸 iframe `localhost:8080` 描述专业模式**。
- 标注教练使用档案隔离的独立会话，能读取当前题、最近 5 次提交、已确认薄弱点和档案记忆摘要；头像可拖动并按思考、鼓励、提醒、成功、错误等状态切换。
- 对话可输出 Chart.js 图表、Mermaid 图和图片作品。数字图必须先由 `read_learning_chart_data` 生成当前档案的 `dataset_ref`，随后才能保存，模型不能直接填写来源或改写数值。`chart_designer`、`diagram_designer`、`illustration_designer` 是隔离上下文的专职子 Agent；实际生图使用管理员已配置的 imagegen 模型，并支持单次临时选择而不修改全局默认。
- 管理员工作台：`/admin` 聚合系统健康、初始化进度、统一任务中心与五中心入口；五中心为内容治理、教学配置、AI 能力、扩展与集成、系统运维。初始化向导为固定顺序可恢复状态机（账号安全/对话/Embedding/知识库/Label Studio/完整体检 + 可选生图/MCP/Skill），可跳过、恢复、重测；依赖配置变化自动降级 stale。
- 教师工作台 `/teacher` 只读展示被授权学生；代管需管理员发起、带理由与 scope、30 分钟自动失效并逐写审计，不修改原始证据。
- 扩展市场采用白名单策略：学生只能安装/启用 `grants.extensions` 白名单内扩展；未审核扩展默认禁用、仅开发模式可用，竞赛模式只加载固定白名单与锁定版本；高风险变更（扩展/MCP/allow_unverified Skill）需二次确认并记录版本与回滚日志。
- 学习数据页具备独立滚动容器；图表、记录、图谱和标注教练按需加载。生产构建与 gzip 路由预算已通过。

最近几轮实现记录见 `docs/superpowers/plans/2026-08-13-platform-upgrade-implementation.md`、`docs/superpowers/plans/2026-08-14-competition-readiness-vertical-optimization-implementation.md` 与 `docs/superpowers/handoffs/2026-08-14-competition-optimization-ai-handoff.md`；Label Studio 实测边界见 `docs/label-studio-1.23-capability-report.md`。

## 开发与启动

```powershell
# 一键：后端 8001 + 前端 3782 + 可选 Label Studio 8080
.\start_all.bat

# 手动后端
python -m uvicorn deeptutor.api.main:app --host 127.0.0.1 --port 8001

# 手动前端（必须指向 IPv4 后端）
cd web
$env:DEEPTUTOR_API_BASE_URL="http://127.0.0.1:8001"
npm run dev -- --port 3782

# 专业模式（可选）
.\start_label_studio.bat
```

专业模式配置规则：

- `LABEL_STUDIO_URL=http://127.0.0.1:8080`
- 本机环回地址默认只读发现 `data/label-studio/label_studio.sqlite3` 中的有效服务 Token，并在私有设置目录生成桥接密钥，不需要新手手工复制凭据；
- 远程或正式部署必须显式设置 `LABEL_STUDIO_API_TOKEN` 和 `LABEL_STUDIO_BRIDGE_SECRET`，不会尝试读取本地数据库；
- 可用 `LABEL_STUDIO_LOCAL_DB` 为隔离测试指定本机数据库，环境变量中的 Token/密钥始终优先。

Label Studio 只作为专业标注引擎和管理员管理台。学生从标注星图专业模式进入，不应看到或输入 Label Studio 账号；不要恢复已归档的 `label-studio-frontend` npm 包。

Windows 注意事项：

- 前端访问后端用 `127.0.0.1`，避免 `localhost` 解析成 `::1`。
- 若本机代理不可用，构建前清空 `HTTP_PROXY`、`HTTPS_PROXY`。
- PowerShell 运行中文测试输出可设置 `PYTHONIOENCODING=utf-8`。
- Next dev 同一 `.next` 目录只能启动一个实例；隔离验收可使用生产构建 `npm run start -- --port <端口>`。

## 架构与数据边界

```text
Web / WebSocket
  → FastAPI routers + multi_user context
  → DeepTutorApp.start_turn → ChatOrchestrator → AgenticChatPipeline
  → 标注教练总控 → 受限工具 / 专职子 Agent
  → 当前学习档案的私有数据根目录
```

关键模块：

| 模块 | 位置 |
|---|---|
| 学习档案、PIN、授权、迁移 | `deeptutor/services/learning_profiles/`、`deeptutor/api/routers/learning_profiles.py` |
| 当前用户/档案路径解析 | `deeptutor/multi_user/context.py`、`deeptutor/multi_user/paths.py` |
| 教学标注草稿与提交 | `deeptutor/services/annotation_attempts/`、`deeptutor/api/routers/annotation.py`、`web/components/annotation/UnifiedAnnotationWorkbench.tsx` |
| 专业模式网关与白名单 | `deeptutor/services/label_studio_gateway/`、`deeptutor/api/routers/label_studio_gateway.py` |
| 教练上下文 | `deeptutor/services/coach_context/` |
| 可信可视化 | `deeptutor/services/visualization_artifacts/`、`deeptutor/tools/learning_chart_data_tool.py`、`deeptutor/tools/visualization_artifact_tool.py` |
| 专职子 Agent | `deeptutor/tools/delegate_expert_tool.py`、`deeptutor/skills/builtin/annotation-coach-flows/references/experts/` |
| 能力中心与初始化向导 | `deeptutor/api/routers/capability_center.py`、`deeptutor/services/onboarding/`、`web/components/admin/AdminDashboard.tsx` |
| 管理员五中心与工作台 | `web/app/(admin)/admin/`、`web/components/admin/`、`web/lib/capability-routes.ts` |
| 教师工作台 | `web/app/(admin)/teacher/`、`web/components/teacher/TeacherDashboard.tsx` |
| 扩展白名单市场 | `deeptutor/services/extension_marketplace.py`、`deeptutor/multi_user/grants.py` |
| 真实用户测试证据 | `deeptutor/services/usability_study/`、`deeptutor/api/routers/usability_study.py`、`web/app/(admin)/admin/operations/usability/` |
| 性能指标与预算 | `deeptutor/services/performance_metrics/`、`scripts/measure_student_journey.py` |
| 学习报告与提醒 | `deeptutor/services/learning_communication.py` |
| 题库与课程资产 | `data/user/workspace/task_bank.json`、`competency_tree.json`、`web/public/images/` |

硬性边界：

- `learning_profile_id` 只表示学生学习档案，不能复用模型配置中的 `profile_id`。
- 所有学生私有读写必须通过当前用户和当前档案路径服务解析；不能拼接公共 `data/user` 路径。
- 诊断、日志、模型上下文和 API 响应不得包含 PIN 哈希、API Key、Label Studio Token/Cookie、隐藏身份密码或其他学生数据。
- Label Studio 项目、任务和 annotation-id 均须由服务端再次校验当前档案归属；隐藏导航不等于授权。
- 报告和提醒只能引用落盘事实。单次错误是 `unconfirmed`，只有重复且确认后才能称为稳定薄弱点。
- `VisualizationArtifact` 的数据图必须引用服务端生成的数据快照 `dataset_ref`；只写“来源”文字不算可信数据，且不得为了好看改数或补零。

## 工具、Skill、MCP 与扩展

`ALWAYS_ON_TOOLS` 的唯一来源是 `deeptutor/agents/_shared/tool_composition.py`。新增内置工具时至少同步：

1. `deeptutor/tools/builtin/__init__.py` 的导入、类型注册、导出及可配置集合；
2. `tool_composition.py` 的挂载策略；
3. 标注教练 Persona/Skill 的调用规则；
4. 注册测试、工具测试和一次对话冒烟。

学生扩展采用白名单市场，不能安装任意 URL、npm 包、命令或 MCP。Skill/MCP 的自定义来源和凭据仅是管理员高级配置；前端永远不回显秘密值。

## 验证基线

按改动范围先跑定向测试，再跑可行范围的整体验证：

```powershell
python -m ruff check <本次 Python 文件>
python -m pytest <本次相关测试> -q

cd web
npx tsc --noEmit
npx eslint <本次 TS/TSX 文件> --quiet
npm run build
npm run perf:check
```

浏览器验收至少覆盖：能力中心、学习档案锁、学习数据滚动、教学标注、专业模式降级、标注教练、图表切换；控制台不得出现 `Canvas is already in use`。涉及浏览器验证时按 Playwright skill 的服务器探测和临时脚本规则执行。

## Git 与工作树约定

- 用户已批准直接提交 `main`；本任务只 commit，不 push。
- 每个阶段做小而可回滚的中文提交，使用精确路径暂存，禁止 `git add .`。
- `docs/` 与 `data/` 默认被忽略；确需纳入版本控制时使用 `git add -f -- <精确文件>`。
- 工作树内 `.playwright-mcp/`、`.superpowers/`、`工具开发/`、`研究与学习/`、截图、脚本、竞赛文档等未跟踪内容属于用户，未经明确要求不得暂存、删除、移动或格式化。
- 禁止 `git reset --hard`、宽泛 checkout、清理未跟踪文件以及覆盖正式 Label Studio/学习数据。

## 当前交付重点

竞赛纵向优化的代码部分（任务 0.1–0.3、1.x、2.x、3.x、4.1–4.4 代码、5.1、5.2）已完成，覆盖：统一当前任务与四入口首屏、编辑权隔离与矩形框标注、草稿/正式修订与确定性评分、教材导入与混合检索、确定性对话编排与评测集、统一角色权限与 30 分钟代管审计、管理员五中心与教师工作台、可恢复初始化向导与扩展白名单、真实用户测试证据服务、竞赛就绪检查器与黄金闭环 E2E、性能预算机检。专业模式具备档案任务分配与低侵入未保存状态桥接；教学模式已迁移到统一 React 标注台。

**仍属人工验收/外部条件、不能由代码代跑**：

- 任务 0.4 内容审校的人工终审（高风险标准误引归零、正式题目来源可解析、随机抽 20 道题复核）；
- 任务 4.4 的真实用户执行：2 名学生 + 1 名职教教师完成优化前后两轮测试、知情同意签署、录屏/录音授权索引、报告数字与原始记录逐条核对；
- 任务 5.1/5.2 的竞赛电脑验收：从干净启动连续三次黄金演示、性能预算（冷启动 3s/页面切换 1s/成长首屏 2s/发送状态 300ms/首字 5s）的真实测量；
- 管理员轮换并重新输入真实模型密钥、配置并通过五项验收的 Embedding、有合法使用权的教材原文件、竞赛电脑或等效限速环境的最终测量。

最终测试命令与基线：

```powershell
# 后端
python -m ruff check deeptutor tests   # 基线 28 项错误（本次改动文件通过）
python -m pytest -q --ignore=tests/services/partners/test_channel_streaming.py
#   → 3723 passed / 12 skipped / 33 failed（33 项为可选依赖/POSIX/sandbox 差异，与基线一致）
# 前端
cd web
npx tsc --noEmit
npm run test:node                       # 334 项通过
npm run build
npm run perf:check                      # 全部路由在预算内
# 竞赛就绪与黄金 E2E
python scripts/competition_readiness_check.py --json
npx playwright test tests/e2e/golden-student-journey.spec.ts tests/e2e/degraded-services.spec.ts
#   → 11 项通过（需先起前端；可用 PW_BROWSER_CHANNEL 指向本机 Chrome）
python scripts/measure_student_journey.py --profile-root <档案根>
```

当前机器的 Embedding 与 imagegen 模型目录均未配置，因此能力中心必须显示“资料未索引/生图不可用”，不能伪造 ready 状态。管理员配置模型并通过连接测试后，才能把现有 60 篇资料真正索引、运行带引用问答，以及执行真实生图。不要再按旧文档把专业模式描述为直接 iframe `localhost:8080` 或让学生使用共享管理员账号。
