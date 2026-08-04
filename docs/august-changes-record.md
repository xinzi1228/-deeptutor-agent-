# 「标注星图」8 月改动完整记录（2026-08-01 至 08-04）

> 用途: 发给 AI 接力工作的专项文档。8 月 1 日起共 **130 提交**，是 fork 后最核心的工作。
> 更新: 2026-08-04 | 上游: HKUDS/DeepTutor | 远程: https://github.com/xinzi1228/-deeptutor-agent-.git
> 借鉴来源汇总: lumen / edumcp / Multi-Agent-Study-Assistant / Vibe-learning / EverOS / awesome-llm-apps / agency-agents / TradingAgents / feynman-tutor / AG-UI / FastGPT / RAGFlow / OpenHands / LobeHub

---

## 目录
1. [8/1：借鉴落地 + 知识图谱 + 回归（44 提交）](#1-81-借鉴落地--知识图谱--回归)
2. [8/2：竞赛 3 大块 + 多专家体系 + 死代码清理（56 提交）](#2-82-竞赛-3-大块--多专家体系--死代码清理)
3. [8/3：全中文 + 进度可视化 + 引用溯源 + 定时提醒（28 提交）](#3-83-全中文--进度可视化--引用溯源--定时提醒)
4. [8/4：定时任务管理 + 分享 + 生成式 UI（30 提交）](#4-84-定时任务管理--分享--生成式-ui)

---

## 1. 8/1：借鉴落地 + 知识图谱 + 回归（44 提交）

### 1.1 借鉴落地（P1/P2，参照 `docs/agent-projects-review.md` + `docs/borrowing-design.md`）

| 提交 | 借鉴来源 | 落地内容 |
|------|---------|---------|
| `694c1165` | 标注教练进阶 | 学习记录持久化 + 个人中心仪表盘 + 开源 Agent 借鉴起点 |
| `e9cc43f5` | lumen / Multi-Agent / Vibe | **P1**: 前置依赖链、教育学自检、有界诊断 brief、课程范围 RAG |
| `e32894fd` | **EDUMCP** | P2-1 学习者状态 MCP server（19 工具 + 7 资源） |
| `82bcecaf` | **lumen** | P2-2 可重跑建课（幂等模式） |
| `19c0ed40` | **feynman** | P2-3 IOU 交互演示工具（可视化转交） |
| `87416e2a` | **lumen** | P2-4 决策审计（可追溯推荐理由） |
| `2f44656b`+`17b84b4e` | **TradingAgents** | 对抗性教学方案评估工具（多角色辩论）+ 前端集成 |
| `9eb1b72f` | Label Studio | 实机验证修复 3 个 bug |
| `940acc6e`+`efd9922c` | **EverOS** | 记忆进化 Reflection + foresights 预测验证闭环 + episodes 时间线 + atomic facts |
| `0143de71` | **awesome-llm-apps Self-Improving** | 教学流程自改进循环（TeachingChangelog） |
| `4c08ea40` | **awesome-llm-apps CRAG + Teaching Team** | CRAG 相关性校验 + 学习路径手册 docx |
| `f2ef0958`+`5e613103` | **agency-agents** | Coach 成功指标 + 角色氛围 |

### 1.2 学习者知识图谱（8 任务，借鉴 cognee ECL/GraphRAG）

| 提交 | 内容 |
|------|------|
| `6aea0487`+`0e27d6b7` | 设计 + 计划（借鉴 cognee ECL/GraphRAG 模式） |
| `33ae2d86` | `KnowledgeGraphStore.build` 确定性全量建图（本体种子 + 掌握/挣扎） |
| `f61d8540`+`82535d00` | 边冲突最新优先 + `incremental_update` 增量更新（幂等/重分析） |
| `72694d4a` | `GraphQueryService` 确定性图查询（risk_path/concepts/mastery） |
| `5632250e`+`3635c9fd` | `GraphQueryTool` 图查询 Coach 工具 + LLM 解释层 + 延迟加载 + 高风险才解释 |
| `0fecd6bb`+`771747dc` | 注册 graph_query 为**第 12 个 always-on 教学工具** |
| `a45af985`+`0f0a40ed` | write_learning_record 落盘后增量更新图谱（失败降级） |
| `f891669a` | MCP 暴露 get_knowledge_graph / query_risk_path |
| `0b1d509f` | 知识图谱可视化面板 + Label Studio 嵌入 pro 模式 |

### 1.3 回归修复 + 文档

- `4eed12c0` kp→技能别名映射 + 真实数据 risk_path 覆盖
- `b79a178a` 回归发现：Coach 多轮对话漏落盘 → 工具结果附记录提醒
- `d70ef05f` 补全诊断落盘 → finalize_diagnosis 工具（brief+建课）
- `ec47aca4`/`60091e8f`/`f27eafc0` fork 功能清单（前端可见/大白话/详细 18 项）
- `f84434c3` 整体回归演示报告

## 2. 8/2：竞赛 3 大块 + 多专家体系 + 死代码清理（56 提交）

### 2.1 对话内可视化（竞赛模块⑤，9:51 起，8 任务）

| 提交 | 内容 |
|------|------|
| `54eaa461`+`068fa2d7` | 设计 + 计划 |
| `556ab278`+`e49432ed` | chart 契约构造器 + matplotlib 成绩单 PNG（CJK 字体 + 降级） |
| `a3cc2983` | annotation_check 评测后生成成绩单 PNG + chart 元数据 |
| `6430fa5f` | `ability_radar` 能力雷达工具 |
| `4ccc8d5f` | finalize_diagnosis 返回学习进度 chart |
| `18cdc4bf` | graph_query 风险链返回图谱 chart（cytoscape 契约） |
| `58b26d1d`+`12895b50` | 前端 ChatChartCard 组件 + AssistantMessage 渲染图表卡 |
| `18a95579` | 成绩单图标题 CJK glyph 修复 |
| `e8c9094c` | 修复 chart 数据从 tool_result 事件读取（metadata.tool_metadata.chart） |

### 2.2 困难检测介入（竞赛模块④，11:39 起，10 任务）

| 提交 | 内容 |
|------|------|
| `3f6a6d5a`+`c98300da` | 设计 + 计划 |
| `28e06ab9`+`47c6cc57` | `StruggleDetector` 确定性 3 信号（连续低分/错误重复/停留超时）+ tz 归一 |
| `33098e0f` | intervention_suggestion 信号→介入建议映射（对接 readiness_gate） |
| `0f924ed7` | `StruggleDetectTool` + LLM 解释层（失败降级） |
| `377c3cd4` | 注册 struggle_detect 为**第 14 个 always-on** |
| `1f268415`+`9f5790ce` | 接入教学流程协议 + PERSONA 规则12 |
| `86cc7f56`+`b5656329` | log_decision 支持 struggle_intervention kind + 前端卡住介入标签 |
| `e417ffc2` | 检测器异常降级为无信号 |

### 2.3 工作台裁剪 → 标注星图（12:55 起，8 任务）

| 提交 | 内容 |
|------|------|
| `877237a3`+`176a32cf` | 设计（竞品空白领域原创）+ 计划 |
| `c89537c3`+`39d6c3a8`+`bb28b73d` | capability 白名单只留 chat + persona 白名单 + 默认注入 |
| `da926980`+`f2e64107`+`860c835f`+`8fafbdfd` | 删 9 路由目录 + 侧边栏裁 4 项 + 保留页入口裁剪 + 移除死链接 |
| `a6bce17b` | 恢复附件上传 + 清理 ChatComposer 死 props |
| `45e885b6`+`9482cf98`+`f8317e67`+`0af5ed78` | 品牌替换「标注星图」+ CLI 文档清理 + Home 选择器只留 chat |

### 2.4 任务引导引擎化（竞赛模块③，16:46 起，14 任务）

| 提交 | 内容 |
|------|------|
| `c1350bf1`+`ff9bfba8` | 设计 + 计划（状态机 + 像素校验 + 题型扩展） |
| `c6d45a30`+`da0bbe90` | `TeachingFlowEngine` 6 步状态机（gate+阻塞报告+flow_state 默认持久化） |
| `75f6584f`+`75f1e293` | `teaching_flow` 工具（query/advance/reset + start_task/block + 下一步提示），**第 15 个 always-on** |
| `c2ee714d`+`2465db1a`+`67bc2476` | annotation_check 像素校验（贴边/重叠/紧致度，无 GT 启发式） |
| `3e6f7e6e`+`fb6db6c1`+`72713959` | 新题型评测（judgment/standard/error_case） |
| `d70a762e`+`bdcc0d85` | grading 题型扩展（tf/规范/错误案例，fail-closed） |
| `08239c59`+`7648b2dc`+`d94a789f` | task_bank task10-12 + annotation_check task_id 自动推进 + flow 协议对齐 |

### 2.5 打卡徽章引擎（19:37 起，6 任务）

| 提交 | 内容 |
|------|------|
| `aec81539`+`4633eee6` | 设计 + 计划（从 learning records 派生） |
| `072c2669`+`74089145`+`24a42aa6` | `AchievementService` 打卡 + 6 徽章（确定性派生 + fallback + 防护） |
| `1dbab1bc`+`b035987c`+`745f7da8` | `GET /api/v1/achievements` + 热力图 + 徽章墙 + 日期偏移修复 |

### 2.6 多专家角色体系（20:54 起，借鉴 agency-agents，13 提交）

| 提交 | 内容 |
|------|------|
| `3592b2e3`+`ab147392` | 设计 + 计划（6 专家 + 轻量编排 + 索引校验） |
| `e77b044d`+`6a580094` | 6 专家角色卡（frontmatter + 身份/使命/规则/能力/流程）+ 工具名修正 |
| `1b1c8bd9`+`0cefc5cc` | `experts_manifest.json` 索引（divisions.json 风格）+ 一致性校验 + coordinator id 对齐 |
| `ed5a0192`+`5285adac` | `EXPERT_ROUTE` 阶段→专家路由 + state 附带 expert + manifest 交叉测试 |
| `45e99814`+`e469d8fe` | `auto_readiness(f1)` 自动 readiness 验收 + bbox 全链路接线测试 |

### 2.7 死代码清理 + error_case 语义（21:28 起，3 提交）

| 提交 | 内容 |
|------|------|
| `b28826d8` | error_case 未列出案例视为隐式无误 + auto_readiness docstring 4/6 |
| `b36b6180` | 删 64 文件/~19k 行死代码（space/agents/knowledge/partners orphan 组件 + CapabilityConfigCard + 死 props + 3 ConfigPanel） |
| `53c6c381` | 移除 ChatComposer 配置门控清理后的死回调 |

### 2.8 当天文档

- `afe1f44f` 2026-08-02 开发日报（6 大工作块汇总）

## 3. 8/3：全中文 + 进度可视化 + 引用溯源 + 定时提醒（28 提交）

### 3.1 界面全中文化（9:42 起，11 提交）

| 提交 | 内容 |
|------|------|
| `f9516cb4`+`b3a7fd08` | 成熟度差距分析（6 大类 + 前端功能对照 + 6 项逐项探索） |
| `ae719f41`+`4903fe6e` | 设计 + 计划（默认 zh + 保留切换） |
| `710823fa` | 4 处默认语言 en→zh（app-shell-storage ×2 / AppShellContext / init.ts） |
| `63ccd597` | zh locale 静态加载（首帧即中文）+ 对齐残留 en 默认 |
| `feeabe06` | 兜底清理硬编码英文（前端扫描 + 后端空态抽查） |
| `bd7bdff8`+`1c0d0916` | 冒烟截图 + 后端 ui.language 默认 zh + 默认 zh 断言 + html lang + 死代码清理 |
| `413b13e5`+`c85792a2` | **补齐 131 个未翻译 i18n key** + 修正 72-600 key + persona 遗漏 |

### 3.2 进度页 Tab 化（11:20）

- `ee71f4c2` 13 面板分 4 Tab（概览/记录/成就/图谱），默认概览一屏
- `372b8c22` 冒烟截图

### 3.3 教学轨迹（13:05 起，借鉴 FastGPT 运行日志）

| 提交 | 内容 |
|------|------|
| `3b80c633`+`27e3ec1e` | 设计 + 计划（合并进记录 Tab，练习回合可展开因果链） |
| `e762c292`+`bea94e8e` | `GET /api/v1/profile/trace-log`（records+decisions ±10 分钟匹配）+ 断言测试 |
| `b7eb6163`+`50275fb8` | Timeline 升级为可展开教学回合链 + 恢复预测徽章 + aria |

### 3.4 引用溯源（14:01 起）

| 提交 | 内容 |
|------|------|
| `cd0059da`+`3a5eb432` | 设计 + 计划（规范库页 + 对话〔规范:〕检测） |
| `fe298ac8`+`a8b1fea2` | `GET /api/v1/standards`（skill references 5 文档 + 章节）+ 容错 |
| `9d71a53f`+`171172d3` | 标注规范库页 + 侧边栏入口 + apiFetch 约定 + aria |
| `45cc3ec7`+`01e81272` | 对话〔规范: 文档§章节〕→ remark 插件 → 📖 chip → 弹窗 + Simple 路径 |
| `3ce4242e`+`bd7ec4e2` | PERSONA 教 Coach 用 + parseStandardHref 解码 percent-encoded href |

### 3.5 定时学习提醒（16:06 起）

| 提交 | 内容 |
|------|------|
| `76fd78b0`+`37264ac5` | 设计 + 计划（cron 工具验证 + 提示词 + 端到端） |
| `f449d8d9` | cron 工具 8 项测试（fake 服务隔离） |
| `9a711c03` | PERSONA 教 Coach 用 cron 工具 |

### 3.6 当天文档

- `3d7ffe05` 交接文档 v4

## 4. 8/4：定时任务管理 + 分享 + 生成式 UI（30 提交）

### 4.1 教学流程面板（12:23 起）

| 提交 | 内容 |
|------|------|
| `16ccbea3`+`df34e410` | 设计 + 计划（6 步状态图，只读 flow_state） |
| `66ec4dbc` | `GET /api/v1/profile/teaching-flow`（只读）+ 2 测试 |
| `9e3b4aa5` | 前端 6 步状态条（done/in_progress/blocked/pending + 专家路由 + 阻塞横幅） |

### 4.2 定时任务管理 UI（13:31 起）

| 提交 | 内容 |
|------|------|
| `265594f2`+`d4782166` | 设计 + 计划 |
| `e37b3fc1` | `CronService.set_job_enabled`（启停持久化）+ 2 测试 |
| `31b1bd78` | cron REST API（GET/DELETE/PATCH，owner 隔离 chat:local-admin）+ 3 测试 |
| `7479ae2e` | 定时任务管理页 + 侧边栏入口 |

### 4.3 免登录分享（15:32 起，借鉴 FastGPT）

| 提交 | 内容 |
|------|------|
| `5c753608`+`d29a8f58` | 设计 + 计划（token 白名单 + 只读分享页，安全前提：不暴露无鉴权 get_session） |
| `299642ad` | `ShareStore`（token_urlsafe(16) + JSON 持久化 + 过期 + 撤销）+ 4 测试 |
| `3ef4855c` | shares REST API（创建/撤销_鉴权 + 读取_公共 token）+ 3 测试 |
| `f13329d9`+`960449c1` | 分享按钮 + 只读分享页 + iframe 片段 + Next.js 16 params 修复 |

### 4.4 生成式 UI（16:41 起，借鉴 AG-UI structured-message，零框架依赖）

| 提交 | 内容 |
|------|------|
| `cb947f08`+`58553088` | 设计 + 计划（quiz_card 练习卡片，落地 chart 通道） |
| `e4b59f59` | `render_ui` 工具（validate_component 校验 → metadata.chart）+ 3 测试 |
| `4cd422d6` | ChatChartCard 扩展 quiz_card（题目/选项/点击即时对错/解释） |
| `d250a51f` | PERSONA 教 Coach 出题用 render_ui |

### 4.5 当天文档 + 交接

- `3d350818` 接力交接文档（fork 起点以来全部改动）
- `5d1764b0` 完整改动溯源交接文档（clone 后 164 提交 + 借鉴来源 + 实现方式）

---

## 五、端到端实测成果（Playwright 全部通过）

| 功能 | 实测结果 |
|------|---------|
| 界面全中文 | 侧边栏「主页/数据标注/进度/记忆/设置」，可切英文 |
| 进度页 Tab 化 | 4 Tab，概览一屏（fitsOnScreen=true） |
| 教学轨迹 | task1 行展开显示 F1=50%/review_first/推进决策 rationale |
| 教学流程面板 | 6 步状态条 + task task1 + 专家 task_guide |
| 规范引用 | Coach 输出 📖 bbox-guide chip → 点击弹窗「目标检测标注 · 遮挡目标处理」 |
| 定时提醒 | 对话设 30s 提醒 → Coach 主动提醒进会话（3 条教学风格） |
| 定时任务管理 | 列表→停用→删除→空态完整闭环 |
| 免登录分享 | 有效 token 返回 732 条消息会话；无效 token 报「无效或已过期」 |
| 生成式 UI | 出 IOU 选择题 → 可点击练习卡片 → 点 A 变绿+解释 |

## 六、当前状态与下一步

### 完成
- 竞赛 6 模块 ✅（①学习计划 ②会话 ③任务引导 ④困难检测 ⑤报告 ⑥批改）
- 3 优化 ✅（工作台裁剪/任务引导引擎化/打卡徽章）
- 8/3-8/4 全部增强 ✅（全中文/教学轨迹/流程面板/规范引用/定时提醒/定时任务/分享/生成式 UI）

### 未做（下一步候选）
- **竞赛交付材料**（01报名表/02Demo说明/05合规/06材料包，9/1 硬要求）——素材在 docs/ 已齐全，最紧要
- 语音 agent 循环（差距文档最后一项，需外部 STT/TTS 服务）
- 小遗留：死代码残留英文 aria-label、热力图列顺序、course_plan task10-12 映射、error_case 部分正确评分

## 七、关键技术事实（接力必读）

- **工具注册**：`builtin/__init__.py`（import + BUILTIN_TOOL_TYPES + __all__ + CONFIGURABLE）+ `tool_composition.py` always_on（现 16 个：15 教学 + render_ui）
- **chart 契约**：`metadata.chart = {type, data}`，从 tool_result 事件的 `metadata.tool_metadata.chart` 读取
- **flow/PERSONA 双副本**：skill references + persona references / preset + workspace（workspace gitignored 但运行时生效）
- **TeachingFlowEngine**：无参构造持久化到 `data/user/workspace/learning/flow_state.json`；`on_evaluated(task_id, f1, readiness=None)` 自动推进
- **测试基线**：2985 passed / 33 预存在失败（Windows 路径/GBK/可选依赖 telegram/slack/sandbox）
- **启动**：后端 `python -m deeptutor_cli.main serve --port 8001`；前端必须 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`（IPv6 问题）；next build 需清 HTTP_PROXY/HTTPS_PROXY
- **docs/ 被 gitignore**，提交需 `git add -f docs/...`
- **备份 tag**：`backup-2026-08-04-share-done`（已推送远程）

## 给接力 AI 的提示词

> 这是 DeepTutor fork「标注星图」数据标注教学 Agent（讯飞竞赛）。8 月起 130 提交完成：借鉴落地（lumen/edumcp/Multi-Agent/Vibe/EverOS/awesome-llm-apps/agency-agents/TradingAgents/feynman-tutor/AG-UI/FastGPT）→ 竞赛 6 模块 → 10 项增强（全中文/进度 Tab/教学轨迹/流程面板/规范引用/定时提醒/定时任务/分享/生成式 UI）+ 死代码清理。全部端到端实测通过。**当前最紧要：竞赛交付材料**（01报名表/02Demo说明/05合规/06材料包，9/1 截止），素材在 docs/ 齐全。详细见本文件 + `docs/session-handoff.md` + `docs/maturity-gap-analysis.md` + `docs/fork-features.md`。启动带 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`。
