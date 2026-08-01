# agency-agents 借鉴分析 — 专家角色写作方法论

> 项目: msitarzewski/agency-agents (137.9k⭐, 343 文件) — "指尖上的完整 AI 代理机构"
> 定位: 数百个即插即用的 AI 专家角色 (.md)，安装到 Claude Code/Cursor/Codex/OpenCode 等
> 关联: 我们的 Persona 系统 (annotation-coach) — 角色写作模式的直接参照

---

## 一、核心机制

```
divisions.json      ← 元数据: 每个 division(目录) → label/icon/color, CI 校验一致性
  engineering/ (58)  marketing/ (36)  specialized/ (57)  sales/ (9) ...
    <agent>.md      ← 专家角色本体 (frontmatter + 专业结构)
scripts/install.sh  ← 安装到各种工具
```

### agent .md 结构 (sales-coach.md, 21KB 示例)

**Frontmatter:**
```yaml
---
name: Sales Coach
description: Expert sales coaching specialist focused on rep development...  # 唯一触发器
color: "#E65100"
emoji: 🏋️
vibe: Asks the question that makes the rep rethink the entire deal.  # 一句话角色氛围
---
```

**正文 10 节:**
| 节 | 内容 | 我们的对应 |
|----|------|-----------|
| Identity & Memory | 角色/性格/记忆/经验 (Socratic, observant...) | PERSONA 核心原则 |
| Core Mission | 使命 + **数据支撑** ("91.2% quota attainment...") | 设计依据 |
| 专业领域分解 | Pipeline Review / Call Coaching / Deal Strategy | flow 文件 |
| Critical Rules | 纪律 (Coaching Discipline / Review Integrity) | 硬约束 |
| **Technical Deliverables** | 交付模板: Coaching Plan / Pipeline Review / Ramp Plan | ❌ 缺 |
| Workflow Process | Step1-4: Observe→Design→Coach→Measure | flow 步骤 |
| Communication Style | 沟通风格 | 交互规范 |
| Learning & Memory | 记忆 (每个 rep 的发展区/模式/反馈历史) | 记忆系统 |
| **Success Metrics** | 成功指标 | ⚠️ 部分 (F1≥0.85) |
| Advanced Capabilities | 规模扩展 | ❌ |

---

## 二、对我们最有价值的 3 个借鉴

### 1. Success Metrics — 系统化教练成功指标 (P0)

**现状:** 我们的 PERSONA 只有"五级 F1≥0.85 / 四级质检≥95%"两个指标。

**借鉴:** 用我们已有的数据源定义教练 KPI:
```
Coach 成功指标 (全部可从现有 API 取):
  1. 学员 F1 提升率       — (最新F1 - 首任务F1) / 首任务F1
  2. 教学模式适配度        — 连续 advance 次数 / 教学模式切换合理性
  3. foresight 命中率      — /api/v1/profile/foresights (已实现)
  4. pattern 确认率        — unconfirmed → confirmed 升级数 (Reflection 已实现)
  5. 教学自改进次数        — TeachingChangelog 版本数 (已实现)
  6. 决策审计完整性        — 每次任务推荐都有 log_decision (已实现)
```
**落地:** PERSONA 加"成功指标"节 + 个人中心加"教练绩效"面板。

### 2. vibe — 一句话角色氛围 (P0)

**现状:** PERSONA frontmatter 只有 name/description。

**借鉴:** 加 `color`/`emoji`/`vibe`:
```
vibe: 诊断优先的苏格拉底教练 — 先弄清学生为什么错，再决定教什么。
```
**落地:** 前端角色选择器可展示 emoji + vibe 氛围。

### 3. Technical Deliverables — 交付模板 (P1)

**现状:** 我们有 flow 流程但无结构化交付文档模板。

**借鉴:** 定义教练交付物模板 (对应 agency 的 Coaching Plan):
```
学习诊断报告   — Phase0 产出 (已有 brief.json, 可渲染为文档)
练习评测报告   — Phase2 产出 (annotation_check 结果 + 缺口 + 建议)
进步周报       — 每周 F1 趋势 + 模式确认 + 下一步
```
**落地:** 复用 docx 生成能力 (P1b 已实现) 生成这些模板。

---

## 三、与我们的对比结论

| 维度 | agency-agents | 我们 | 差距 |
|------|--------------|------|------|
| 角色写作 | 10 节专业结构 + frontmatter 元数据 | 9 条原则 + 流程 | 缺 Deliverables/Metrics/vibe |
| 角色数量 | 数百个可插拔 | 1 个教练 | 可加"质检专家/就业顾问"子角色 |
| 数据支撑 | 引用行业数据 | 引用教学研究 | 已较好 |
| 安装分发 | 多工具 app | 内置 preset | 不需要 |
| 交付物 | 结构化模板 | JSON + docx | 可增强模板 |

**不建议借鉴:** 数百角色的膨胀 (我们是领域垂直平台, 单教练+工具更聚焦)、divisions.json CI 机制 (我们 preset 已够)。

---

## 四、落地建议 (按优先级)

1. **P0: PERSONA frontmatter 增强** — 加 color/emoji/vibe
2. **P0: PERSONA 成功指标节** — 教练 KPI (F1提升/foresight命中/自改进次数)
3. **P1: 个人中心教练绩效面板** — 展示上述 KPI
4. **P1: 交付模板** — 学习诊断报告/练习评测报告 docx

---

## 五、结论

agency-agents 137.9k⭐ 的核心是**专家角色的写作方法论**——"专业、有数据支撑、有交付物、有成功指标"。对我们的直接价值是把 annotation-coach 从"流程严谨"升级为"专业可衡量"：
- 成功指标让教练可被评估 (评审加分)
- vibe 让角色有识别度
- 交付模板让学生拿到可读报告 (已可 docx 生成)
