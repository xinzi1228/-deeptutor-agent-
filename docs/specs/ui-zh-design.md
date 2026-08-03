# 界面全中文化改造设计（UI 默认中文）

> 状态: 设计已获用户批准
> 日期: 2026-08-02

---

## 1. 背景与目标

标注星图是面向职教的中文教学产品，但打开后界面默认全英文。探索确认：

- **前端已高度 `t()` 化**：硬编码英文 JSX 文本节点仅 1 处（VisualizationViewer 标题，已下线模块）；属性字面量 11 处且都是合理技术占位符（`gpt-4o`/`sk-...`/GitHub/Label Studio）
- **zh locale 完整且高质量**：2770 keys 零缺失，核心 UI 词（主页/数据标注/进度/记忆/设置/聊天/发送）全中文化
- **真正根因**：**默认语言是 `"en"`**——4 处默认值把产品锁死在英文，zh 翻译齐全也不生效
- **后端工具/PERSONA 已中文**：teaching_flow 等工具输出中文，PERSONA 规则"始终用中文"

**目标**：产品开箱即用即中文界面；保留 en/zh 切换能力（用户可切回英文）。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 默认语言 | 改为 `"zh"`（4 处默认值），非重建 |
| 2 | en 保留 | 不删 en locale、不动切换逻辑——默认改 zh，能力保留 |
| 3 | 兜底清理 | 少量硬编码英文中文化 + 后端英文文案抽查 |
| 4 | 验证 | 后端 pytest + 前端 tsc/build + Playwright 冒烟 |

## 3. 改造方案

### 3.1 Part A — 默认语言切换（根因修复，4 处）

| 文件 | 改动 |
|------|------|
| `web/context/app-shell-storage.ts:65` | `normalizeLanguage`：默认 `"zh"`（`return value === "zh" ? "zh" : "en"` → 默认 zh） |
| `web/context/app-shell-storage.ts:69` | `readStoredLanguage`：SSR/无存储 → `"zh"` |
| `web/context/AppShellContext.tsx:72` | SSR `useState<AppLanguage>("en")` → `"zh"` |
| `web/i18n/init.ts:9,27` | `normalizeLanguage` 空值 → `"zh"`；`fallbackLng` → `"zh"` |

注意 SSR 与客户端 hydration 一致：`AppShellContext` 的 `useState("zh")` 与 `readStoredLanguage()` 无存储返回 `"zh"` 必须同步（原注释 "Always start with en to match SSR" 的用意是防止 hydration mismatch——改 zh 时两边一起改）。

### 3.2 Part B — 兜底清理

| 项 | 处理 |
|----|------|
| `web/components/visualize/VisualizationViewer.tsx` 硬编码 "Visualization" 标题 | 包 `t()` 或改中文 |
| 设置页 `placeholder="gpt-4o"`/`sk-...` 等 | 保留（技术占位符本就英文）；若有对应 zh 键则用 t() |
| 后端返回给前端的英文文案（错误消息/空态） | 抽查 profile/tools API，能中的中文化，不能的保留（Coach 输出已中文） |

### 3.3 Part C — 验证

1. 后端 pytest 全量（无回归）
2. 前端 `tsc --noEmit` 0 错误 + `next build`
3. 冒烟（Playwright）：
   - 打开 `/` → 侧边栏「主页/数据标注/进度/记忆/设置」
   - 登录页「登录」；Settings 页「提供商连接/模型列表/诊断」
   - 切 en → 可回英文
4. `tests/i18n-placeholders.test.ts` 检查是否需补"默认 zh"断言

## 4. 测试

| 层 | 测试 |
|----|------|
| 单元 | `tests/i18n-placeholders.test.ts` 检查默认语言相关 |
| 集成 | 前端 tsc + build |
| 冒烟 | Playwright 默认中文 + 切 en 回退 |

## 5. 明确不做

- 不删 en locale、不移除语言切换入口
- 不做全面后端英文文案中文化（Coach 已中文，仅抽查 profile/tools 空态）
- 不动 UI 布局/样式

## 6. 风险

- **hydration mismatch**：SSR 默认 `"zh"` 与客户端 `readStoredLanguage()` 无存储 `"zh"` 必须同步，否则 React 水合警告
- 极端：用户 localStorage 曾存过 `"en"` → 仍显示英文（这是预期，切换能力保留；`writeStoredLanguage` 不变）
