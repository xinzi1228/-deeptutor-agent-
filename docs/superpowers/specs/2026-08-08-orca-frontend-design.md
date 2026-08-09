# 第八轮优化设计：前端状态点原语 + 时长反馈规范（借鉴 stablyai/orca）

> 日期：2026-08-08。来源：`stablyai/orca`（YC-backed "AI Orchestrator"，Electron React IDE + 移动伴侣）。已 clone 到 `%TEMP%\opencode\refs\orca\orca\`。深度调研：`AgentStateDot.tsx`（状态点原语 + 状态词汇表 + a11y label）、`AgentWorkingSpinner.tsx`（相位同步 spinner）、`docs/STYLEGUIDE.md`（时长反馈规则 + 单色设计纪律 + 兄弟组件一致性）。
> **结论**：Orca 前端最可借鉴的是「**状态点原语 + 统一状态词汇表**」和「**时长反馈匹配规则**」。我们前端当前无共享状态点原语（各组件内联 STATUS_RING/Loader2），无时长反馈规范。单独立项，**实施留待后续**（当前优先竞赛交付材料）。

## 关键事实核查（Orca 深度）
- **状态点原语**（AgentStateDot.tsx）：`AgentDotState` 类型（working/blocked/waiting/interrupted/failed/done/idle/permission）+ `agentStateLabel()` 每状态 a11y 标签 + 渲染（working=黄 spin / done=emerald check / waiting=琥珀问号 / blocked=红点 / idle=灰点）。状态点与图标分离（"谁" vs "什么状态"）。
- **相位同步 spinner**（AgentWorkingSpinner.tsx）：CSS 动画跑 compositor，`getAnimations().startTime=0` 同步 late-mount 相位；`prefers-reduced-motion` 停用。
- **时长反馈规则**（STYLEGUIDE.md:270-294）：0-100ms 无反馈 / 100ms-1s 仅禁用 / 1-3s 禁用+spinner / 3s+ 阶段标签。**预占空间**（width 非 min-width）+ **远端慢时延迟 200ms 显示加载**。
- **单色设计纪律**：中性灰承载 chrome，颜色只留给状态；`color-mix(in srgb, var(--token) 12%, var(--background))` 做色调不造 hex；token 成对。

## 我们现状（已核实）
- **无共享状态点原语**：Coach 状态环（H2）是 AnnotationCoach 内联 `STATUS_RING`；ChatComposer 内联 `Loader2 animate-spin`；无跨组件统一的"状态词汇表"。
- **无时长反馈规范**：提交按钮只有 `disabled` + `Loader2`，无 3s+ 阶段标签、无预占空间纪律。
- 已有 CSS 变量体系（--primary/--border 等，globals.css）。

## 借鉴点（单独立项，后续实施）

### O1. 共享状态点原语 + 状态词汇表 ⭐ S 成本
借鉴 AgentStateDot：抽一个跨组件共享的 `AgentStateDot` 组件（放 `web/components/common/`）。
- `AgentDotState` 类型 + `agentStateLabel()`（a11y）+ 渲染（working spin / done emerald check / waiting amber 问号 / blocked 红点 / idle 灰点）。
- **统一状态词汇表**：Coach 状态环（H2）、专家任务卡（Orca 看板）、提交按钮等所有"状态"共用此原语，色值对齐 Orca（yellow=working/emerald=done/amber=waiting/red=blocked/gray=idle）。
- 现 H2 的 STATUS_RING 迁移到用该原语（或保持 ring 样式但色值对齐词汇表）。

### O2. 时长反馈规范（STYLEGUIDE UX 规则）⭐ S 成本
借鉴 Orca 的时长反馈表 + 预占空间 + 延迟加载：
- **提交按钮**：0-100ms 无反馈 / 100ms-1s 禁用 / 1-3s 禁用+spinner / 3s+ 阶段标签（如"分析中…/生成中…"）。
- **预占空间**：会变长的标签用 `width` 固定 footprint，避免点击瞬间布局跳动。
- **延迟加载**：本地快操作不显示 spinner（<200ms），慢操作才显示。

### O3. 单色设计纪律（可选）⭐ S 成本
借鉴 Orca：颜色只留给状态，中性灰承载 chrome；`color-mix` 做色调不造 hex。我们已有 CSS 变量，补纪律文档即可。

## 不借鉴
- Electron 桌面壳 / WebGL 终端 / xterm 序列化（Web 平台不适用）
- 移动伴侣应用（E2EE WS + Expo，工程量大）
- View Transition 看板列间动画（专家任务卡立项后再定）

## 优先级
| 优先级 | 项 | Effort | 说明 |
|--------|----|--------|------|
| **P0** | O1 状态点原语 + 词汇表 | S | 跨组件统一状态语言 |
| **P0** | O2 时长反馈规范 | S | 交互反馈质量 |
| P1 | O3 单色纪律 | S | 设计系统一致性 |

## 实施顺序建议
先 O1（状态点原语，为 Coach 状态环/专家卡提供基础）→ O2（时长反馈）→ O3（纪律文档）。**单独立项，当前先完成竞赛交付材料后再实施。**

## 复用与冲突
- O1 与 Coach 状态环（H2）色值对齐，不冲突（H2 保持 ring 样式，色值改用词汇表）
- O2 与 ChatComposer 现有 Loader2 兼容（只加阶段标签/预占纪律）
- 不触碰 ChatMessages.tsx / annotation_tool*.html / 后端
