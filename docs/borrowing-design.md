# 借鉴实施设计文档 — 开源 Agent 项目精华落地

> 关联调研: `docs/agent-projects-review.md`
> 状态: 设计稿。改代码前先对照本文件逐项验收。

---

## 设计原则

1. **不推翻现有诊断式教学体系** — 借鉴是对现有 flow 的增强，不是重写
2. **每个借鉴点有明确来源** — 注明来自哪个项目，可溯源
3. **改动最小、验收明确** — 每条给目标文件 + 验收标准
4. **兼容现有数据** — 记忆/记录格式演进不破坏已存数据

---

## P0 — 低成本高价值（改 prompt/流程/CLI）

### P0-1 意图分诊 (feynman-tutor)

**问题:** 现有 flow-onboarding Step0 只有"有/无记录"两分支。学生一句确认类问题（"IOU 0.5 够吗？"）也会走进度恢复流程，答非所问。

**方案:** 有记录分支下先分诊三种意图：

| 意图 | 信号 | Coach 动作 |
|------|------|-----------|
| 快速确认 | 一句话确认/小疑问 | 直接回答，以问题结尾，答完再问方向 |
| 续学 | "继续上次""接着练" | 从断点恢复，展示进度 |
| 深入/新方向 | 其他 | 从断点进入 Phase1/2，先复习弱项 |

**目标文件:** `flow-onboarding.md` Step0
**验收:** Coach 对"IOU 0.5 够吗？"直接回答而不是展示进度恢复

---

### P0-2 事实 vs 推理校准 (feynman-tutor)

**问题:** "三个绝不"里的"绝不直接纠错"过绝对。学生缺事实（定义/符号含义/工具机制）时，强制苏格拉底探问是浪费时间。

**方案:** Step3 先判断学生缺「推理」还是「事实」：

```
缺推理 (概念理解/方法选择) → 苏格拉底, 让他推
缺事实 (定义/符号/工具机制) → 直接给, 不卖关子
能推但要很久 → 看精力: 有兴致让他推, 累了接一把
```

**目标文件:** `flow-theory.md` Step3
**验收:** Coach 对"IOU 分母是什么"这类定义问题直接回答，对"为什么取交集"这类推理问题继续探问

---

### P0-3 记忆确认前置 (feynman-tutor)

**问题:** 当前 Coach 评测完直接写 learning record，学生可能不认可记录内容。

**方案:** 写 `write_learning_record` 前强制复述确认：

```
"我记一下: 本次 task2, F1=86%, 掌握: 多目标+小目标, 待改进: 边缘漏标。这样可以吗？"
→ 学生确认 → 写
→ 学生纠正 → 按纠正复述 → 再确认 → 才写
```

**目标文件:** `flow-practice.md` Step6、`flow-theory.md` Step6
**验收:** Coach 从不跳过确认直接写记录

---

### P0-4 三层学习者笔记 (feynman-tutor)

**问题:** synapse 记忆有 confidence/source/pattern/correction 四维，但 pattern 没有证据链——Coach 可能凭单次观察下"学生总是漏小目标"的结论。

**方案:** synapse 记录增强：

```json
{
  "type": "annotation_exercise",
  ...
  "error_pattern": null,
  "pattern_evidence": [           ← 新增: 证据链
    {"task_id": "task2", "scene": "图片边缘3个车漏标", "quote": "学生自述: 没看到右边"},
    {"task_id": "task4", "scene": "远处马漏标", "quote": null}
  ],
  "pattern_status": "unconfirmed"  ← 新增: unconfirmed | confirmed
}
```

**规则 (直接抄 feynman):**
- 一层: 学生明确约定的沟通规则 → preferences
- 二层: 跨 ≥2 次对话、证据充分的稳定模式 → `pattern_status=confirmed`
- 三层: 单次观察、未看清的 → 只记"什么场景做了什么"，不命名不归类，`pattern_status=unconfirmed`

**绝不允许:** 从一次观察直接升级成画像。三层记录随时间、证据充分后手动升二层。

**目标文件:** `PERSONA.md` 记忆系统节、`learning_records.py` 校验放宽（不强制 evidence）
**验收:** 单次练习记录里 error_pattern 带 evidence + unconfirmed，不参与 readiness 判断

---

### P0-5 教学法理论引用 (Vibe-learning-AgenticWorkflow)

**问题:** PERSONA 的教学决策无理论依据，评审（或深究的教师）会质疑"为什么这么设计"。

**方案:** PERSONA.md 加「设计依据」节，引用四条教学研究：

```
VanLehn(2011): 1:1 导师效果量 d=0.79 vs 大班课 d≈0.0
Bloom(1984):   2-sigma 问题 — 1:1 辅导比大班课高 2 个标准差
Chi(2005):     建构主义学习 > 被动接受
Flavell(1979): 元认知是学习效果核心调节变量
```

**目标文件:** `PERSONA.md` 开头
**验收:** PERSONA 中出现四条引用且与设计决策对应

---

### P0-6 CLI 教学命令 (Vibe-learning-AgenticWorkflow)

**问题:** CLI chat 只有 /cap /kb /tool 等基础设施命令，缺教学领域命令。

**方案:** 给 `deeptutor_cli/chat.py` 加 4 个教学命令：

| 命令 | 行为 | 实现 |
|------|------|------|
| `/resume` | 从记忆断点续学 | 向 Coach 注入消息"继续上次的进度" |
| `/progress` | 打印学习进度仪表盘 | 直接调 LearningRecordStore 聚合 |
| `/concept-map` | 打印能力图谱+掌握状态 | 直接调 competency_tree + records |
| `/challenge` | 出一道迁移挑战题 | 向 Coach 注入消息"出一道挑战题测试我" |

**实现要点:**
- `/progress` 和 `/concept-map` 是纯本地查询（不消耗 LLM），复用 profile.py 的聚合逻辑
- `/resume` 和 `/challenge` 复用现有 turn 流程，注入预置消息
- 抽取共享聚合函数，CLI 与 API 不重复实现

**目标文件:** `deeptutor_cli/chat.py`、`deeptutor/services/learning_records.py`（加聚合方法）
**验收:** CLI 里 `/progress` 打印任务数/F1/雷达，`/resume` 触发 Coach 续学

---

### P0-7 双 SOT 分离 (Vibe-learning-AgenticWorkflow)

**问题:** `learning_records.jsonl` 混着课程进度（theory_mastered / annotation_exercise）和学习者画像（diagnosis）。

**方案:** 记录加 `scope` 字段：

```json
{"type": "diagnosis", "scope": "learner", ...}
{"type": "annotation_exercise", "scope": "progress", ...}
```

聚合时: dashboard 用 `scope=progress`，画像用 `scope=learner`。向后兼容——旧记录无 scope 时按 type 推断（diagnosis→learner，其余→progress）。

**目标文件:** `learning_records.py`（append 时补 scope）、`profile.py`（聚合按 scope）
**验收:** `/api/v1/profile` 只统计 progress 记录；diagnosis 单独进画像字段

---

### P0-8 回答以问题结尾 (Vibe-learning-AgenticWorkflow)

**问题:** Coach 教学回合可能以陈述句结尾，学生被动接收。

**方案:** flow-theory Step3 加硬约束：

> 教学回合的回复必须以问题结束。例外: 仅当学生明确说"你直接讲/告诉我答案"。

**目标文件:** `flow-theory.md` Step3
**验收:** 教学回合回复均以问号结尾（除学生要求直讲）

---

## P1 — 中成本（加工具/小功能）

### P1-1 competency_map 前置依赖链 (Multi-Agent-Study-Assistant)

**问题:** 能力图谱是平面技能树，无前置依赖。readiness=step_down 时 Coach 只能凭经验回退。

**方案:** `competency_tree.json` 技能节点加 `prerequisites` 字段；`competency_map` 工具 node 查询时返回前置链；flow-theory Step6 的 step_down 判定优先用前置链。

**目标文件:** `competency_tree.json`、`competency_tool.py`、`decision-matrix.md` §3
**验收:** `competency_map node=skill-1-1-4` 返回其前置技能

---

### P1-2 教育学自检 (Vibe @edu-analyst)

**问题:** Coach 设计学习方案无教育学自检。

**方案:** flow-onboarding Step4 展示路线后加 3 问自检（内部判断，不展示给学生）:

```
自检 3 问:
1. 认知负荷: 这模块会不会一次塞太多？
2. ZPD: 起点是不是正好在学生能力边缘外一步？
3. 理论实践比: 是否符合该模式 (Zero-Base 4:6 / Standard 3:7 ...)？
自检不过 → 调整路线再展示
```

**目标文件:** `flow-onboarding.md` Step4
**验收:** Step4 展示前有自检逻辑，过载时精简

---

### P1-3 有界诊断 brief (lumen)

**问题:** Phase0 诊断产出散落在记忆里，没有结构化 brief 契约。

**方案:** 诊断完成时生成结构化 brief（不入 records，写 `workspace/learning/brief.json`）:

```json
{
  "goal": "找标注工作", "goal_type": "job",
  "diagnosed_level": "standard", "teaching_mode": "Standard",
  "modules": ["标注基础", "进阶技能", "质量管控", "工具进阶"],
  "priority_domains": ["图像数据标注"],
  "estimated_days": "5-7天"
}
```

**目标文件:** `learning_records.py`（加 save_brief / get_brief）、`flow-onboarding.md` Step5
**验收:** 诊断后有 brief.json，下次会话能读取

---

### P1-4 课程范围 RAG (lumen)

**问题:** rag 无范围限定，Phase1 讲解可能检索到无关模块内容。

**方案:** flow-theory Step1 讲解时，rag 查询限定当前模块关键词前缀（如 `模块2:`），或用 `kb_files` 定位模块文档后 rag。

**目标文件:** `flow-theory.md` Step1
**验收:** 讲解某模块时 rag 查询带模块限定

---

## P2 — 高成本（基础设施，本期不实施，仅记录）

| # | 借鉴 | 说明 |
|---|------|------|
| P2-1 | 学习者状态 MCP server (edumcp) | learning_records 暴露为 MCP 资源 |
| P2-2 | 可重跑建课 (lumen) | 建课流程幂等化/可取消 |
| P2-3 | 可视化 subagent 转交 (feynman) | IOU 3D 演示走 subagent 产出路径 |
| P2-4 | 决策审计 UI (lumen) | "为什么推荐这个任务"可追溯 |

---

## 实施顺序

```
第一批 (prompt/flow, 无代码):  P0-1 → P0-2 → P0-3 → P0-5 → P0-8
第二批 (记忆/记录 schema):      P0-4 → P0-7
第三批 (CLI + 工具):            P0-6 → P1-1
第四批 (流程增强):              P1-2 → P1-3 → P1-4
最后: 同步 skill 副本 → 全链路回归
```

## 验收总清单

- [ ] 意图分诊: 确认类问题直接答
- [ ] 事实vs推理: 定义直接给、推理才探问
- [ ] 记忆确认: 写记录前复述等确认
- [ ] 三层笔记: 记录带 pattern_evidence + pattern_status
- [ ] 理论引用: PERSONA 有 VanLehn/Bloom/Chi/Flavell
- [ ] CLI: /resume /progress /concept-map /challenge 可用
- [ ] 双 SOT: records 分 scope=learner / scope=progress
- [ ] 回答以问题结尾: 教学回合以问号结束
- [ ] skill 副本与 presets 副本一致
- [ ] Coach 全链路对话回归正常
