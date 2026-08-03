# 标注星图 — 成熟度差距分析（vs 开源 Agent 项目）

> 定位: 纯差距分析快照（非设计/非计划）。供评审汇报与后续规划参考。
> 创建: 2026-08-02（合并前端页面功能差距对照）
> 参照: OpenHands / RAGFlow / LobeHub / FastGPT / awesome-llm-apps

---

## 一、模型接入与用户易用性

### 1. LLM 配置流程过重
- 接入模型要走 7 步：Profile → Provider → Base URL → API Key → Model ID → Context Window → 诊断测试
- 术语全是开发者向（Profile/binding/Context Window/Dimension/Diagnostics），成熟产品（ChatGPT/Cursor）只需"选供应商 + 粘贴 Key"两步
- 无开箱即用的预配置模板（OpenAI/DeepSeek/硅基流动等）；验证藏在"诊断"折叠面板，无粘贴后自动测试的绿勾/红叉

### 2. 设置项严重超纲
- 28 个设置子页面（LLM/Embedding/Search/TTS/STT/ImageGen/VideoGen/MCP/Agents...），通用 DeepTutor 平台遗留
- 对标注星图，用户只需 LLM（必配）+ 可选 Embedding；普通用户被 28 个设置页淹没

### 3. 首次使用无引导闭环
- 注册→登录→进首页只有随机欢迎语；未配 LLM 时聊天静默失败，无前置检测与引导
- 无演示对话/示例任务进度，"立即体验"按钮缺失

## 二、用户界面友好性

### 4. 无生成式 UI（Generative UI）
- 成熟 agent 能动态渲染交互组件（表单/卡片/可编辑计划/聊天驱动面板）；awesome-llm-apps 有 generative_ui_agents 分类
- 我们只有 4 类预置图表（成绩单/雷达/进度/图谱），静态渲染，agent 不能生成新 UI 组件

### 5. 无语音 Agent 循环
- 成熟项目有语音进→语音出的完整语音 agent（语音导览/客服/语音 RAG）
- 我们只有基础 TTS/STT 转发接口，无完整语音对话 agent 流程

## 三、教学场景专属能力

### 6. 无教师/班级视角
- 有多用户隔离 + 管理员后台，缺中间层"教师"角色：建班级、添加学生、看全班进度、批量催作业
- 竞赛 6 人团队 + 教学平台，教师视角是必答题

### 7. 无主动触达（学习提醒自动化）
- cron 服务已就绪 + 7 个 IM 渠道（Telegram/WeCom/Lark/DingTalk/Slack/QQ/Matrix/Discord）都有，但零教学接入
- 成熟项目（OpenHands automations、LobeHub Schedule）都能定时/事件触发主动推送——如"每日学习提醒""连续 3 天未练主动问候"

### 8. 无引用溯源可交互
- 学习记录里的标准出处（如 GB/T 41867 §6.1）在对话中不可点击查看原文
- RAGFlow 可视化 chunk + 点击溯源、FastGPT 引用可修改删除；我们 source_manifest 只进系统提示词，溯源停留元数据层

## 四、可观测性与运营

### 9. 无对话调用链运营视图
- 数据齐全（learning records/decisions/flow_state/traces），但前端无"一条对话里用了哪些工具、卡在哪一步、每次评测结果"的完整链路面板
- FastGPT 有调用链路日志 + 应用评测；这是教师看学生进度的核心诉求

### 10. 无可视化流程编排
- TeachingFlowEngine 是代码内状态机（6 步），无可视化编排或流程状态图
- FastGPT Flow 画布、RAGFlow agentic workflow 是核心卖点；轻量版至少 Progress 页显示"6 步当前走到哪一步"

### 11. 无系统化评估体系（Evals）
- 成熟项目都有离线评测集（LLM-as-judge 批量跑教学回合 → 指标回归）
- 我们有对抗评估 + 单元测试，但无"20 个标准教学回合 → 接话质量分/F1 命中率"的系统评测集

### 12. 无可观测性集成（LLM Ops）
- 成熟项目标配 Langfuse/OpenTelemetry/LangSmith（token 成本/延迟/失败率/trace 面板）
- 我们零集成，只有本地 UsageTracker 内部结构

## 五、分发与生态

### 13. 无一键部署 + 首启引导
- OpenHands npm 一条命令、FastGPT/LobeHub/RAGFlow Docker 一条命令
- 我们安装要 clone + pip install -e + next dev 三步，且无 onboarding 向导

### 14. 无免登录分享/嵌入
- FastGPT 有免登录分享窗口 + Iframe 一键嵌入，我们没有——给评委/家长演示缺便捷途径

### 15. 无插件/技能市场 UI
- 有 skill 系统 + ClawHub 外部 hub，但无内置市场 UI 和热安装引导（LobeHub 有 10k skills 市场）

## 六、前端页面功能差距对照（对标项目页面集成功能）

### 明确缺失

| # | 功能 | 标杆 | 我们现状 |
|---|------|------|---------|
| 1 | 免登录分享（生成链接给外部看） | FastGPT | ❌ 无分享按钮/链接 |
| 2 | Iframe 一键嵌入（嵌入别站） | FastGPT | ❌ 无嵌入产物 |
| 3 | 调用链路运营视图（工具轨迹面板） | FastGPT/OpenHands | ⚠️ 仅 TracePanels/SubagentRunTranscript 局部片段，无完整链路面板 |
| 4 | 定时任务管理 UI（创建/编辑/启停 cron） | LobeHub Schedule/OpenHands | ❌ 后端有 cron 服务但前端无管理界面 |
| 5 | 可视化工作流画布（拖拽节点编排） | FastGPT Flow/RAGFlow | ❌ 无 |
| 6 | 技能/插件市场页（浏览/安装） | LobeHub 10k skills | ❌ 无（只有 backend skill 系统） |
| 7 | 免登录演示态 / 引导 Tour | 全部 | ⚠️ 有 SettingsTour 但仅设置页，无整体 onboarding |
| 8 | 移动端适配（响应式） | LobeHub | ⚠️ 桌面优先 |

### 有雏形但未到集成页水平

| # | 功能 | 标杆 | 我们现状 |
|---|------|------|---------|
| 9 | 语音对话 UI | LobeHub 语音 | ⚠️ 有 mic 组件痕迹，无完整语音交互页 |
| 10 | 白盒可编辑记忆 | LobeHub | ⚠️ 有 Memory L1/L2/L3 工作台（已不错） |
| 11 | 主题/外观自定义 | LobeHub | ✅ 已有 appearance 设置 |
| 12 | 知识库 chunk 可视化 | RAGFlow | ⚠️ 有 KB 后端但前端知识库页已删 |

### 我们反而领先（对标前端所无）

- Progress 页雷达/图谱/打卡徽章/教练绩效面板（教学专属，前端集成度最高）
- 对话内 4 类图表卡片（成绩单/雷达/进度/图谱）
- 三层记忆可视化（LobeHub 只有单层）

## 七、已领先、无需补

- 三层白盒记忆、7 个 IM 多渠道、多模型 provider、决策审计/对抗评估、学习图谱/雷达图

## 八、核心信号

缺的不是"算力/逻辑"层，而是**让教学过程"可见、可运营、可分发"的前端层**——数据都在（records/decisions/flow_state/traces），缺的是画出来给教师和学生看的运营视角，以及让新用户 5 分钟上手的一键配置/引导/部署体验。

对标项目前端页面的三类共性缺失：
1. **分享/分发** — 免登录分享链接 + Iframe 嵌入
2. **运营/调试** — 调用链路视图 + 定时任务管理 UI
3. **可视化编排** — 流程画布（工作量大，不建议短期）

## 九、参照项目清单

| 项目 | 类型 | Stars | 借鉴点 |
|------|------|-------|--------|
| OpenHands | 编码 agent/自动化 | 高 | automations、运营面板、多后端 |
| RAGFlow | 知识库 RAG | 高 | 引用溯源、chunk 可视化、中文界面 |
| LobeHub | 聊天 UI 生态 | 高 | 中文界面标杆、技能市场、白盒记忆 |
| FastGPT | LLM 应用平台 | 高 | 分享/嵌入、调用链路、工作流画布、中文 |
| awesome-llm-apps | 模板集 | 130k | 生成式 UI、语音、always-on、eval |

## 十、明确不做（教学无关）

- 多数据源同步连接器（Confluence/S3/Notion）
- 通用代码执行沙箱开放给用户
- 多 agent 后端切换（local/remote/cloud）
- 完整 DAG 可视化编排画布（短期）

## 十一、遗留映射（供未来规划参考，非承诺）

| 优先级 | 事项 | 教学价值 | 工作量 |
|--------|------|---------|--------|
| P0 | 默认全中文界面改造 | 第一印象 | 小 |
| P0 | 对话调用链运营视图 | 教师核心诉求 | 小 |
| P0 | 引用溯源可点击 | 权威性 | 小 |
| P1 | 教学流程可视化（6 步状态图） | 评委印象 | 小 |
| P1 | 定时学习提醒（cron 接入） | 主动陪伴 | 小 |
| P1 | 定时任务管理 UI | 运营 | 中 |
| P2 | 免登录分享/嵌入 | 演示 | 中 |
| P2 | 生成式 UI | 视觉冲击 | 大 |
| P2 | 语音 agent 循环 | 完整度 | 大 |

---

## 十二、逐项探索结论与方案（2026-08-02）

> 对前端页面功能差距逐项代码级探索，确认后端依赖现状 + 落地工作量。共性结论：**后端能力大多现成，主要工作在前端页面 + 少量聚合 API**。

### ① 免登录分享 + Iframe 嵌入
- **FastGPT 做法**：分享按钮 → 生成 `shareToken` 免登录链接 → 白名单校验 → 只读访问该应用；同一 URL 可 `<iframe>` 嵌入任意站点
- **可复用**：`sessions.py` 会话数据返回现成；`SessionViewerPanel` 只读渲染可复用
- **关键安全约束**：当前 `get_session(session_id)` **无任何鉴权**（AUTH_ENABLED 时路由级拦截，但单机模式=读全部）。分享不能直接暴露只读 API，否则放大风险——**必须先补会话鉴权**
- **方案**：`share.py` 路由（`POST /api/v1/shares` 登录创建 → 随机 token + 关联 session + 过期；`GET /api/v1/share/{token}` 挂公共路由绕过 auth → 只读快照）+ 前端 `/share/{token}` 只读页（禁用 composer）+ Home 会话菜单「分享」按钮 + 可选 Iframe 嵌入片段
- **工作量**：中（安全隔离是前提）

### ② 调用链路运营视图
- **FastGPT 做法**：应用「运行日志」展开对话看每节点输入/输出/耗时/LLM 调用
- **可复用**：`TracePanels.tsx`（2447 行）已实时渲染 tool trace + research 阶段卡（`AssistantActivity` 在用）；`getTraceMeta` 已复用；profile API 14 端点全有
- **真实缺口**：非缺 trace 渲染，缺**跨会话聚合的教师视角**——"按时间/任务过滤的评测+工具调用记录"，和"评测→卡住→介入→落盘"整条因果链（现分散 records/decisions/flow_state 三处）
- **方案**：`GET /api/v1/profile/trace-log?limit&task_id` 聚合生成「教学回合列表」+ Progress 页「教学轨迹」面板（行展开复用 getTraceMeta 渲染）
- **工作量**：小（数据全有，后端聚合 + 前端 1 面板）

### ③ 定时任务管理 UI
- **标杆做法**：LobeHub Schedule / OpenHands Automations 前端创建/编辑/启停定时任务
- **可复用**：`CronService` 完整（`CronSchedule` at/every/cron + `CronJob` + JSON 持久化 + `compute_next_run`），main.py lifespan 已启停
- **真实缺口**：无任何 cron API、无业务调用方（完全空置）
- **教学应用**：「每日 20:00 提醒」「连续 3 天未练主动推送」走已有 partners 渠道
- **方案**：`cron.py` 路由（list/create/patch/delete + runs 历史，action 限消息模板白名单）+ Settings「定时任务」页 + 预置教学模板
- **工作量**：中（cron 服务现成不用重写）

### ④ 可视化工作流画布
- **标杆做法**：FastGPT Flow（ReactFlow 拖拽）、RAGFlow agentic workflow
- **关键判断**：**不建议做完整画布**——教学是线性流程（诊断→计划→理论→练习→反馈→记录），无并行/复杂分支；现有 TeachingFlowEngine 已验证+全测试，重做编排=重构核心教学层风险高；cytoscape（已有）是图展示非图编排
- **轻量替代**：**流程状态可视化（非编排）**——Progress 页「教学流程」6 步横向状态条，高亮当前步 + 阻塞原因；数据源 `flow_state.json` 现成；纯 CSS/SVG 无需 reactflow
- **工作量**：小（可与②合并为「教学轨迹」面板）

### ⑤ 技能/插件市场页
- **标杆做法**：LobeHub 独立市场页浏览安装
- **可复用**：`SkillService` CRUD + install_tree + hub-lock 溯源；skills API `/list` `/tags/*` `/hub/catalog` `/hub/detail` `/install`；ClawHub 集成
- **真实缺口**：**纯前端市场 UI 页**
- **方案**：Settings「技能市场」页（Tab A 已安装 / Tab B ClawHub 市场安装）；低配版只做「已安装」卡片列表
- **工作量**：小-中（后端全现成）

### ⑥ 引导 Tour / 演示态
- **标杆做法**：所有成熟产品 first-run 引导（选目标→配模型→首个交互）
- **可复用**：`SettingsTourOverlay` 跨路由引导框架（data-tour + Spotlight + 键盘导航）；演示数据已有预跑
- **真实缺口**：无首次启动整体引导、无未配模型前置检测
- **方案**：Home 挂载查 `/api/v1/settings` 是否有 active LLM profile → 无则横幅引导；复用 Tour 框架新增 Home/Annotation/Progress 步骤（localStorage 标记首次触发）；Home 欢迎语带示例提问 chip
- **工作量**：小-中（框架现成）
