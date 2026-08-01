# 学习者知识图谱设计文档（Knowledge Graph Engine）

> 关联调研: `docs/everos-review.md`（EverOS 记忆借鉴）、`docs/regression-report.md`（回归发现）
> 借鉴来源: cognee（ECL 流水线 + GRAPH_COMPLETION 图增强检索的设计模式，不引入其重依赖）
> 状态: 设计稿。改代码前先对照本文件逐项验收。

---

## 1. 设计原则

1. **轻量重实现，渐进演进** — 用 NetworkX（已在依赖中）+ JSON 持久化复刻 cognee 的"图存储 + 图查询"精华，零新增依赖；若未来查询复杂度超限再考虑引入 cognee 库。
2. **JSONL 仍是唯一 truth** — 知识图谱是**派生索引**，可随时从 JSONL + competency_tree + task_bank 重建；图损坏不影响学习记录。
3. **确定性图构建与查询** — 图构建/图遍历全部确定性规则，无 LLM 调用，可重跑可单测（对齐 `build_course_plan` 风格）。
4. **LLM 只做解释层** — 风险链结论由确定性图算法得出（不会错），LLM 仅生成自然语言解释；解释失败降级为纯结构化返回。
5. **本体与学习痕迹分存** — competency_tree/task_bank 静态本体从 JSON 读，图上只存学习痕迹（掌握度/挣扎边）的增量，避免重复存储本体。

---

## 2. 架构概览

```
写入层（确定性）              图存储                查询层（确定性）           解释层（LLM）
┌────────────────┐   ┌─────────────────────┐   ┌─────────────────┐   ┌──────────────────┐
│ write_learning_│   │ KnowledgeGraphStore  │   │ GraphQueryService│   │ GraphQueryTool    │
│ record /       │──▶│ (NetworkX + JSON)    │◀──│  · risk_path    │──▶│ (Coach 工具)      │
│ log_decision   │   │ workspace/learning/  │   │  · concepts     │   │  确定性结果        │
│ finalize_      │   │ knowledge_graph.json │   │  · mastery      │   │  + LLM 解释       │
│ diagnosis      │   └─────────────────────┘   └─────────────────┘   └──────────────────┘
└────────────────┘             ▲ 增量更新
                               │
                     competency_tree.json (本体种子: 4层树 + prerequisites)
                     task_bank.json        (任务↔技能外键: knowledge_points)
```

---

## 3. 组件拆分

### 3.1 `deeptutor/services/knowledge_graph.py` — 图存储（核心新服务）

**`KnowledgeGraphStore`** — 负责图构建、增量更新、序列化。

| 方法 | 签名 | 职责 |
|------|------|------|
| `build` | `build(*, tree, bank, records) -> dict` | **纯函数**：从能力树 + 任务库 + 学习记录重建整图（确定性、可重跑，与 `build_course_plan` 同风格） |
| `incremental_update` | `incremental_update(record) -> dict` | 写入学习记录后**增量**更新掌握度/挣扎边（避免每次全量重建） |
| `get` / `save` | `get() -> dict` / `save(graph) -> Path` | 原子读写 `knowledge_graph.json` |
| `ensure_seeded` | `ensure_seeded(tree, bank) -> dict` | 首次构建时从本体种入静态节点/边（Skill/Task/TaskGroup/本体边） |

**图数据模型（JSON 结构）**：

```json
{
  "schema_version": 1,
  "built_at": "ISO-UTC",
  "source": "deterministic_graph_builder",
  "nodes": {
    "skill-1-1-1": {"type": "Skill", "name": "边界框绘制规范", "level": 4},
    "skill-1-1-2": {"type": "Skill", "name": "遮挡目标处理", "level": 4},
    "task2": {"type": "Task", "name": "交叉路口行人检测", "difficulty": "easy"},
    "task-group-1": {"type": "TaskGroup", "name": "图像数据标注"},
    "learner:default": {"type": "Learner", "name": "当前学习者"}
  },
  "edges": [
    {"source": "skill-1-1-2", "type": "prerequisite", "target": "skill-1-1-1"},
    {"source": "task2", "type": "requires", "target": "skill-1-1-1"},
    {"source": "learner:default", "type": "mastered", "target": "skill-1-1-1",
     "evidence": "practice", "f1": 0.82, "ts": "..."},
    {"source": "learner:default", "type": "struggling", "target": "skill-1-1-2",
     "evidence": "practice", "f1": 0.65, "ts": "..."},
    {"source": "task2", "type": "belongs_to", "target": "task-group-1"}
  ]
}
```

**节点类型**：`Skill`(29 个技能叶子) / `Task`(task1-9) / `TaskGroup`(4 组) / `Learner`。
**边类型**：

| 边 | 方向 | 来源 | 用途 |
|----|------|------|------|
| `prerequisite` | 技能→前置技能 | competency_tree `skill.prerequisites` | 风险链下探 |
| `requires` | 任务→所需技能 | task_bank `knowledge_points` | 任务风险评估 |
| `belongs_to` | 任务→任务组 | task_bank 分类 | 概念导航 |
| `mastered` | Learner→技能 | records: F1≥0.7 或 readiness∈{advance,advance_with_caution} | 掌握度 |
| `struggling` | Learner→技能 | records: F1<0.7 或 error_pattern status=confirmed | 风险信号 |

**确定性规则（对齐现有 `LearningStats.facts()`）**：
- `mastered`: 练习 F1≥0.7 **或** theory readiness ∈ {advance, advance_with_caution}
- `struggling`: 练习 F1<0.7 **或** 同一 error_pattern ≥2 次 confirmed

### 3.2 `deeptutor/services/graph_query.py` — 图查询（确定性，返回结构化子图）

**`GraphQueryService`**：

| 方法 | 签名 | 职责 |
|------|------|------|
| `risk_path` | `risk_path(target) -> dict` | **风险链推理**：查目标(技能/任务)的前置依赖，标出未掌握/挣扎的技能，沿 `prerequisite`/`requires` 下探找受影响的下游技能/任务 |
| `concepts` | `concepts(skill_id) -> dict` | 概念关系导航：`{prerequisites, dependents, tasks, belongs_to}`（替代 skill_tree 的运行时遍历） |
| `mastery_snapshot` | `mastery_snapshot() -> dict` | 学习者掌握度：`{mastered, struggling, next_suggested}`（将 facts() 落到图） |

**`risk_path` 输出契约**：

```json
{
  "target": "skill-1-1-2",
  "target_name": "遮挡目标处理",
  "missing_prereqs": [{"id": "skill-1-1-1", "name": "边界框绘制规范"}],
  "struggling": [{"id": "skill-1-1-2", "name": "遮挡目标处理", "f1": 0.65}],
  "affected_downstream": [
    {"id": "task4", "name": "十字路口多目标检测", "via": "requires", "reason": "依赖'遮挡目标处理'"}
  ],
  "confidence": "high"
}
```

### 3.3 `deeptutor/tools/graph_tool.py` — `GraphQueryTool`（Coach 工具）

- 定义：`graph_query(query_type, target)`
  - `query_type` ∈ {risk_path, concepts, mastery}（enum）
  - `target`：技能 id 或任务 id（risk_path/concepts 必填）
- 执行流程：
  1. 确定性图查询（`GraphQueryService`）
  2. **若 LLM 可用**：追加自然语言解释（提示词：基于 `risk_path` 结果解释"为什么 X 有风险 + 建议先补哪些")
  3. LLM 失败 → 降级为纯结构化返回（图查询结论仍正确）
- **注册**：`builtin/__init__.py` + `tool_composition.py` always_on（第 12 个教学工具）

### 3.4 MCP 暴露 — learner_server

在 `deeptutor/services/mcp/learner_server.py` 新增：
- `get_knowledge_graph`（limit）— 返回图摘要（节点/边计数 + 学习痕迹）
- `query_risk_path`（target）— 风险链查询（确定性，不含 LLM 解释）

---

## 4. 数据流

1. **诊断完成** → `finalize_diagnosis` → 建课同时触发 `KnowledgeGraphStore.ensure_seeded`（本体种子）
2. **理论/评测完成** → `write_learning_record` → `LearningRecordStore.append` → **`KnowledgeGraphStore.incremental_update(record)`**（新 mastered/struggling 边）
3. **决策** → `log_decision` → `append_decision` → 图增量更新（可选，记录推荐理由）
4. **教学中** → Coach 调 `graph_query` → 确定性返回子图 → LLM 解释 → 教学反馈（如"先补边界框绘制规范，再挑战 task4"）

---

## 5. 错误处理与降级

| 场景 | 处理 |
|------|------|
| 图构建/更新失败 | try/except 降级为仅 JSONL 写入（图是派生索引，不阻塞学习记录） |
| 无图谱文件 / 未诊断 | `risk_path` 返回空 + 提示"先完成诊断" |
| 目标 id 不存在 | 返回错误信息 + 建议就近技能 |
| LLM 解释失败 | 降级为纯结构化 `risk_path` 结果（结论仍正确） |
| 图文件损坏 | 从 JSONL + 本体全量重建（`build` 是纯函数） |

---

## 6. 测试策略

| 测试 | 验证点 |
|------|--------|
| 图构建确定性 | 同输入两次 `build` → 输出完全一致 |
| 风险链正确性 | 构造已知图 → 验证 `missing_prereqs`/`affected_downstream` 路径正确 |
| 增量更新幂等 | 同一记录两次 `incremental_update` → 边不重复 |
| 降级路径 | 无 LLM / 无图谱文件 / 目标不存在 → 不崩溃 |
| 工具注册 | `graph_query` 出现在 always_on + schema 正确 |
| 一致性 | `mastery_snapshot().mastered` 与 `LearningStats.facts()` 对齐 |

---

## 7. 与现有层的关系（不推翻原则）

- **不替换** `LearningRecordStore` — JSONL 仍是唯一 truth；图是派生索引
- **不重复存储本体** — 静态 Skill/Task/TaskGroup/本体边从 competency_tree/task_bank 读取种入
- **`skill_tree()` 暂不动** — 前端已用；`facts()` 的掌握度逻辑被图复用但不重复存储
- **NetworkX 已存在** — 零新增依赖
- **不触 REST API + 前端** — 个人中心已有 skill_tree/radar 面板，图谱面板暂缓（记录在 future-tasks）

---

## 8. 验收标准

1. `python -c "import deeptutor.services.knowledge_graph"` 无错误
2. 从空 `learning/` 目录 + 回归脚本跑一轮 → `knowledge_graph.json` 生成，含 mastered/struggling 边
3. `graph_query(query_type="risk_path", target="task4")` 返回正确的缺失前置/下游风险
4. `risk_path` 结果能触发 LLM 解释；断开 LLM 时降级纯结构化返回
5. MCP `get_knowledge_graph` / `query_risk_path` 可调用
6. 全部单测通过；回归演示重跑不破坏现有流程

---

## 9. 明确不做（YAGNI）

- ~~REST API + 前端图谱面板~~（future-tasks）
- ~~错误模式关联查询~~（等错误数据积累，记录于 future-tasks）
- ~~引入 cognee 库~~（渐进：若未来查询复杂度超限再评估）
- ~~LLM 实体/关系抽取~~（本体是预置的，抽取增量收益有限）
