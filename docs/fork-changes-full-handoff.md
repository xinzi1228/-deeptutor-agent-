# DeepTutor Fork「标注星图」— 完整改动溯源交接文档

> 用途: 发给 AI 接力工作的**完整**文档。clone 后所有改动 + 借鉴了哪些 GitHub 项目/Skill + 具体怎么做的。
> 更新: 2026-08-04
> fork 起点: `43805736`（首个 fork 提交）之后共 **164 个提交**
> 远程: https://github.com/xinzi1228/-deeptutor-agent-.git（分支 main）

---

## 〇、一句话总览

DeepTutor（开源 AI 教学 Agent 平台）被 fork 并彻底改造为「**标注星图**」——一个面向数据标注工程师岗位的智能教学产品，参加科大讯飞 XA-202603 竞赛。clone 后做了 **164 个提交**：先从 5 个开源教育 Agent 项目 + EverOS + awesome-llm-apps 借鉴并落地 15+ 项教学能力，再完成竞赛 6 模块，最后做了多专家体系、界面全中文化、进度可视化、定时提醒、免登录分享、生成式 UI 等 10 项增强。

---

## 一、借鉴了哪些 GitHub 项目 / Skill

### 1.1 教育 Agent 项目（第一轮调研 `docs/agent-projects-review.md`）

| 项目 | 借鉴点 | 落地方式 |
|------|--------|---------|
| **aieducations/edumcp** | 学习者状态 MCP server | 已落地：`deeptutor/services/mcp/learner_server.py`（19 工具 + 7 资源） |
| **ahmedEid1/lumen** | 诊断 brief、可重跑建课、决策审计 | 落地：`brief.json` 诊断契约、`course_plan` 幂等建课、`log_decision` 决策审计 |
| **A-R007/Multi-Agent-Study-Assistant** | competency 前置依赖链 | 落地：`competency_tree.json` 加 prerequisites + `competency_map` 返回前置链 |
| **idoforgod/Vibe-learning-AgenticWorkflow** | Never-Answer 协议、双 SOT、3-Phase | 落地：回答以问题结尾、records 加 `scope` 字段、教学 3 阶段 |

### 1.2 记忆系统（`docs/everos-review.md`）

| 项目 | 借鉴点 | 落地方式 |
|------|--------|---------|
| **EverMind-AI/EverOS** | 分层记忆 + reflection 整理 | 落地：三层记忆（L1 轨迹/L2 摘要/L3 画像）+ `reflect` 整理端点 |

### 1.3 awesome-llm-apps（`docs/awesome-llm-apps-review.md`）

| 借鉴点 | 落地方式 |
|--------|---------|
| **Self-Improving Agent Skills**（三 agent 循环：测试→诊断→单点修复） | 落地：`improve_teaching_flow` 工具 + TeachingChangelog 教学自改进 |
| **Corrective RAG (CRAG)**（检索→相关性评分→改写重试） | 落地：RAG 检索后相关性校准 |
| **AI Teaching Agent Team**（教学组件独立交付物） | 落地：course_plan 导出学习手册 docx |

### 1.4 更早期借鉴（PERSONA 融合，`docs/borrowing-design.md`）

| 来源 | 借鉴点 | 落地 |
|------|--------|------|
| **feynman-tutor**（教学 Skill） | 意图分诊、事实vs推理、记忆确认前置、三层学习者笔记 | 落地：flow 文件 + PERSONA 记忆系统 |
| **universal-diagnostic-tutor**（Skill） | error_to_intervention、readiness_gate、understanding_check | 落地：decision-matrix.md 8 张决策表 |
| **education-agent-skills**（Skill） | Retrieve-First、渐进提示梯 L0-L5、Teach-Back | 落地：flow-theory |
| **teach / mattpocock**（Skill） | MISSION 驱动、lessons 单元、fluency vs storage | 落地：flow-onboarding |
| **synapse**（Skill） | confidence/source/pattern/correction 四维记忆 | 落地：learning records 字段 |
| **TradingAgents**（MetaGPT 家族） | 多角色对抗评估 | 落地：`evaluate_teaching_plan` 独立评估员 |
| **aetherviz-master**（Skill） | 3D 交互教学网页 | 落地：个人中心可视化 |

### 1.5 后期借鉴（最新几轮）

| 来源 | 借鉴点 | 落地 |
|------|--------|------|
| **msitarzewski/agency-agents** | agent 角色封装 + divisions.json 索引 | 落地：6 专家卡 + experts_manifest.json |
| **jnMetaCode/agency-orchestrator** | 验收自动核验 | 落地：auto_readiness F1 阈值判定 |
| **AG-UI 协议**（ag-ui-protocol，15.1k stars） | structured-message 生成式 UI | 落地：render_ui 工具 + quiz_card 交互卡片（**零框架依赖**，复用 chart 通道） |
| **FastGPT** | 免登录分享/嵌入、运行日志、定时任务管理 | 落地：shares 分享、trace-log 运营视图、cron REST |
| **OpenHands/RAGFlow/LobeHub** | 差距分析参照（`docs/maturity-gap-analysis.md`） | 指导功能优先级 |

---

## 二、clone 后的改动全貌（164 提交，按阶段）

### 阶段 1：fork 起点 — 标注教学核心（最早，`43805736` 起）

首个提交即建立了标注教学骨架：
- annotation-coach Persona（诊断优先苏格拉底教练）
- IOU/F1 检查工具（`annotation_check`）
- Canvas 标注工作台（web/public/annotation_tool.html）
- Label Studio 集成
- 记忆追踪

### 阶段 2：借鉴落地（~30 提交）

按 `borrowing-design.md` 落地 P0/P1 借鉴：
- 意图分诊/事实vs推理/记忆确认/三层笔记（改 flow + PERSONA）
- 教学法理论引用（VanLehn/Bloom/Chi/Flavell 进 PERSONA）
- CLI 教学命令（/resume /progress /concept-map /challenge）
- competency 前置依赖链
- 有界诊断 brief + 课程范围 RAG
- 学习者状态 MCP server
- 决策审计 + 对抗评估 + 教学自改进 + CRAG

### 阶段 3：竞赛 6 模块（~40 提交）

| 模块 | 关键实现 |
|------|---------|
| ①学习计划 | course_plan 4 模块 DAG + finalize_diagnosis + competency_map + job_analysis |
| ②会话管理 | 三层记忆 + 断点续学 + graph_query 风险链 |
| ③任务引导 | TeachingFlowEngine 6 步状态机 + teaching_flow 工具 + 像素校验 + task_bank 12 任务 |
| ④困难检测 | StruggleDetector 3 信号 + struggle_detect 工具 + 介入建议 |
| ⑤学习报告 | Progress 页全面板 + 对话内 4 类图表 + 打卡徽章 |
| ⑥练习批改 | annotation_check 5 题型 + grading 扩展 + 自动 readiness |

### 阶段 4：平台打磨（8/2-8/4，~60 提交）

见下文第三节（10 项增强，每项含实现方式）。

---

## 三、10 项增强（每项怎么做的）

### 1. 工作台裁剪 → 标注星图
**做法**：capability 白名单只留 chat（`builtin_capabilities.py` 移除 6 个通用能力注册）；persona 白名单只留 annotation-coach + 生产路径默认注入；前端删 9 个路由目录（book/co-writer/partners/playground/agents/knowledge/notebook/space/profile，~13.7k 行）；侧边栏裁 4 项；i18n 品牌替换为「标注星图」。

### 2. 多专家角色体系（借鉴 agency-agents）
**做法**：6 个专家角色 md（frontmatter name/description/color/emoji/vibe + 身份/使命/规则/能力/流程）放 `annotation-coach-flows/references/experts/`；`experts_manifest.json` 索引（divisions.json 风格）；`EXPERT_ROUTE` dict 阶段→专家 + `TeachingFlowEngine.expert_route()` + state 附带 expert；teaching_flow query 返回「路由专家」；`auto_readiness(f1)` F1→readiness_gate 判定写入 flow_state/metadata。

### 3. 界面全中文化
**做法**：改 4 处默认语言 en→zh（app-shell-storage 的 normalizeLanguage/readStoredLanguage、AppShellContext SSR useState、init.ts normalizeLanguage/fallbackLng）；zh locale 静态 import（首帧即中文）；后端 ui.language 默认 zh；扫描并补齐 **131 个未翻译 i18n key**（设置/聊天/记忆/标注页）；保留 en/zh 切换。

### 4. 进度页 Tab 化
**做法**：13 面板分 4 Tab（概览/记录/成就/图谱），`useState<Tab>("overview")` + TABS 数组驱动，数据仍单次 Promise.all 加载，默认概览一屏。

### 5. 教学轨迹（调用链运营视图）
**做法**：新增 `GET /api/v1/profile/trace-log` 聚合 records + decisions 成教学回合（±10 分钟邻近匹配介入/决策，倒序）；前端 Timeline 升级为可展开回合链（F1/readiness/卡住介入/推进决策）。

### 6. 教学流程面板（6 步状态图）
**做法**：新增 `GET /api/v1/profile/teaching-flow` 只读 flow_state.json；前端横向 6 步状态条（done 绿/in_progress 蓝/blocked 红/pending 灰）+ 专家路由 + 阻塞横幅。

### 7. 引用溯源（规范库 + 对话可点击）
**做法**：`GET /api/v1/standards` 从 annotation-guide skill references 读 5 个规范文档+章节；侧边栏「标注规范」库页；对话 `〔规范: 文档§章节〕` → remark 插件转 `standard:` 链接 → 前端拦截渲染 📖 chip → 点击 StandardDialog 弹窗原文；`parseStandardHref` 解码 percent-encoded href（markdown URL 编码问题）。

### 8. 定时学习提醒
**做法**：cron 工具已存在（schedule/list/cancel），补 8 项测试 + PERSONA 教 Coach 用；对话「30秒后提醒我」→ Coach 调 cron 注册 every-30s job → `execute_job` 到点用 Coach persona 生成教学提醒追加进会话。

### 9. 定时任务管理 UI
**做法**：`CronService.set_job_enabled` 新方法（启停持久化）；`deeptutor/api/routers/cron.py` REST API（GET/DELETE/PATCH，owner 隔离 chat:local-admin）；侧边栏「定时任务」页（卡片列表/启停/删除/空态）。

### 10. 免登录分享 + 生成式 UI
**分享**：`ShareStore`（token_urlsafe(16) + JSON 持久化 + 过期 + 撤销）；`POST /api/v1/shares`（鉴权）+ `GET /api/v1/share/{token}`（**公共路由**，token 白名单只读，安全前提：不暴露无鉴权的 get_session）；前端分享按钮 + 弹窗链接/iframe + `/share/[token]` 只读页；修复 Next.js 16 `params` Promise 需 `React.use()`。
**生成式 UI**：借鉴 AG-UI structured-message 思想，零框架依赖；`render_ui` 工具（`validate_component` 校验 quiz_card 结构 → metadata.chart）+ ChatChartCard 扩展 `quiz_card`（题目/选项/点击即时对错/解释）+ PERSONA 教 Coach 出题用。

---

## 四、当前状态

### 完成
- 竞赛 6 模块 ✅
- 3 优化（工作台裁剪/任务引导引擎化/打卡徽章）✅
- 10 项增强（见第三节）✅
- 界面全中文 ✅

### 未做
- **竞赛交付材料**（01报名表/02Demo说明/05合规/06材料包，9/1 硬要求）——素材在 docs/ 已齐全
- 语音 agent 循环（差距文档最后一项，需外部 STT/TTS）
- 小遗留：死代码残留英文 aria-label、热力图列顺序、course_plan task10-12 映射等

## 五、技术事实（接力必读）

- 工具注册：`builtin/__init__.py` + `tool_composition.py` always_on（现 16 个：15 教学 + render_ui）
- chart 契约：`metadata.chart = {type, data}`，从 tool_result 的 `metadata.tool_metadata.chart` 读取
- flow/PERSONA 有双副本（skill references + persona references / preset + workspace）需同步
- TeachingFlowEngine：`on_evaluated(task_id, f1, readiness=None)` 自动推进；flow_state 在 `data/user/workspace/learning/`
- 测试基线：2985 passed / 33 预存在失败（Windows 路径/GBK/可选依赖/sandbox）
- 启动：后端 `python -m deeptutor_cli.main serve --port 8001`；前端必须带 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`（解决 IPv6）；next build 需清 HTTP_PROXY/HTTPS_PROXY
- docs/ 被 gitignore，提交需 `git add -f docs/...`

## 六、给接力 AI 的提示词

> 这是 DeepTutor fork「标注星图」（数据标注教学 Agent，参加讯飞竞赛）。clone 后 164 提交：借鉴了 edumcp/lumen/Multi-Agent-Study-Assistant/Vibe-learning/EverOS/feynman-tutor/universal-diagnostic-tutor/agency-agents/AG-UI 等 10+ 项目与 Skill，完成竞赛 6 模块 + 10 项增强（多专家/全中文/进度可视化/教学轨迹/规范引用/定时提醒/定时任务/分享/生成式UI）。当前最紧要：**竞赛交付材料**（9/1 截止，素材在 docs/ 齐全）。全貌见 `docs/handoff-to-ai.md`，借鉴细节见 `docs/borrowing-design.md` + `docs/agent-projects-review.md` + `docs/everos-review.md` + `docs/awesome-llm-apps-review.md` + `docs/maturity-gap-analysis.md`，功能清单见 `docs/fork-features.md`。启动带 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`。
