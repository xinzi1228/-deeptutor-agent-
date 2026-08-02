---
name: annotation-coach-flows
description: 标注教练的教学流程库。Phase 0 诊断、Phase 1 理论教学、Phase 2 实践练习的完整教学协议和决策分支。当标注教练需要教学流程指导、错误诊断策略、准备就绪判定规则时使用。
---

# 标注教练 — 教学流程库

为 `annotation-coach` 教学教练角色提供完整流程协议。

## 文件索引

| 阶段 | 文件 | 用途 |
|------|------|------|
| Phase 0 迎新诊断 | `references/flow-onboarding.md` | 7步诊断流程：识别身份→捕获动机→诊断对话→摸底测验→展示路线→记录+转场 |
| Phase 1 理论学习 | `references/flow-theory.md` | 7步教学循环：激活→讲解→检查→回应→错误分析→教学回授→门控 |
| Phase 2 实践练习 | `references/flow-practice.md` | 6步实践流水线：选任务→展示→等待→评测→反馈→记录 |
| 决策矩阵 | `references/decision-matrix.md` | 8张共用决策表：形成性评估、error→干预、readiness gate、check类型、提示梯、理论↔实践路由、rag映射、rubric |
| 资源索引 | `references/resources.md` | 标注领域权威资源：国标、教材、工具、就业信息 |
| 专家角色卡 | `references/experts/*.md` | 6 专家角色（learning_planner/session_steward/task_guide/struggle_detective/report_analyst/grading_expert），对应竞赛 6 模块，按教学阶段路由 |
| 专家索引 | `experts_manifest.json` | 专家角色索引（coordinator + 6 experts），divisions.json 风格，pytest 校验一致性 |

## 使用方法

```
read_skill("annotation-coach-flows", file="references/flow-onboarding.md")      # Phase0
read_skill("annotation-coach-flows", file="references/flow-theory.md")          # Phase1
read_skill("annotation-coach-flows", file="references/flow-practice.md")        # Phase2
read_skill("annotation-coach-flows", file="references/decision-matrix.md")      # 分支判断
read_skill("annotation-coach-flows", file="references/resources.md")            # 资源推荐
read_skill("annotation-coach-flows", file="references/experts/<expert_id>.md")  # 专家角色卡（按阶段路由）
```
