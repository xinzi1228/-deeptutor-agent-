# 议题⑦ 设计：多 Agent 总控（总控 + 分管，避免上下文污染）

> 用户诉求：一个总控 agent 掌管分管 agent，专人专事，避免上下文污染。

## 1. 现状痛点

- 6 专家（learning_planner/task_guide/grading_expert/struggle_detective/report_analyst/session_steward）通过 `EXPERT_ROUTE` 按阶段路由，但**全部共享同一 context + 同一 8 轮 loop + 全部 21 个工具**
- 专家卡在 `annotation-coach-flows/references/experts/`，PERSONA「专家协作」节切换视角——**逻辑多专家、物理单上下文**，互相污染
- 无 subagent/委派机制

## 2. 调研借鉴

| 来源 | 核心机制 | 融入点 |
|------|---------|--------|
| OpenAI Swarm | handoff 交接 + `context_variables`（最小上下文传递） | 总控→分管 handoff |
| superpowers dispatching-parallel-agents | 子 agent **隔离 context**（不继承主 agent 历史，构造精确所需）；brief 结构（Focused/自包含/明确输出）；主 agent 保留 context 协调 | **防污染核心机制** |
| lumen | capped intake → structured brief → orchestrator；**审计 agent 决策** | brief 契约 + 决策可追溯 |
| Multi-Agent-Study-Assistant | 6 角色分工 | 专家职责边界 |
| LangGraph supervisor | supervisor 路由 worker | 总控路由模式 |

## 3. 目标架构

```
用户 → 总控 Agent（保留用户会话 + teaching_flow + 记忆区）
         │  route_input 分诊（议题⑤）→ EXPERT_ROUTE 决定派谁
         ▼
      delegate_to_expert 工具（委派，brief 结构化自包含）
         │  brief = {目标, 任务数据, 约束, 期望输出}
         ▼
      分管 Agent（6 专家，各自独立 context）
         · 独立 system prompt（专家卡）
         · 受限工具白名单（专人专事）
         · 独立 LLM 调用（一次任务一次）
         ▼
      结构化结果回传 → 总控汇总 → 用户
```

## 4. 上下文隔离机制（核心，防污染）

| 维度 | 现状 | 改造后 |
|------|------|--------|
| 对话历史 | 专家共享全历史 | 分管 agent 只带 **brief**（自包含），**绝不继承全历史** |
| 工具 | 21 个全开 | 每个分管 agent **受限工具白名单** |
| 记忆 | 共写同区 | 分管 agent 写对应记忆区（议题②） |
| 结果 | 混在 context | 结构化返回（verdict JSON） |

## 5. 强化设计（4 点，来自调研）

1. **brief 契约化**：委派 brief = `{目标, 任务数据, 约束, 期望输出}`，自包含、不引用全历史
2. **决策审计**：每次委派写 trace-log（"为何派 grading_expert"），评审可追溯（lumen）
3. **并行委派**：独立专家任务并行（如 struggle_detect 与 grading 同时跑）（dispatching）
4. **结果汇总验证**：总控收集各分管结果 → 检查冲突 → 整合给用户（dispatching）

## 6. 实现与测试

- `delegate_to_expert` 工具（新增）：总控调，内部起一次独立 AgentLoop（专家卡 prompt + 受限工具 + brief），返回结构化结果
- 专家卡从 `annotation-coach-flows/references/experts/` 读取（已有）
- 分管 agent 复用 `AgenticChatPipeline`（跑一个受限回合）
- 委派决策写 trace-log（审计）
- 测试：`tests/tools/test_delegate_expert.py`（各专家委派 + brief 隔离 + 受限工具 + 结果回传）
- 冒烟：提交标注 → 总控委派 grading_expert → 独立评分 → 返回 verdict → 总控反馈

## 7. 衔接

- 议题⑤ `route_input`：总控意图分诊入口
- 议题② 记忆分区：分管 agent 写对应记忆区
- 议题③/⑥：检索/护栏作为分管 agent 公共工具
- 议题④：LS 评分回传也走总控调度
