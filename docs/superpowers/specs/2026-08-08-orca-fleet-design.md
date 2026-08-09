# 第八轮优化设计 B：专家 Fleet 看板 + 任务通知（借鉴 stablyai/orca 功能）

> 日期：2026-08-08。来源：`stablyai/orca`（YC-backed "AI Orchestrator"）。已 clone 到 `%TEMP%\opencode\refs\orca\orca\`。深度调研：`AgentKanbanBoard.tsx`（看板列 + 卡片）、`dashboard-snapshot.ts`（序列化快照契约）、`smart-attention.ts`（需你→完成→工作中排序）、`mobile-notification-replay.ts`（seq/epoch 重放 + WS 即推送）。
> **结论**：Orca 的功能可借鉴点与前端（O1-O3）互补——**专家 Fleet 看板**（把 delegate 系统可视化）+ **WS 即推送 + seq/epoch 重放**（Coach/任务完成通知）。**与前端设计（`2026-08-08-orca-frontend-design.md`）是两个独立文档**，本设计单独立项。

## 关键事实核查（Orca 深度）
- **Fleet 看板**（AgentKanbanBoard.tsx）：列 = `Needs You → Working → Done → Idle`（生命周期桶，固定序）；卡片 = 状态点 + 图标 + 标题（unseen 加粗）+ 消息摘要 + 时间戳（`startedAt` vs `finishedAt`）。**askSummary 横幅**：专家提问时琥珀卡显示问题摘要。
- **快照契约**（dashboard-snapshot.ts）：结构化克隆安全的可序列化 `DashboardCard`，含 `paneKey`（稳定 key）/`bucket`/`dotState`/`task`/`lastUserMessage`/`lastAgentMessage`/`unseen`（ack 模型）/`startedAt`/`finishedAt`/`stateChangedAt`。
- **Smart attention 排序**（smart-attention.ts）：每工作流分类「1 需你（blocked/waiting）/ 2 完成 / 3 工作中 / 4 空闲」，需你者浮顶。
- **WS 即推送**（mobile-notification-replay.ts）：持久 WS 双作推送通道；desktop 存 256 事件重放缓冲 + 单调 `notificationSeq` + `notificationEpoch`（进程生命周期 UUID）；客户端 `getMissedSince(seq, epoch)` 幂等 catch-up。
- **unseen ack 模型**：打开终端对话框即 ack；done 卡 unseen 时 emerald，ack 后 settle 灰。

## 我们现状（已核实）
- **delegate 系统**（delegate_expert_tool.py）：6 专家，`DELEGATE_TIMEOUT_SECONDS=60`，E3 单轮 ≤2 并发。前端只有 `SubagentRunTranscript`（完整结论折叠块），**无实时专家状态看板**。
- **进度事件**：delegate 经 `_retrieve_trace_metadata`（subagent_delegate）→ `tool.progress`（"专家 X 分析中…"）→ TracePanels trace 行。
- **trace-log 端点**（profile.py:153）：`GET /api/v1/profile/trace-log`（教学回合审计，AnnotationCoach 30s 轮询 struggle）。
- **WS**：unified-ws.ts 单连接流式。

## 借鉴点（功能部分）

### F1. 专家 Fleet 看板（消息流内专家任务卡）⭐ M 成本
借鉴 AgentKanbanBoard + dashboard-snapshot，把 delegate 可视化：
- **专家任务卡**（ChatMessages 内可折叠）：每专家一行（状态点 + 专家名 + 当前工具 working 时 + 结果摘要 done 时），状态实时更新。
- **状态桶**：`Needs You → Working → Done → Idle`——对应 ask_user（等待输入）/运行中/完成/空闲。
- **unseen ack**：专家完成 → emerald + unseen；打开卡片/查看后 ack。
- **askSummary 横幅**：delegate 卡住/提问时琥珀显示摘要。
- 数据源：复用 delegate 事件流（tool_call/tool_result/tool.progress），零后端改动（前端状态机）。

### F2. WS 即推送 + seq/epoch 重放（任务完成通知）⭐ M 成本
借鉴 mobile-notification-replay：
- **后端**：回合完成事件打 `notificationSeq`（单调）+ `notificationEpoch`（进程 UUID），存重放缓冲（如 256）。
- **前端**：WS 收到通知 → 桌面通知/Coach 气泡；断线重连 → `getMissedSince(seq, epoch)` 幂等 catch-up。
- 落地：利用现有 WS 流式 + trace-log；新增轻量通知事件类型（或复用现有 result/error 事件）。

### F3. Smart Attention 排序（Coach 审阅优先级）⭐ S 成本
借鉴 smart-attention：学习记录/教学回合按「需学生回应 → 完成 → 工作中 → 空闲」排序，Coach 优先审阅需学生回应的会话。

## 不借鉴
- Electron 壳 / WebGL 终端 / 移动伴侣（Web 平台不适用）
- 并行 worktree git 操作（教学场景无 git）
- View Transition 列间动画（看板落地后再定）

## 优先级
| 优先级 | 项 | Effort | 说明 |
|--------|----|--------|------|
| **P0** | F1 专家 Fleet 看板 | M | 前端状态机，零后端 |
| P1 | F2 WS 推送重放 | M | 需后端事件 seq/epoch |
| P1 | F3 Smart attention 排序 | S | Coach 审阅优先级 |

## 实施顺序建议
先 F1（专家看板，纯前端，价值最高）→ F3（排序，快）→ F2（推送重放，需后端）。

## 复用与冲突
- F1 复用 delegate 事件流 + 前端 O1 的 AgentStateDot 状态点原语（色值词汇表）
- F1 不碰 delegate_expert_tool.py / ChatMessages 大文件（新增独立卡片组件）
- F2 不碰 unified-ws 核心（只加事件消费 + 重放缓冲）
- 与前端设计（orca-frontend O1-O3）互补，各自独立实施
