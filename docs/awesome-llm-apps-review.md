# awesome-llm-apps 借鉴分析

> 项目: Shubhamsaboo/awesome-llm-apps (129k⭐) — 100+ LLM 应用/Agent/RAG 模板
> 定位: 可运行的多智能体/RAG/记忆应用模板集, 覆盖 17 个分类
> 关联: 我们已借鉴 EverOS(记忆)/TradingAgents(对抗评估)/lumen/MetaGPT 家族

---

## 一、与我们最相关的 3 个模式

### 1. Self-Improving Agent Skills — 技能自改进循环 (最有价值)

> Google ADK 三智能体循环, Karpathy autoresearch 方法论:
> 上传 skill → Executor 生成测试场景+评分标准 → 三 agent 迭代优化

| Agent | 角色 | 做的事 |
|-------|------|--------|
| **Executor** | 运行+评分 | 对测试场景运行 skill, 按评分标准打分 |
| **Analyst** | 失败诊断 | 检查失败评估, 定位根因, 推荐变异策略 (Pydantic 结构化输出) |
| **Mutator** | 提示编辑 | **只做恰好一个**有针对性的改动 (Pydantic 结构化输出) |

**核心纪律: 一次只改一个点。** 测试 → 诊断 → 单一修复 → 重测。

**可借鉴到我们:** coach 的教学 flow 文件 (PERSONA.md + references/) 可以加"教学自改进"：
- 用对抗性评估 (evaluate_teaching_plan) 作为 Executor 的"测试+评分"
- Analyst 角色 = 我们已有的独立评估员 (质疑认知负荷/ZPD)
- Mutator 纪律 = 每次只改一个教学环节, 不是大改
- 产出: 教学流程版本化 + 改动日志

### 2. Corrective RAG (CRAG) — 纠正式检索

> LangGraph 多阶段: 检索 → **相关性评分** → **查询改写** → **web fallback**

```
User Query → 检索 (Qdrant) → 相关性评分 (LLM)
  ├─ 够相关 → 回答
  └─ 不够 → 查询改写 → 重试 / web fallback
```

**可借鉴到我们:** 我们 rag 无相关性校验。可加：
- 检索后 LLM 评分相关性
- 低相关 → 查询改写 (加当前模块限定) 重试
- 仍低 → 明确告知"知识库无此内容"，不硬凑

这正好补上我们 P1-4 课程范围 RAG 的"范围校验"环节。

### 3. AI Teaching Agent Team — 分工产出独立文档

> CrewAI 4 角色教学团队, 每个产出独立 Google Doc:
> Professor(知识库) + Academic Advisor(学习路径) + Research Librarian(资源) + Teaching Assistant(练习)

**可借鉴到我们:** 教学组件作为**独立可读交付物**，而非只有 JSON：
- 我们已有 course_plan (JSON) → 可生成"学习路径文档"
- 我们已有 task_bank → 可生成"练习手册"
- 用 docx/pptx skill 产出 → 学生/教师可读、可打印

---

## 二、其他相关分类一览

| 分类 | 数量 | 对我们价值 |
|------|------|-----------|
| RAG 应用 | 21 | CRAG/Agentic RAG 思路 |
| 多 Agent 团队 | 13 | Teaching Team 已分析 |
| 记忆应用 | 6 | EverOS 已覆盖, 我们更完善 |
| MCP Agent | 5 | Multi-Router 是"多 agent 分派", 我们单 Coach 不需要 |
| Agent Skills | 5 | Self-Improving 最值得 |
| Starter Agents | 12 | 通用演示, 领域不匹配 |

---

## 三、落地建议 (按价值)

### P0 — 教学流程自改进循环 (Self-Improving 借鉴)

**现状:** coach 的教学 flow 文件是静态的。对抗性评估 (evaluate_teaching_plan) 已能质疑方案，但没有"应用修复→版本化→改动日志"闭环。

**借鉴方案:**
```
教学自改进 (可手动/定期触发):
  1. 选定一个教学环节 (如 flow-theory Step3)
  2. evaluate_teaching_plan 对抗性审查 → 质疑点 + 修正建议
  3. 采纳**一条**修正 (Mutator 纪律: 一次一个点)
  4. 记录到 teaching_changelog.json (版本 + 改动 + 理由)
  5. 保留原版 (版本化, 可回滚)
```

**落地:** 新增 `TeachingChangelog` store + `improve_teaching_flow` 工具 + 审计。

### P1 — CRAG 相关性校验

**落地:** `rag_tool` 检索后加相关性评分 → 低相关查询改写重试。补 P1-4 的范围校验。

### P1 — 可读教学交付物

**落地:** 用 docx skill 从 course_plan + task_bank 生成"学习路径手册.docx"，供教师/学生/评审阅读。

---

## 四、结论

awesome-llm-apps 是**模板集合**（129k⭐），不是单一架构。对我们的价值集中在 3 个可移植模式：

1. **Self-Improving 循环**（测试→诊断→单点修复→版本化）— 让 coach 教学流程自我进化，与我们已有的对抗性评估闭环互补
2. **CRAG 相关性评分** — 让 rag 检索有"够不够相关"的校验
3. **独立教学交付物** — 教学组件从 JSON 升级为可读文档

不建议照搬: 4 角色 CrewAI 教学团队 (依赖 Google Docs/Composio 外部服务, 我们单 Coach 已更完善)、Multi-MCP Router (我们单 Coach + always-on 工具已够)。
