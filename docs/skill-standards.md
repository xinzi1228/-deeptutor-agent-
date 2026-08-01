# Skill 编写规范 — 本项目强制遵守

> 来源: DeepTutor 内置 skill-creator (77行)，全文采用
> 适用范围: annotation-coach PERSONA.md 及所有 references/ 子文件

---

## 5 条核心原则

### 1. 描述是唯一的触发器

LLM 只看到 skill 的 `description` 字段，据此决定是否加载全文。
正文里的任何内容在加载前 LLM 都看不见。

✅ 正确:
```yaml
description: 数据标注教练。诊断优先→理论→实践。始终中文。
```

❌ 错误:
```yaml
description: 数据标注教练。基于岗位能力图谱和专业知识库，用get_annotation_task获取课程任务，
用annotation_check评分，用write_memory/read_memory追踪学习进度。
集成了universal-diagnostic-tutor、education-agent-skills、teach、aetherviz-master、
learning-assessor的教学模式。始终用中文回复。
```

**违反后果:** LLM 不会加载此 skill → Coach 退化成一个普通 DeepSeek 对话机器人
→ 不调工具、不走流程 → **第一次测试时已发生**

### 2. 精简至上

Context 窗口共享。假定 LLM 已经很聪明，只加它不知道的内容。
每段自问: 这段配得上 token 代价吗？

✅: Persona 正文 ≤ 100 行，references 子文件各自 ≤ 500 行
❌: 把所有协议、案例、话术模板塞进一个文件

**违反后果:** Context 不够 → LLM 只看到前半段 → 后面的纠错分支/准备就绪判定被截断
→ 关键决策点 LLM "凭空发挥" → 教学质量不可控

### 3. 匹配自由度

高风险、易出错的序列 → 写死每一步（低自由度）
低风险、允许发挥的领域 → 只给原则和约束（高自由度）

✅: 纠错分支写死 8 种信号→动作；反馈话术给模板但允许调整
❌: 反馈话术写死逐字要求；纠错分支只说"根据情况灵活处理"

**违反后果:** 纠错写太松 → LLM 每次处理不同 → 有时直接给答案、有时追问太多
→ 教学效果不可预测

### 4. 渐进披露

Skill 正文是路由器和摘要（≤ 500 行）。
长内容（协议细节、案例、模板）放在 references/ 子文件中，
LLM 按需用 `read_skill(name, file="references/xxx.md")` 加载。

✅:
```
annotation-coach/
├── PERSONA.md (100行)              ← 路由器
└── references/
    ├── flow-onboarding.md (200行)   ← 按需加载
    ├── flow-theory.md (300行)
    ├── flow-practice.md (250行)
    ├── decision-matrix.md (150行)
    └── resources.md (80行)
```

❌: 所有内容塞在 PERSONA.md 里 1000+ 行

**违反后果:** LLM 一次性消化 1000 行指令 → 注意力分散 → 中间部分被忽略
→ 看起来流程完整，执行时跳过关键步骤

### 5. 无辅助文件

Skill 目录内不要放 README、changelog、setup 指南。
只放模型完成任务需要的协议文件。

✅: SKILL.md + references/ (纯教学协议)
❌: SKILL.md + README.md + CHANGELOG.md + todo.md + notes.md

**违反后果:** LLM 可能把 meta 文档当成教学协议读取 → 产生幻觉
→ "根据 CHANGELOG v3.2 的更新..." (根本不存在的版本号)

---

## 适用范围

- `deeptutor/services/persona/presets/annotation-coach/` 下所有 .md 文件
- 未来新增的任何 skill

## 每次修改后的检查清单

- [ ] description 一行说明"做什么 + 什么时候触发"？
- [ ] 单个文件 ≤ 500 行？
- [ ] 高风险路径（纠错/判定）写死了每一步？
- [ ] 低风险路径（反馈话术）给了原则但允许调整？
- [ ] 长内容拆分到了 references/ 中？
- [ ] 目录内没有 README/changelog 等辅助文件？
