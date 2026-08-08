# 第七轮优化设计：Coach 快捷语面板（借鉴 PetPhrase）

> 日期：2026-08-08。来源：`chengbuilds/PetPhrase`（Windows 桌宠常用语管理器，Rust + Slint，MIT）。已 clone 到 `%TEMP%\opencode\refs\petphrase\PetPhrase\`。深度调研：`logic.rs`（chip/卡片混排 + use_count 频率排序 + 贴宠定位）、`main.rs copy_item`（点→动画→自动收闭环）、`anim.rs`（PetState + 帧循环 + once 回 idle）。
> **结论**：PetPhrase 的「点 chip → 动画反馈 → 自动收」交互范式 + chip 混排 + 使用频率排序，直接适配我们 Coach 的快捷反馈语——学生一键发送「夸一下/给思路/换一题」等教学快捷语，Coach 即时响应。

## 关键事实核查（PetPhrase 深度）
- **混排布局**（logic.rs `layout_group` L124-142）：短句（≤10 字符无换行）→ 气泡 chip 流式排布；长句 → 独占卡片。`by_use` 按 use_count 降序，**同频保手动序**，`phrase_idx` 回源不错位。
- **点短语闭环**（main.rs `copy_item` L809-869）：复制 → use_count+1 落盘**但不重排列表**（点击瞬间不跳动）→ pet wave 动画反馈 → 非常驻 200ms 自动收面板 / 常驻 ✓ 800ms 自清。
- **动画**（anim.rs）：PetState（idle/wave/run/failed/review/jump），once 播放回 idle。
- **我们现状**：AnnotationCoach.tsx 已有 H1-H3（messages/cards/sending/awaitingInput/flash/hint + `flashCoach()` H2 + `send()` H3 + CoachBubble）。**无快捷语机制**。

## 借鉴点

### P1. Coach 快捷语 chip 栏 ⭐ S 成本
借鉴 `layout_group` 的 chip 混排 + `copy_item` 的反馈闭环：
- **快捷语常量** `QUICK_PHRASES`：4 类（表扬/提示/推进/求助），每类 2-3 条，i18n 本地化（`annotation.quick.*`）。
- **chip 栏**：气泡底部、输入框上方一排 chip（短句 → chip 流式）。短句判定仿 `is_short`（无换行且 ≤10 字符）。
- **使用频率排序**：`useCount`（`Record<string, number>`）点击 +1，localStorage 持久化，同组内按 use_count 降序（同频保预设序）。**点击不重排**（PetPhrase 借鉴：点击瞬间列表不跳动）。
- **发送**：`sendQuickPhrase(text)` 复用 `send()` 的 WS payload 逻辑，但**跳过忙时提示分支**（快捷语不抢焦点——忙时静默忽略或排队）。
- **反馈**：点 chip → 发送 + `flashCoach()`（wave）+ chip `copied` 状态 800ms ✓ 高亮（复用 H2 的 flash 机制）。

## 不借鉴
- 剪贴板复制（教学场景直接发送给 Coach，非外部复制）
- 贴宠定位/常驻跟随（Web 浮动气泡已固定右下角）
- 后端可配置快捷语（用户增删）——YAGNI，静态预设 + 频率排序体验已够
- 全局快捷键（Web 场景不适用）

## 优先级
| 优先级 | 项 | Effort | 说明 |
|--------|----|--------|------|
| **P0** | P1 快捷语 chip 栏 | S | 一键发送 + 频率排序 + wave flash 反馈 |

## 实施顺序建议
单一任务：QUICK_PHRASES 常量 + chip 栏渲染 + sendQuickPhrase + useCount 排序 + flash 反馈 + i18n。

## 复用与冲突
- 复用 `send()` 的 WS 逻辑、`flashCoach()`（H2）、`CoachBubble` 样式
- 新增 `useCount` state + localStorage key（`annotation.coach.quick.uses`）
- 不触碰 ChatMessages.tsx / annotation_tool*.html / 后端 / PERSONA
