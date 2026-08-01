# Phase 1: 理论学习 — 设计文档

## 概述

学生在 Chat 页面与 Coach 进行苏格拉底式对话学习。每个知识点遵循
"检索激活 → 正式讲解 → 先解释后探问 → 渐进建构 → 教学回授 → 记录推进"
的教学循环。

**设计参考来源：**

| 来源 | 借用了什么 |
|------|----------|
| **education-agent-skills / Retrieve-First Gate** | 讲新内容前先让学生回忆已知 + 自信度评分 → 只教缺口 |
| **education-agent-skills / Explain-First Interrogator** | 学生先解释 → Coach 探问最弱环节（≤3轮）→ 不直接纠错 |
| **education-agent-skills / Progressive Hint Ladder** | 学生卡住时 6 级渐进提示 → 绝不给答案 → reflection 要求 |
| **education-agent-skills / Teach-Back Evaluator** | 学生教 Coach（AI 角色扮演"Alex"）→ 3维评分验收 |
| **education-agent-skills / Adaptive Hint Sequence** | 4 层提示结构（策略→概念→程序→底线） |
| **Bloom** | 每次只出一个概念、掌握门控、苏格拉底 ≤ 2 轮 |
| **Coze 工作流** | DAG 节点+连线结构 → Persona 的 references/ 拆分 |
| **DeepTutor / Mastery Path** | "引擎算数，模型教书" → annotation_check 算 IOU，Coach 决定反馈 |

---

## 学习循环（每个知识点）

```
Step 0: 检索激活（Retrieve-First Gate）
│  先问"上次学了什么？"+"你现在对这概念了解多少？"
│  → 肯定正确部分 → 指出缺失 → 从缺失处开始
├─ Step 1: 正式讲解
│  调 rag 搜索知识库，只讲缺口（≤ 200 字 / 次）
│  调 competency_map 定位技能树位置
│  引用来源 "根据 GB/T 41867-2022 §4.3..."
├─ Step 2: 理解检测（Explain-First Interrogator）
│  学生用自己的话解释 → Coach 找最弱环节 → 探问（≤ 3 轮）
│  ├─ 正确 + 高自信(≥7) → 跳过 Step3 → Step4
│  ├─ 正确 + 低自信(≤4) → 再测 1 次
│  └─ 错误 → Step3 纠错分支
├─ Step 3: 纠错分支
│  ├─ 错误 + 高自信 → 认知冲突（给反例，不直接纠错）
│  ├─ 错误 + 低自信 → 换方式重新讲
│  └─ 卡住不说话 → Progressive Hint Ladder L0→L5
├─ Step 4: 教学回授（Teach-Back Evaluator）
│  Coach 扮演 Alex: "我完全不知道这概念，教教我"
│  3维评分: 连贯性/完整性/误解风险 (各1-3分)
│  通过(≥2/2/2) → Step5 | 不通过 → 修正后重新回授
└─ Step 5: 记录 + 推进
    write_memory → 显示 Mini进度图 → 判断下一步
    → 有对应实践任务? "去标注工作台验证" : 推进下一个知识点
```

## 实现位置

所有流程细节实现在 Persona 的 references/ 目录中：
- `PERSONA.md` — 核心原则 + 流程入口
- `references/flow-onboarding.md` — Phase 0 迎新诊断
- `references/flow-theory.md` — Phase 1 理论学习（含完整 DAG + 渐进提示梯）
- `references/flow-practice.md` — Phase 2 实践练习（含逐框反馈模板）
- `references/decision-matrix.md` — 所有分支决策表

路径: `deeptutor/services/persona/presets/annotation-coach/`
