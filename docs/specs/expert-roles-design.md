# 多专家角色体系设计（Expert Roles — 借鉴 agency-agents）

> 状态: 设计已获用户批准
> 日期: 2026-08-02

---

## 1. 背景与目标

标注星图产品当前是**单 annotation-coach 角色**完成所有教学（诊断/计划/理论/练习/反馈/报告），通过 flow 协议 + 14 工具 + TeachingFlowEngine 支撑。竞赛文档描述的是"6 模块系统"与"6 人团队分工"。

**本次目标**：借鉴 `msitarzewski/agency-agents`（即插即用 AI 专家角色系统）+ `jnMetaCode/agency-orchestrator`（DAG 编排 + 验收自动核验），把教学升级为**多专家角色体系**：
1. **A. 6 专家角色集**：对应竞赛 6 模块，每个按 agency-agents 的 frontmatter + Identity/Mission/Rules/Capabilities/Processes/Deliverables 结构封装；annotation-coach 作为总协调者按阶段路由。
2. **B. 轻量编排**：TeachingFlowEngine 增加"阶段→专家路由" + "自动 readiness 验收"（评测后自动判定推进）。
3. **C. 专家索引 + CI 校验**：`experts_manifest.json`（divisions.json 风格）+ pytest 一致性校验。

**借鉴来源**：
- `msitarzewski/agency-agents`：agent 角色封装标准（frontmatter: name/description/color/emoji/vibe；正文: Identity & Memory / Core Mission / Critical Rules / Core Capabilities / Processes & Deliverables）、部门目录 + divisions.json 索引 + CI 一致性校验
- `jnMetaCode/agency-orchestrator`：多专家协作编排 + **验收自动核验**（auto-verified acceptance）——教学场景落为轻量（线性流程无需完整 DAG）
- 现有基础：annotation-coach PERSONA.md 已用相同 frontmatter（name/description/color/emoji/vibe）；decision-matrix readiness_gate 6 判定已是"验收核验"雏形

**明确不做**：
- 完整 DAG 编排器（教学是本质线性流程——诊断→计划→理论→练习→反馈，无真实并行/复杂分支；重构已验证的 TeachingFlowEngine 收益低风险高）
- 技能/工具并入统一索引（技能已有 `skill taxonomy`，工具已有注册+测试，各自成体系）

## 2. 设计决策汇总（已确认）

| # | 维度 | 决策 |
|---|------|------|
| 1 | 多专家形态 | 6 专家角色集（对应竞赛 6 模块），annotation-coach 总协调按阶段路由 |
| 2 | B 编排 | 轻量：TeachingFlowEngine 加"阶段→专家路由" + 评测后自动 readiness 验收 |
| 3 | C 索引 | 专家索引（divisions.json 风格）+ pytest 一致性校验（目录↔索引双向 + frontmatter 完整） |
| 4 | 专家文件位置 | `deeptutor/skills/builtin/annotation-coach-flows/references/experts/*.md`（与 flow-* 平级） |
| 5 | 索引位置 | `deeptutor/skills/builtin/annotation-coach-flows/experts_manifest.json` |

## 3. A. 6 专家角色集

### 3.1 专家清单（对应竞赛 6 模块）

| 专家 id | 名称 | 模块 | 核心职责 | 核心工具/数据 |
|---------|------|------|---------|--------------|
| `learning_planner` | 学习计划师 | ①学习计划引擎 | 诊断后建课程计划、模块化路线、目标对齐 | finalize_diagnosis / course_plan |
| `session_steward` | 会话管家 | ②会话管理器 | 会话恢复、断点续学、记忆管理、跨会话上下文 | read_memory / write_memory |
| `task_guide` | 任务引导师 | ③任务引导引擎 | 选任务、展示、等待、评测推进、6 步协议 | teaching_flow / get_annotation_task |
| `struggle_detective` | 困难检测师 | ④困难检测介入 | 卡住信号检测、介入建议、阻塞报告 | struggle_detect / log_decision |
| `report_analyst` | 学习报告师 | ⑤学习报告插件 | 进度/雷达/图谱/成就报告、可视化 | graph_query / achievements / chart_cards |
| `grading_expert` | 练习批改师 | ⑥练习批改引擎 | 评测、反馈、错误分析、readiness 判定 | annotation_check / grading |

### 3.2 专家角色文件结构（借鉴 agency-agents）

每个专家一个 markdown 文件，结构：

```markdown
---
name: <expert_id>
description: <一句话职责>
color: "#<hex>"
emoji: <emoji>
vibe: <角色气质一句话>
---

# <专家名> Agent

你是<专家名>，专注<职责>。

## 🧠 你的身份与记忆
- **角色**: ...
- **人格**: ...
- **记忆**: 你记住的领域模式
- **经验**: 你的背景

## 🎯 你的核心使命
### <任务域 1>
- 职责描述...

## ⚠️ 你必须遵守的规则
### <规则域>
- 规则（引相应 flow 协议 / 工具 / readiness_gate）...

## 🛠 你的核心能力
### 工具与数据
- **工具**: ...
- **数据源**: ...

## 📋 你的流程与交付物
### 流程
- ...
### 交付物
- ...
```

- 每个专家只覆盖自己模块，不越界（借鉴 mathmodel 阶段边界）
- 关键规则必须引用现有的 flow 协议（flow-onboarding/flow-theory/flow-practice/decision-matrix）与工具名（保持与代码/索引一致）
- 中文内容，与产品语言一致

### 3.3 annotation-coach 协调者更新

`PERSONA.md` 增加"专家协作"节：

```markdown
## 专家协作（多专家角色体系）

你是总协调者。按教学阶段路由到对应专家视角，调用专家角色卡的规则：

| 阶段 | 路由专家 |
|------|---------|
| 诊断/建课 | learning_planner |
| 会话恢复/记忆 | session_steward |
| 选任务/推进 | task_guide |
| 卡住/介入 | struggle_detective |
| 进度/报告 | report_analyst |
| 评测/反馈 | grading_expert |

切换专家视角时，遵守对应专家角色卡的 Core Mission + Critical Rules。
```

同步到 workspace persona 副本（gitignored，运行时生效）。

## 4. B. 轻量编排（TeachingFlowEngine 增强）

### 4.1 阶段→专家路由

`deeptutor/services/teaching_flow.py` 新增：

```python
EXPERT_ROUTE: dict[str, str] = {
    "onboarding": "learning_planner",      # 诊断/建课
    "theory": "learning_planner",          # 理论教学
    "select_task": "task_guide",
    "show_task": "task_guide",
    "waiting": "task_guide",
    "evaluate": "grading_expert",
    "feedback": "grading_expert",
    "record": "report_analyst",
    "struggle": "struggle_detective",
    "report": "report_analyst",
    "session": "session_steward",
}

class TeachingFlowEngine:
    def expert_route(self, stage: str) -> str:
        """Map a teaching stage to its expert role id."""
        return EXPERT_ROUTE.get(stage, "task_guide")
```

- `teaching_flow` 工具的 query 返回附带 `expert`（当前阶段对应专家 id），让 Coach 知道当前用哪个专家视角
- 阶段名：任务级 6 步（select_task...record）+ 会话级宏观阶段（onboarding/theory/report/session/struggle）——宏观阶段从 records 推断（有诊断→onboarding 完成；在理论环节→theory 等），实现时用可注入/简化的推断

### 4.2 自动 readiness 验收

`annotation_check` 评测 bbox 后（on_evaluated 时），**自动判定 readiness**：

| F1 | readiness | 动作 |
|----|-----------|------|
| ≥ 0.85 | `advance` | 升难度/下一任务 |
| 0.7 ≤ F1 < 0.85 | `advance_with_caution` | 同难度新任务，开头先测 |
| 0.65 ≤ F1 < 0.7 | `more_practice` | 同概念+同难度+不同数据 |
| < 0.65 | `review_first` | 回 Phase1 补缺口 |

- 写入 flow_state（evaluate 步骤的 `readiness` 字段）+ 学习记录（annotation_exercise 的 readiness 字段）
- 阈值常量可配置（`READINESS_THRESHOLDS`）
- Coach 可覆盖（`teaching_flow` advance 时带 readiness 参数覆盖默认），默认自动判定

## 5. C. 专家索引 + 校验

### 5.1 `experts_manifest.json`（divisions.json 风格）

放 `deeptutor/skills/builtin/annotation-coach-flows/experts_manifest.json`：

```json
{
  "_note": "教学专家角色索引（Source of truth）。每个条目对应 references/experts/<id>.md。pytest 校验目录与索引双向一致 + frontmatter 完整。",
  "coordinator": {
    "id": "annotation_coach",
    "label": "标注教练",
    "icon": "🎯",
    "color": "#3B82F6",
    "file": "personas/annotation-coach/PERSONA.md"
  },
  "experts": [
    {"id": "learning_planner", "label": "学习计划师", "icon": "🗺️", "color": "#10B981", "file": "references/experts/learning_planner.md"},
    {"id": "session_steward", "label": "会话管家", "icon": "💬", "color": "#6366F1", "file": "references/experts/session_steward.md"},
    {"id": "task_guide", "label": "任务引导师", "icon": "🧭", "color": "#F59E0B", "file": "references/experts/task_guide.md"},
    {"id": "struggle_detective", "label": "困难检测师", "icon": "🕵️", "color": "#EF4444", "file": "references/experts/struggle_detective.md"},
    {"id": "report_analyst", "label": "学习报告师", "icon": "📊", "color": "#8B5CF6", "file": "references/experts/report_analyst.md"},
    {"id": "grading_expert", "label": "练习批改师", "icon": "✅", "color": "#06B6D4", "file": "references/experts/grading_expert.md"}
  ]
}
```

### 5.2 pytest 一致性校验 `test_experts_manifest.py`

- **双向一致**：索引中每个条目的 file 存在于磁盘；references/experts/ 下每个 .md 都有索引条目
- **frontmatter 完整**：每个专家文件含 name/description/color/emoji/vibe 五字段
- **id 一致**：frontmatter name == 索引 id == 文件名（去扩展名）
- **协调者存在**：PERSONA.md frontmatter 完整

## 6. 测试与验证

| 组件 | 测试 |
|------|------|
| 专家文件 | frontmatter 完整（5 字段）+ name/id/文件名一致（pytest） |
| 索引 | 目录↔索引双向一致（pytest） |
| expert_route | 阶段→专家映射正确（pytest） |
| 自动 readiness | F1 各阈值判定正确（pytest：0.85/0.7/0.65 边界） |
| teaching_flow query | 返回附带 expert 字段 |
| 回归 | 全量 pytest + 前端 tsc |

## 7. 实施任务划分（供 writing-plans 细化）

1. 6 专家角色文件（experts/*.md）+ annotation-coach PERSONA 协作节（preset + workspace 副本同步）
2. `experts_manifest.json` + `test_experts_manifest.py` 一致性校验
3. TeachingFlowEngine `expert_route` + teaching_flow query 附带 expert
4. annotation_check 自动 readiness 验收（阈值 + flow_state/records 写入 + Coach 可覆盖）
5. 全量回归 + 冒烟
