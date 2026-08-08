# 第六轮优化设计：AnnotationCoach 前端 UX 增强（借鉴 hermes-agent）

> 日期：2026-08-08。来源：`NousResearch/hermes-agent`（AI agent 框架，Python 后端 + React/TS 前端，stdio/WS JSON-RPC）。已 clone 到 `%TEMP%\opencode\refs\hermes\hermes-agent\`。深度调研：`turnController.ts`（分段转写 + 乐观锁）、`state.py`（宠物状态机优先级）、`petFlashStore.ts`（瞬态 flash TTL）、`submissionCore.ts`（乐观忙锁 + 忙时输入）、`theme.ts`（种子主题）、`session-status-dot.tsx`。
> **结论**：Hermes 前端三大可借鉴机制——① 分段式消息渲染（内联产物落在叙述间）；② 宠物状态机（活动信号 → 优先级动画）+ 瞬态 flash；③ 乐观忙锁 + 忙时输入。全部作用于 **AnnotationCoach.tsx**（372 行独立组件，Coach 陪伴专属，不碰 ChatMessages 1500 行大文件）。

## 关键事实核查（hermes 深度）
- **分段转写**（turnController.ts `flushStreamingSegment` L398-430 / `pushInlineDiffSegment` L477-499）：流式文本封段（`segmentMessages`），内联产物（diff）先 `flushStreamingSegment` 落成独立叙述段，再插卡片——**卡片渲染在发生处，不粘到末尾**。
- **宠物状态机**（agent/pet/state.py:41-81 `derive_pet_state`）：优先级 error→FAILED > celebrate→JUMP > just_completed→WAVE > awaiting_input→WAITING > tool_running→RUN > reasoning→REVIEW > busy→RUN > IDLE。各表面喂**已跟踪信号**，零新事件管道。
- **瞬态 flash**（petFlashStore.ts:15 `flashPet(state, ms=1600)`）：回合结束/错误/好评时 1600ms 覆盖稳态，TTL 衰减。
- **乐观忙锁**（submissionCore.ts:37-39 `markSubmitting`）：提交瞬间同步置忙，防双击竞态。
- **忙时输入分派**（useSubmission.ts:182-225）：queue/steer/interrupt 三模式。

## 我们现状（已核实）
- `AnnotationCoach.tsx`（372 行）：浮动气泡 + struggle 卡点轮询（30s）+ 快捷键 + AI 标识。**C2 已加 mood 关键词检测**（celebrating/empathetic/curious → emoji + 淡色强调，`CoachBubble` 组件）。
- 消息渲染：`messages[]` 数组（user/coach 两态），流式 content 事件累加。**无分段**——若 Coach 在教学里出卡片，卡片是单独的 tool_result 事件，渲染逻辑未分段。
- 提交流程：`send()` 用 `sending` 布尔 + `attemptSend` 重试（AnnotationCoach.tsx:115-150）。**无乐观忙锁**，忙时输入直接忽略（`if (!content || sending) return`）。
- `UnifiedChatContext`：`isStreaming` 布尔（通用聊天），AnnotationCoach 独立 WS 客户端。

## 借鉴点

### H1. 分段式消息渲染（AnnotationCoach 气泡内）⭐ S-M 成本
借鉴 `flushStreamingSegment`：AnnotationCoach 的 coach 消息按 tool_result 边界拆成「叙述段 → 卡片段」交替渲染。
- **现状**：coach 流式 content 累加成一个气泡；若中途有 render_ui 卡片事件（Quiz/进度/LS 卡），卡片与叙述混在一起。
- **落地**：消息渲染时，把 `messages[]` 中 coach 消息按内容特征分段——遇 `chart` 类内容（`render_ui` 卡片）时，卡片作为独立块渲染在**当前叙述之后**（而非等整条消息结束）。**复用 ChatChartCard 组件**（已有 chart 契约）。
- 因 AnnotationCoach 用独立 WS + `handleEvent`（只处理 content/session/done/error），需**扩展 handleEvent 处理 tool_result 的 chart**，存独立 `cards[]` 数组，渲染时插在叙述间。

### H2. Coach 状态环 + 瞬态情绪 flash（升级 C2）⭐ S 成本
借鉴 `derive_pet_state` 优先级 + `petFlashStore` TTL。
- **现状**：C2 的 `detectCoachMood` 是静态关键词（消息级）。
- **落地**：浮动头像加**状态环**（环形指示器）——从现有信号派生：`sending`（busy→RUN 环）、`awaitingInput`（学生回合→WAITING 环，学生回合时暂停）、`messages[]` 尾部内容（推理→REVIEW 环）。优先级：卡点介入（struggle hint）→ 待输入 → 发送中 → 空闲。
- **瞬态 flash**：回合完成（sending 转 false）→ `wave` flash（1600ms）；评分高分（检测到 celebrating 消息）→ `jump` flash；错误（error 事件）→ `failed` flash。flash 覆盖稳态，TTL 衰减回稳态。
- **补强 C2**：现有 mood emoji 保留，状态环是「持续状态」，flash 是「情绪脉冲」，两者分层。

### H3. 乐观忙锁 + 忙时输入处理 ⭐ S 成本
借鉴 `markSubmitting` 同步置忙。
- **现状**：`send()` 的 `sending` 在点击后设置，`attemptSend` 重试期间用户可再点（虽然 `!content || sending` 挡住，但**无同步乐观锁**）。
- **落地**：`send()` 开头**同步**置 `sending=true`（在任何 await/重试前）；忙时输入弹轻提示（"我在分析上一个问题，稍等"）而非静默忽略。

## 不借鉴
- xterm 嵌入聊天（我们有原生 React 聊天）
- 完整宠物动画（VRM/Live2D，过度）
- 种子生成式主题重构（工程量过大，现有 CSS 变量够用）
- 忙时输入 steer/interrupt 完整三模式（教学场景 queue 即可）

## 优先级
| 优先级 | 项 | Effort | 说明 |
|--------|----|--------|------|
| **P0** | H2 Coach 状态环 + 瞬态 flash | S | 升级 C2，陪伴感最直接 |
| **P0** | H3 乐观忙锁 + 忙时提示 | S | 交互健壮性 |
| P1 | H1 分段式卡片渲染 | M | 卡片落在叙述间 |

## 实施顺序建议
先 H2（状态环 + flash，纯前端小改）→ H3（乐观锁）→ H1（分段渲染，涉及 handleEvent 扩展）。

## 复用与冲突
- H2 升级 C2（保留 mood emoji，加状态环 + flash 分层），不冲突
- H1 复用 ChatChartCard（chart 契约），扩展 AnnotationCoach handleEvent
- 不触碰 ChatMessages.tsx / annotation_tool*.html / 后端
