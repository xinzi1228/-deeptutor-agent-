# 标注教练 — 完整设计文档

## 项目概述

DeepTutor 标注教学平台。面向职业教育的 AI 数据标注工程师岗位智能教学教练。

**核心定位：** 诊断优先的苏格拉底式 AI 导师。学生对话学习+标注实操，Coach 驱动全流程。

**技术基础：** DeepTutor (31k⭐) + Label Studio (28k⭐) + 19 个教学 skill

---

## 一、系统架构

```
用户 → Chat 页面 (WebSocket)
  │
  ▼
AgenticChatPipeline
  ├── Persona: annotation-coach (PERSONA.md + references/)
  ├── Tools: annotation_check / get_annotation_task / competency_map / job_analysis / rag
  ├── Skills: annotation-guide / universal-diagnostic-tutor / learning-assessor / teach
  └── Memory: read_memory / write_memory (synapse 四维 JSON)
  │
  ▼
标注实操 (annotation_tool.html / Label Studio)
  │ postMessage/localStorage
  ▼
Coach 评测反馈 → 学习记录 → 个人中心可视化
```

---

## 二、完整学习流程

### Phase 0: 迎新与诊断 (flow-onboarding.md, 166行)

**目标:** 确诊学生水平，选定教学模式，规划学习路线。不教任何概念。

```
Step0: read_memory → 有记录? → 展示进度从断点继续 : 进入诊断
Step1: MISSION 捕获 → "为什么学标注？" → job/cert/course/interest
Step2: 诊断对话 ≤3轮 → 自然聊天提取教学模式信号
Step3: 摸底测验 ≤3分钟 → Zero-Base跳过 / 概念层1题 / 有经验task6摸底
Step4: 展示4模块路线 + 预估时长
Step5: write_memory + 加载 Phase1/2
```

**三种教学模式判定:**

| 信号 | 模式 | 特点 |
|------|------|------|
| 完全零基础 | Zero-Base | 8步beginner序列, ≤150字/次, 先理解"是什么"再学"怎么做" |
| 有概念/做过 | Standard | teach→check→continue, ≤200字/次, 理论实操交替 |
| 有经验/老手 | Advanced | 压缩已知, ≤300字/次, 只在薄弱点停留 |

**学习路线 (course-designer 模块化):**

| 模块 | 预估 | 理论 | 实践 | 目标 |
|------|------|------|------|------|
| 1. 标注基础 | 3-5天 | IOU/F1/格式 | task1,3,5 | F1≥0.7 |
| 2. 进阶技能 | 5-7天 | 遮挡/小目标/多标签 | task2,4,6,7,9 | F1≥0.85 |
| 3. 质量管控 | 3-4天 | 质检/错误分析 | task8+LS全流程 | 能自检互检 |
| 4. 工具进阶 | 2-3天 | LS/CVAT/格式转换 | LS项目 | 对��四级标准 |

---

### Phase 1: 理论学习 (flow-theory.md, 185行)

**目标:** 每次只教一个概念块。教完就停。等学生回应。根据回应调整下一步。

**三个绝不:** 不塞多概念 · 不直接纠错 · 不分回合全做完

```
Step0: 检索激活 (Retrieve-First Gate)
  "你听过这个概念吗？" → 只教缺口

Step1: 讲解 (cognitive_load_budget)
  Zero-Base: 8步beginner序列, ≤150字
  Standard: rag+competency_map, ≤200字, 引用来源
  Advanced: 压缩已知, ≤300字

Step2: 理解检测 (understanding_check)
  7种检查选1种 → 出1题 → 停等答案

Step3: 回应学生 (mastery_signal_interpretation)
  Ask vs Explain 先判断 → 信号→行动 → ≤3轮探问

Step4: 错误分析 (mistake_analysis)
  粗心 vs 概念 → 只修最小缺口

Step5: 教学回授 (Teach-Back)
  扮演Alex → 学生教 → 3维评分 (连贯/完整/误解风险)

Step6: 门控+记录 (readiness_gate)
  6种判定 → write_memory → 模块完成生成学习参考
```

**渐进提示梯 (L0-L5):**
```
L0 诊断 → L1 概念问 → L2 类比 → L3 原理提醒 → L4 步骤提示 → L5 近完整支架
绝不给最终答案
```

**教学模式切换:**
- 连续3次advance → 升模式
- 连续2次失败 → 降模式
- 学生说"太简单/跟不上" → 立即切换

---

### Phase 2: 实践练习 (flow-practice.md, 153行)

**目标:** 每次一个任务。诊断式对话。先正确后缺口。推进凭证据。

**三个绝不:** 不列菜单 · 不一个回复塞评分+分析+修复+下一步 · 不放水推进

```
Step1: 选任务 (readiness驱动, 12种信号判定)
Step2: 展示任务 (发完即停, 不教怎么做)
Step3: 等待提交 (检查格式)
Step4: 评测 (annotation_check → 内部形成判断)
Step5: 反馈 (3个回合, 每个回合等回应):
  回合1: Verdict + 正确部分 → 停
  回合2: 缺口 + 诊断问题 → 停
  回合3: 修复 + 下一步建议 → 停
Step5a: 处理三种反应 (重试/继续/回理论) → 先诊断再回应
Step6: 记录 (write_memory JSON) + 推进 (6种readiness)
```

**7要素回答顺序 (answer_grading_protocol):**
```
Verdict → 正确部分 → 缺口 → 错误类型 → 修复 → 门控 → 下一步
```

**三种学生反应处理 (multiturn_tutoring_protocol):**
- "重试" → 不给同题, 给对齐练习或先修复缺口
- "继续" → 凭readiness判定, 不放水
- "回理论" → 不翻整个模块, 只讲卡住的那一点

---

### 决策矩阵 (decision-matrix.md, 156行)

两个Phase共用的8张分支决策表:

| § | 内容 | 行数 | 引用方 |
|---|------|------|--------|
| 1 | 形成性评估 [正确性×自信度] 4象限 | 15 | flow-theory Step3, flow-practice Step5 |
| 2 | 9种标注错误→教学干预映射 | 25 | flow-theory Step3, flow-practice Step5 |
| 3 | 6种 readiness 判定 | 30 | flow-theory Step6, flow-practice Step1/6 |
| 4 | 7种理解检查方式选择指南 | 15 | flow-theory Step2 |
| 5 | L0-L5 渐进提示梯触发条件 | 20 | flow-theory Step3 |
| 6 | 理论↔实践路由决策 | 25 | 全流程 |
| 7 | rag关键词→错误类型映射 | 15 | flow-practice Step5 |
| 8 | 4维标注 Rubric | 11 | flow-practice Step5 |

---

## 三、Skill 集成总览

### 已完全集成 (14个)

| Skill | 集成方式 | 落点 |
|-------|---------|------|
| universal-diagnostic-tutor | 15个协议借用 | 6个 flow 文件 |
| education-agent-skills | 5个教学模式 | flow-theory |
| learning-assessor | 4维rubric + 5维分析 | decision-matrix §8 |
| course-designer | 模块化课程设计 | flow-onboarding Step4 |
| teach (mattpocock) | 学习参考生成 | flow-theory Step6 |
| annotation-guide | 重构为6文件 | builtin skills |
| skill-creator | 编写规范 | docs/skill-standards.md |
| synapse | 四维记忆模型 | PERSONA.md |
| scaffold-exercises | 三层结构 | flow-practice |
| tutor-learn-path | 学习路线规划 | flow-onboarding |
| tutor-practice | 练习+评分+诊断 | flow-practice |
| tutor-state-card | 跨会话状态 | PERSONA.md |
| tutor-resource-scan | 权威资源索引 | resources.md |
| teaching-resource-generator | 题目设计原则 | flow-theory Step2 |

### 已注册待实现 (2个)

| Skill | 能力 | 状态 |
|-------|------|------|
| teach | HTML Lesson生成 | 流程中已标注, 等前端工程 |
| aetherviz-master | 3D交互演示 | 流程中已标注, 等前端工程 |

### 按需调用 (3个)

docx/pptx/pdf/xlsx — 生成学习报告/教学课件 (需沙箱 code_execution)

---

## 四、文件结构

```
deeptutor/services/persona/presets/annotation-coach/
├── PERSONA.md (88行)           ← 8条核心原则 + 1条硬性节奏约束
│                                   工具注册 + 记忆格式 + 流程入口
│
└── references/
    ├── flow-onboarding.md (166行) ← Phase 0: 迎新诊断
    ├── flow-theory.md (185行)     ← Phase 1: 理论学习
    ├── flow-practice.md (153行)   ← Phase 2: 实践练习
    ├── decision-matrix.md (156行) ← 共用分支决策表 (8张)
    └── resources.md (55行)        ← 标注领域权威资源索引

总计: 6个文件, 803行
```

**加载机制:** LLM通过 `read_skill(name, file="references/flow-xxx.md")` 按需加载当前阶段的流程。不一次性全吞 (progressive disclosure)。

---

## 五、记忆系统

**格式:** 结构化 JSON (synapse 四维模型)

```json
{
  "type": "theory_mastered | annotation_exercise | diagnosis",
  "task_id": "task2",
  "knowledge_point": "多目标检测",
  "f1": 0.85, "precision": 0.90, "recall": 0.81,
  "difficulty": "medium",
  "confidence": 0.9,           // synapse: 置信度
  "source": "explicit",        // synapse: explicit/implicit/correction
  "error_pattern": null,       // synapse: 重复行为模式
  "teaching_mode": "Standard",
  "readiness": "advance",      // readiness_gate: 6种判定
  "signal_type": "...",
  "difficulty_adjustment": {...},  // 6维难度调整
  "teach_back_score": "3/3/2",
  "skill_growth": "+5% vs task1",
  "knowledge_points": ["多目标检测", "小目标标注"],
  "session_summary": "本模块掌握了...",
  "timestamp": "2026-07-31T10:00:00"
}
```

**读写时机:** 每次对话开始(read_memory) + Phase完成(write_memory)

---

## 六、工具清单

| 工具 | 用途 | 调用阶段 |
|------|------|---------|
| read_memory | 读取学习历史 | 每次对话开始 |
| write_memory | 记录学习进度 | 每Phase完成 |
| competency_map | 查询能力图谱 | Phase0全景 + Phase1定位 |
| get_annotation_task | 获取练习任务 | Phase2选任务 |
| annotation_check | 评测标注结果 | Phase2评测 |
| rag | 搜索知识库 (60篇) | Phase1讲解 + Phase2反馈 |
| job_analysis | 人才需求分析 | Phase0 (学生问就业时) |
| code_execution | 生成Mini进度图 | Phase每轮结束 |
| read_skill | 加载流程/知识文件 | 切换Phase时 |

---

## 七、知识库

| 资源 | 内容 | 格式 |
|------|------|------|
| annotation-guide skill | 标注速查手册 (6文件) | read_skill 加载 |
| annotation_kb/ | 60篇专业知识 (6领域) | rag 搜索 |
| task_bank.json | 9个分级练习任务 | get_annotation_task 调取 |
| competency_tree | 45节点能力图谱 | competency_map 调取 |

---

## 八、待实施任务

### P0 — 系统可用的基础

- [ ] 启动 DeepTutor + 验证 annotation-coach Persona 加载
- [ ] 验证 Coach 调工具 (competency_map / job_analysis / get_annotation_task / annotation_check)
- [ ] 走通完整链路: 诊断 → 学 IOU → 检查 → task1 标注 → 评测 → 反馈 → 记录

### P1 — 学习体验

- [ ] 个人中心页面 (ECharts/Chart.js 雷达图+技能树+F1曲线)
- [ ] Mini进度图生成 (code_execution + matplotlib)

### P2 — 交互演示

- [ ] IOU 实时计算交互演示 (Canvas, 参考 aetherviz-master UI)
- [ ] HTML Lesson 生成 (teach skill, 模块完成后自动生成)

### P3 — 工程化

- [ ] Label Studio 一键启动 (compose.yaml 集成)
- [ ] 学习报告生成 (docx/pptx)

---

## 九、设计约束 (skill-standards.md)

所有 Persona 文件的 5 条强制规则:

1. **描述是唯一的触发器** — description 一行说清"做什么+何时触发"
2. **精简至上** — 单个文件 ≤ 500 行
3. **匹配自由度** — 高风险写死步骤, 低风险给原则
4. **渐进披露** — 正文路由, 长内容入 references/
5. **无辅助文件** — 目录只放协议, 不放 README/CHANGELOG

---

## 十、文件索引

```
项目根目录/
├── docs/
│   ├── V1-DESIGN.md              ← V1 初始设计文档
│   ├── skills-inventory.md       ← 19个skill完整清单
│   ├── skill-standards.md        ← skill编写5原则
│   ├── future-tasks.md           ← 两大未实现潜力
│   └── specs/
│       ├── phase0-onboarding.md  ← Phase0 早期设计
│       └── phase1-theory.md      ← Phase1 早期设计
│
└── deeptutor/
    ├── services/persona/presets/annotation-coach/
    │   ├── PERSONA.md            ← 教练核心 (88行)
    │   └── references/           ← 流程协议 (715行)
    ├── skills/builtin/annotation-guide/
    │   ├── SKILL.md              ← 标注速查路由器
    │   └── references/           ← 5个子文件
    └── tools/
        ├── annotation_check.py   ← 标注评测引擎
        ├── task_bank_tool.py     ← 题库工具
        ├── competency_tool.py    ← 能力图谱工具
        ├── job_analysis_tool.py  ← 人才分析工具
        └── label_studio_tool.py  ← LS集成工具
```
