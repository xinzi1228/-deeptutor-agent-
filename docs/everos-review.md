# EverOS 借鉴分析 — 记忆系统升级参考

> 项目: EverMind-AI/EverOS (11.7k⭐, Python, 2025-10 创建)
> 定位: 为每个 AI agent 提供的**便携记忆层** — 本地优先、Markdown 原生
> 关联: https://evermind.ai/everos | docs/storage_layout.md | docs/reflection.md

---

## 一、EverOS 核心设计

### 存储三件套 (Markdown 是唯一真相)

| 层 | 载体 | 内容 | 可重建 |
|----|------|------|--------|
| **Markdown + YAML frontmatter** | `.md` 文件 | 记忆内容本身，可读/可编辑/diff/Git 版本化 | 它是真相 |
| **SQLite** | `.index/sqlite/*.db` | 系统状态、审计、cascade 队列、OME 状态 | ✅ 从 markdown 重建 |
| **LanceDB** | `.index/lancedb/*.lance` | 向量 + BM25 + 标量检索 | ✅ 从 markdown 重建 |

**核心规则: 删掉整个 `.index/` 目录，记忆不丢失** — 从 `.md` 树重建。

### 目录布局 (scope 编码在路径)

```
~/.everos/
├── default_app/default_project/
│   ├── users/<user_id>/
│   │   ├── user.md          单文件 profile (重写)
│   │   ├── episodes/        episode-<日期>.md (每日日志追加)
│   │   ├── .atomic_facts/   atomic_fact-<日期>.md (分解事实)
│   │   └── .foresights/     foresight-<日期>.md (前瞻预测)
│   ├── agents/<agent_id>/
│   │   ├── .cases/          agent_case-<日期>.md (案例日志)
│   │   └── skills/          可复用技能
│   └── knowledge/          可编辑、带来源的知识页 (Wiki)
└── .index/                 派生索引 (可重建, gitignore)
```

### Reflection (离线记忆进化) — 最值得借鉴

> 定期把散落在多次对话的记忆片段合并成一条按时间组织的叙事。
> 运行在后台：合并相似 cluster 内的 Episodes → 解决过期信息(保留最新) → 软归档被替换的原文。

- 默认关闭，`ome.toml` 一行开启，**每周一 02:00 自动跑**
- 每个 run 是**有损 LLM 合并**，不建议跑太频繁 (最多每周一次)
- 产出: 追加一条合并叙事到 Episode log，旧片段标记为 archived (退出默认搜索)

---

## 二、与我们的系统对比

| 概念 | EverOS | 我们现有 | 差距 |
|------|--------|---------|------|
| 存储真相 | Markdown source of truth | `learning_records.jsonl` + L3 md | 我们 JSONL 无派生索引、无重建能力 |
| 记录组织 | episodes 按日 + profile 单文件 | learning_records 追加 | 我们无按日组织 |
| 分解事实 | atomic_facts | synapse record 字段 | 无独立事实层 |
| 前瞻 | foresights | 无 | **缺: 学生下一步预测** |
| 记忆进化 | **Reflection 每周合并/去重/归档** | 无 | **最大短板: 记录无限累积** |
| 知识 | knowledge Wiki (可编辑带来源) | annotation_kb | 我们 KB 只读 |
| 检索 | SQLite + LanceDB 派生索引 | 无索引, 全量读 | 教学场景可能过度 |
| 用户隔离 | app_id/project_id 路径分区 | 单用户/多用户路径 | 已有多用户支持 |

---

## 三、可落地借鉴 (按价值排序)

### P0 — 记忆进化 Reflection (最有价值)

**问题:** 我们的 learning_records.jsonl 无限追加，同一 task 多次练习会累积多条记录，无去重/合并/归档 → 记忆变噪。

**借鉴 EverOS Reflection 思路改造:**
```
reflect_learning_records (每周或手动触发):
  1. 按 task_id + knowledge_point 聚类练习记录
  2. 同 cluster 内合并: 保留最新 F1 + 汇总 error_pattern 证据
     (对应 feynman 三层: pattern unconfirmed → confirmed 升级时机)
  3. 过期/被合并的记录标记 archived (退出默认统计)
  4. 追加一条"合并叙事"摘要到 recent.md
```
**落地:** `LearningRecordStore.reflect()` + 决策审计；可在个人中心加"记忆整理"按钮。

### P0 — foresights (前瞻预测)

**问题:** 我们记录"发生了什么"，但不记录"预测学生下一步会怎样"。

**借鉴:** learning_record 加 `foresight` 字段:
```json
{"type":"annotation_exercise", ..., 
 "foresight": {"predicted_next": "task4 遮挡处理可能漏标", "confidence": 0.7}}
```
下次对话 `read_memory` 时验证预测 → 命中则记 `foresight_hit=true`（校正闭环，synapse correction 维度）。

### P1 — episodes 按日组织

**问题:** learning_records 是扁平 JSONL，无时间维度的分组视图。

**借鉴:** 记录加 `episode_date`（YYYY-MM-DD），个人中心可按日/周时间线展示。轻量改造。

### P1 — atomic facts 独立层

**问题:** 学生"掌握/未掌握"的事实散在每条记录里。

**借鉴:** 新增 `facts.jsonl` 存原子事实（如 "IOU计算 已掌握 2026-07-31"），供技能树/仪表盘直接引用，无需全量扫描 records。对应 EverOS atomic_facts。

### P2 — Markdown source of truth + 可重建索引

**问题:** 我们 JSONL 是唯一真相，无派生检索索引。

**借鉴:** 教学场景可简化为: JSONL (真相) + SQLite 派生索引 (按 task_id/user 快速查询)。删索引可重建。**可能过度工程**，视需要。

---

## 四、结论

EverOS 是"通用 AI 记忆层"，我们是"教学教练记忆"。最值得借鉴的是它的**记忆进化理念**（Reflection 合并/去重/归档）和**前瞻预测**（foresights），这两点正好补齐我们记忆系统"无限累积变噪"和"只记录不预测"的短板。

不建议照搬全套存储栈（SQLite + LanceDB + cascade watcher）——我们的 JSONL + L3 md 对教学场景已够轻，引入派生索引需权衡复杂度。

---

## 五、下一步选项

1. **P0-1 记忆进化 Reflection** — 写 `reflect()` 合并/去重/归档 + 个人中心按钮
2. **P0-2 foresights 前瞻** — 记录加预测字段 + 下次验证闭环
3. **P1 episodes 时间线** — 记录按日分组 + 前端时间线视图
4. 保持现状，仅记录分析
