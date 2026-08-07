# 第二轮优化设计：借鉴开源项目（记忆/多Agent/教学）

> 日期：2026-08-06。来源：本轮调研 clone `Li-Evan/Bloom`（中文苏格拉底家教）、`NirDiamant/Agent_Memory_Techniques`（30 个记忆实践）；搜索 `tutor-gpt`（Theory-of-Mind）、`HKUDS/nanobot`（轻量多agent+记忆）、`TeleAI-UAGI/telemem`（语义去重）、`topoteretes/cognee`（KG记忆）+ 既有借鉴 Mem0/LangGraph/Swarm/feynman。目标：优化 2026-08-05 完成的记忆分区、总控 AgentLoop、拟人化 Coach。

---

## 一、记忆体系（议题①②，对应 8/5 记忆分区 Phase 1-3）

### O1. 记忆路由 Fallback（Memory-Routing #17）⭐ P0
**借鉴**：路由不确定时回退搜所有 store 合并结果（librarian 先分诊，不确定就翻全馆）。
**现状**：`store.read_bucket(bucket)` 只读 `L2/<bucket>/*.md` + L3 全局。route_input 判断区出错 → 记忆检索直接落空。
**设计**：`read_bucket(bucket, *, fallback=True)`：当前区内容命中不足（L2 该区无 .md 或条目 < N）→ 自动回退读全局 L2 根 + L3，返回 `{content, source: "bucket"|"fallback", buckets_hit: [...]}`。`ReadMemoryTool` 透传。
**改动面**：`store.read_bucket` + `ReadMemoryTool`（`deeptutor/tools/builtin/`）+ 测试。
**验收**：区 A 无内容时查询 → 回退返回全局；区 A 有内容 → 仅返回区 A + L3。

### O2. 检索增强 Hybrid+RRF+MMR（Memory-Retrieval #20）P1
**借鉴**：BM25 + 语义 + Reciprocal Rank Fusion 重排 + MMR 多样性。kb_search 已有 hybrid BM25。
**现状**：记忆检索无重排/多样性。
**设计**：记忆区多条 L2 命中时按 Recency + 关键词重叠简单重排（不加 cross-encoder，教学延迟敏感）；保留 1 条/主题 去冗余。
**改动面**：`read_bucket` 排序 + 去重；可选。

### O3. 遗忘标记而非硬删（Forgetting #19 + Mem0 expiration）P1
**借鉴**：指数衰减 + 访问强化；**safeguard**（关键事实如过敏/法律约束不可剪）+ Mem0 `expiration_date` 隐藏不删。
**现状**：L2 ADD-only 永不删 → 记忆无限膨胀，噪音淹没信号。
**设计**：L2 条目支持 `## stale` 标记（过时隐藏，不物理删）；consolidator audit 时 LLM 判断过时 → 打标记；**safeguard**：preferences/不可变槽永不打 stale。
**改动面**：`document.py` 标记 + `meta.py` + audit prompt；教学规模小，P1。

### O4. 生产模式轻量（Production #30）P2
**借鉴**：缓存 + TTL + 观测。
**设计**：教学单用户，仅加"读记忆结果进程内缓存 30s"即可；观测依赖 trace-log 已有。**低优先**。

## 二、总控 / 多 Agent（议题⑦，对应 8/5 delegate AgentLoop）

### O5. 专家 Private Scratchpad + 写权限收敛 ⭐ P0
**借鉴**：Multi-Agent Shared Memory #22——每个 agent 有自己的 cutting board（私有），只把完成结果放共享 recipe book；namespace 访问控制。
**现状**：6 专家白名单含 `write_learning_record` / `log_decision` → 专家在隔离回合内**直接写共享学习记录/决策日志**，中间结论可能污染共享记忆。
**设计**：
1. **写权限收敛**：专家白名单移除 `write_learning_record`（学习记录只由总控写）；`log_decision` 保留给需审计的专家（grading/report）或也收敛。
2. **私有 scratchpad**：delegate 的 `metadata["scratchpad"]` 记录专家中间工具结果（trace 可见），不落 L2/L3。
3. **总控落盘**：总控收到专家结论后统一 `write_learning_record`（已有链路）。
**改动面**：`delegate_expert_tool.py` 白名单 + PERSONA 委派节 + 测试（断言专家白名单不含写记忆工具）。
**验收**：委派 grading_expert 后共享学习记录无专家中间产物；总控自行写记录。

### O6. 冲突解决记录（#22 last-write-wins）P2
**借鉴**：多 agent 同时更新同一事实 → 版本检查。
**现状**：单用户教学，多专家不同时写；consolidator 已有 dedup/merge。**低优先**，记录冲突到 trace 即可。

## 三、拟人化 Coach + 教学流程（议题④3a + Coach 设计）

### O7. Syllabus 进度勾选联动（Bloom）⭐ P1
**借鉴**：Bloom 每次学习后更新 syllabus 掌握项 `[ ]`→`[x]` + 进度表；**启动新课题同轮出大纲+首篇**；**评估篇**触发课程完结自动生成总结。
**现状**：competency_tree + teaching_flow 已有能力树与 6 步流程，但无"可验证目标清单逐项勾选 + 自动总结"闭环。
**设计**：Coach 教学闭环加"目标清单卡片"（render_ui `progress_card` 复用 progress 契约）——每次标注任务后更新目标勾选；掌握项全勾 → Coach 出综合评估任务 → 完结总结。联动议题③ 能力树。
**改动面**：PERSONA 教学流程节 + 前端 progress 卡片（已有 ChartData.progress）+ 可选后端目标清单存储。
**验收**：完成一组任务后目标清单逐项变勾，全勾触发评估。

### O8. 行内思维快照（Bloom `???`）P1
**借鉴**：用户在文档中直接标 `???` 即时疑问，优先级高于文末反馈。
**设计**：标注台/练习中支持学生随时标"这里有疑问"（前端按钮），Coach 优先回应。Phase 3b 实时反馈时一并做。
**改动面**：前端（Phase 3b 规划内）。

### O9. 苏格拉底节奏约束（Bloom ≤2 问 + tutor-gpt ToM）P2
**借鉴**：每次衔接最多 2 个苏格拉底问题，到点必出下一步；tutor-gpt Theory-of-Mind 推断学生心智。
**设计**：PERSONA 加节奏硬约束"每轮追问 ≤2 个，问完必推进"；ToM 增强（推断学生困惑点）P2 可选。
**改动面**：PERSONA 教学节奏节。

### O10. 学习日志渐进式加载（Bloom logging.md）P1
**借鉴**：每次对话先读根目录 learning-log 了解整体状态，**渐进式加载**不全量。
**现状**：Coach 读记忆 `read_memory`/`read_bucket` 全量返回文本。
**设计**：`read_bucket` 返回结构化概览（每区条目数 + 主题）+ 命中下钻全文；Coach 先概览再精读。与 O1 fallback 合并实现。
**改动面**：`store` + 工具 + 测试。

## 四、LS / 标注（议题④）

### O11. AI 辅助标注教学（CVAT ML backend 思路）P2
**借鉴**：CVAT ML backend 预标注；spec 4.3 已设计——预标注正确→新手练手；预标注错误→找错训练。
**现状**：未实现。Phase 3b/3c 规划内。

---

## 五、优先级与实施顺序

| 优先级 | 项 | 改动面 | 对应昨天优化 |
|--------|----|--------|-------------|
| **P0** | O1 路由 fallback | store + ReadMemoryTool + 测试 | 记忆分区 P1/P3 |
| **P0** | O5 专家写权限收敛 | delegate 白名单 + PERSONA + 测试 | 总控 Phase 2 |
| P1 | O10 渐进加载（并入 O1） | store + 工具 | 记忆分区 |
| P1 | O7 syllabus 进度联动 | PERSONA + 前端 progress 卡片 | 教学闭环 |
| P1 | O3 遗忘标记 | document/meta/audit | 记忆分区 |
| P2 | O2/O4/O6/O8/O9/O11 | 各异 | 待规划 |

**本轮建议**：实施 P0 两项（O1 + O5，后端可控、测试快、直接修复昨天优化缺口）；P1 项逐步跟进。
