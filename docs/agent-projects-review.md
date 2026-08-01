# 开源 Agent 项目调研 — 可借鉴之处

> 调研时间: 2026-08 | 方式: GitHub API 搜索 + README/架构文档分析
> 目标: 为「数据标注教学平台」(DeepTutor 教练 + Label Studio 练功房) 寻找可借鉴的设计

---

## 一、项目总览

| 项目 | ⭐ | 定位 | 与我们最相关的点 |
|------|-----|------|----------------|
| **aieducations/edumcp** | 156 | 教育 MCP 互操作协议 | 学习记录/学习者状态跨系统共享标准 |
| **ahmedEid1/lumen** | 76 | 学习者拥有的两角色学习平台 | 六轮 intake→brief→orchestrator 建课→RAG 带引用 |
| **A-R007/Multi-Agent-Study-Assistant** | 46 | 6 专用 Agent 学习平台 | Analyzer/Roadmap/Quiz/Tutor/RAG 六角色分工 |
| **idoforgod/Vibe-learning-AgenticWorkflow** | 23 | 17 Agent 苏格拉底导师 | Never-Answer 协议、教育理论映射、3-Phase、双 SOT |
| **koukekoukej-glitch/feynman-tutor** | 18 | 费曼学习法 skill | 三层学习者笔记、意图分诊、事实vs推理、可视化转交 |
| **towardsai/ai-tutor-app** | 17 | Agentic RAG 导师 (LangGraph) | RAG 引用/接地、上下文工程实验 |
| **saniales/ai-lesson-planner** | 16 | 多 Agent 备课流水线 | course-planner→discussion-moderator→lesson-planner→slides |
| **SirhanMacx/Claw-ED** | 54 | CLI 备课 Agent | 生成完整课时包的 CLI 工作流 |
| **Hawary00/AI-Tutor** | 8 | LangGraph 多模态导师 | 幻觉预防 (答案必须接地材料) |
| **Man0dya/Tutor-AI** | 19 | 多 Agent 家教系统 | FastAPI + React 教学栈 |

---

## 二、重点项目深度分析

### 1. koukekoukej-glitch/feynman-tutor — 最值得整体借鉴

单文件 SKILL.md，教学哲学写得极好。可直接移植到我们 coach 的设计:

**① 三层学习者笔记 (跨会话记忆升级)**
```
① 他和你约定的沟通方式   — 只有他明确说过的规则才能进 (我们: preferences)
② 你能看清的稳定模式     — 跨多次对话、证据充分才升级 (我们: synapse pattern)
③ 你注意到但还没看清的   — 只记"什么场景下做了什么"，不命名不归类
```
**核心规则: 永远不要从一次观察直接升级成画像。** 我们 synapse 记忆应加"证据链"字段——每条 pattern 必须附证据（学生原话/具体场景）。

**② 意图分诊 (Phase 0 Step 0 增强)**
```
- 一句话确认类疑问 → 直接回答，问要不要展开
- 接上次话题 → 从笔记记录的进度直接进入
- 想从头学 → 走完整深入对话
```
我们目前诊断对话只有"有/无记录"两分支，可加第三类"快速确认"。

**③ 事实 vs 推理 (修正"绝不直接给答案")**
```
判断标准: 他要讲的内容，他自己推能推出来吗?
- 能 → 让他推 (苏格拉底)
- 不能 (缺事实: 定义/工具机制) → 直接给事实，不卖关子
- 能但要很久 → 看精力，累了就接一把
```
我们的"三个绝不"偏绝对，应补这条校准规则——防止把"查定义"也强制变成探问。

**④ 可视化转交 subagent**
> 遇到符号操作（公式推导、矩阵运算）→ 开独立 subagent 调 grimoire skill 产出可交互 HTML → 返回文件路径贴给学生。可视化不接管对话节奏。

完美对接我们的 aetherviz-master / IOU 3D 演示计划——不 inline 生成，subagent 产出 + 路径返回。

**⑤ 写笔记前必须确认** — "他必须看过你总结的内容，明确说'可以'才写"。我们 write_learning_record 目前无确认环节，应让 Coach 先复述摘要等确认。

---

### 2. idoforgod/Vibe-learning-AgenticWorkflow — 工程化最强的教学 Agent

**① 教育理论映射 (我们的 PERSONA 缺理论根基)**
```
VanLehn(2011): 1:1 导师效果 d=0.79 vs 大班课 d≈0.0
Bloom(1984):   2-sigma 问题 (1:1 优势 2 个标准差)
Chi(2005):     建构主义 > 被动接受
Flavell(1979): 元认知是学习效果核心调节变量
```
建议在 PERSONA.md「设计依据」加入这些引用，评审时更有说服力。

**② Never-Answer Protocol (验证我们的提示梯)**
> 3 阶段问题 (L1→L2→L3) 渐进思考深度；发现误解时不直接纠正，用认知冲突问题引导学生自我纠正。

我们已有 L0-L5 提示梯 + 认知冲突干预，与其 L1-L3 思路一致。可借鉴: 他们**每条回答必须以问题结尾**的硬约束。

**③ 双 SOT 状态分离**
> Phase 0 进度 (`state.yaml`) 与学习者状态 (`learner-state.yaml`) 分离。

我们 learning_records.jsonl 目前混着课程进度和学习者画像，可拆两类记录。

**④ CLI 命令词汇表 (可直接移植到我们的 CLI)**
```
/teach [keyword]    课程自动生成
/start-learning     苏格拉底对话开始
/end-session        结束+总结
/resume             断点恢复
/my-progress        进度
/concept-map        概念连接图
/challenge          迁移挑战 (测试)
```
我们 CLI chat 只有 /cap /kb /tool 等基础设施命令，缺教学领域命令。这些命令可映射到 annotation-coach 的流程入口。

**⑤ @edu-analyst 对抗性教育验证** — 一个 agent 专门审核其他 agent 的教学法正确性。可在 coach 流程加一个"教育学自检"步骤：每次模块设计后自问"这符合 ZPD 吗？认知负荷超了吗？"

**⑥ 17 个专业 agent 里对我们有用的:**
- `misconception-detector` (8 型误解) → 对照我们的 9 型 error_to_intervention
- `learner-profiler` (5-7 个自适应问题) → 我们 Phase 0 Step 2
- `concept-mapper` / `progress-tracker` → 个人中心技能图/进度数据模型
- `path-optimizer` (prerequisite DAG) → 我们的 competency_map 缺前置知识链

---

### 3. ahmedEid1/lumen — 生产级平台工程

**① 六轮 capped intake → learning brief → 建课 orchestrator (~50s)**
> 有界 intake (最多 6 轮) 把模糊目标收敛成结构化 brief，再由 orchestrator 建 4 模块/16 课。**诚实状态、无半成品、可重跑、可取消。**

对应我们的 Phase 0。可借鉴"有界 intake + 结构化 brief"作为诊断的产出契约（我们现在诊断产出是写 memory，没有显式 brief 文件）。

**② course-scoped RAG 引用** — 课程范围内的 RAG 回答必须带课程引用。我们的 rag 无"范围限定"，可加"只检索当前模块 KB"。

**③ 审计每个 agent 决策** — 平台记录 agent 每次决策供用户审计。我们已有 StreamBus 事件流，可扩展成"为什么推荐这个任务"的可追溯 UI。

**④ 公开评估、保留弱分** — README 展示 authoring eval 3.85/5 (n=10)，不删弱数据。评审文化可借鉴。

---

### 4. A-R007/Multi-Agent-Study-Assistant — 角色分工确认

6 个 agent: Student Profiler / Roadmap Creator / Quiz Generator / Tutor / Resource Finder / RAG Tutor。

**① Gap Analysis + Prerequisite (我们缺的)**
> 识别你需要的知识和前置知识。我们 competency_map 是平面技能树，缺"前置依赖边"。

**② 自适应难度 Quiz** — 题型匹配知识水平。我们 understanding_check 7 种方式但无难度自适应。

---

### 5. aieducations/edumcp — 互操作标准

教育领域 MCP 协议，让 AI 模型/应用/硬件/内容互通。156⭐ 说明有需求。

**借鉴点:** 定义"学习者状态 MCP server"——把 learning_records 暴露为 MCP 资源，Coach / Label Studio / 个人中心都能读写同一份学习状态。这与我们的 Label Studio 集成方向一致。

---

## 三、可落地借鉴清单 (按优先级)

### P0 — 低成本高价值 (改 prompt/流程即可)

| # | 借鉴 | 来源 | 落地方式 |
|---|------|------|---------|
| 1 | 意图分诊 (快速确认/续学/深入) | feynman | flow-onboarding Step0 加第三分支 |
| 2 | 事实 vs 推理校准 | feynman | flow-theory Step3 加判断规则 |
| 3 | 记忆确认前置 | feynman | write_learning_record 前 Coach 先复述等确认 |
| 4 | 三层学习者笔记 | feynman | synapse 记忆加 pattern 证据链字段 |
| 5 | 教学法理论引用 | Vibe | PERSONA.md 加设计依据 (VanLehn/Bloom/Chi) |
| 6 | CLI 教学命令 | Vibe | chat CLI 加 /resume /progress /concept-map /challenge |
| 7 | 双 SOT 分离 | Vibe | learning_records 分课程进度 vs 学习者画像 |
| 8 | 回答以问题结尾 | Vibe | flow-theory 加硬约束 |

### P1 — 中成本 (加工具/小功能)

| # | 借鉴 | 来源 | 落地方式 |
|---|------|------|---------|
| 9 | 前置依赖链 | Multi-Agent | competency_map 加 prerequisites 字段 |
| 10 | 教育学自检步骤 | Vibe | coach 流程加模块后自检 (ZPD/认知负荷) |
| 11 | 有界诊断 brief | lumen | Phase0 产出结构化 brief 文件 |
| 12 | 课程范围 RAG | lumen | rag 限定当前模块 KB |
| 13 | 概念图/进度 agent | Vibe | 个人中心数据模型对齐 concept-map |

### P2 — 高成本 (基础设施)

| # | 借鉴 | 来源 | 落地方式 |
|---|------|------|---------|
| 14 | 学习者状态 MCP server | edumcp | 暴露 learning_records 为 MCP 资源 |
| 15 | 可重跑建课 | lumen | 建课流程幂等化/可取消 |
| 16 | 可视化 subagent 转交 | feynman | aetherviz 3D 演示走 subagent 产出路径 |
| 17 | 决策审计 UI | lumen | 事件流 → "为什么推荐这个" 可追溯 |

---

## 四、结论

**最有价值的 3 个借鉴方向:**

1. **feynman-tutor 的教学对话哲学** — 意图分诊 + 事实vs推理 + 三层记忆，直接把我们 coach 从"流程严谨"提升到"会教人"
2. **Vibe 的教育理论工程化** — 理论引用、Never-Answer 硬约束、CLI 命令、双 SOT，把设计文档变成有据可依的工程
3. **lumen 的生产级确定性** — 有界 intake、可重跑、决策审计，为竞赛答辩加分

**不建议借鉴:** 17 agent 的重度编排（我们单 Coach + 多工具更轻、可控）；Postgres/pgvector/Redis/MinIO 全栈（我们 SQLite + JSONL 已够教学场景）。
