# 第四轮优化设计：借鉴 TencentDB-Agent-Memory（记忆工具限制 + LLM 去重）

> 日期：2026-08-08。来源：腾讯开源 `Tencent/TencentDB-Agent-Memory`（npm `@tencentdb-agent-memory/memory-tencentdb` 1.0.1，MIT，2026-03 发布）。已完整读源码：L0-L3 四层记忆金字塔 + Mermaid 符号记忆 + capture/recall hooks + L1 抽取/去重 prompt。已 clone 到 `%TEMP%\opencode\refs\tencentdb-memory\package\`。
> **结论**：我们赢在领域层（教学法/诊断/评估/记忆分区），腾讯赢在**记忆工程加固**（结构化提取 + 冲突检测 + 工具护栏）。借鉴两点：**记忆工具调用限制**（format.ts）+ **L1 记录 LLM 去重**（l1-dedup.ts）。

## 关键事实核查
- 腾讯 `l1-dedup.ts`：LLM 批量冲突检测，统一候选池，四动作 `store/skip/update/merge`，支持**跨类型合并**（episodic+persona→persona）+ 多对多（一条新记忆合并多条旧），merge 时 priority 酌情提升、timestamps 取并集保留完整时间线。
- 腾讯 `format.ts`：`MEMORY_TOOLS_GUIDE` 注入「记忆工具调用指南」——每轮 `tdai_memory_search` + `tdai_conversation_search` 合计 ≤3 次，超限后直接回复。
- 我们现状：`reflect()`（learning_records.py:249）是**规则式**去重（按 type+task_id+kp 硬聚类），无法跨类型合并/语义判断；agent_loop 有 E1（同参指纹）/E3（delegate 截断）但**缺记忆类工具总量护栏**。

## 借鉴点

### A. 记忆工具调用限制（每轮 ≤3 次）⭐ S 成本
**腾讯**（`format.ts` MEMORY_TOOLS_GUIDE）：记忆搜索工具每轮合计 ≤3 次，超限引导。
**我们的落地**：
- 常量 `_MEMORY_TOOLS`（agent_loop.py）：`kb_search`/`graph_query`/`competency_map`/`ability_radar`/`get_annotation_task`（只读检索类；**不含**写入类 write_learning_record/log_decision）
- agent_loop `_run_loop`：每轮 `result.tool_calls` 中记忆类工具数量 ≥3 → 丢弃超限调用 + 注入中文 system 引导（**复用 E3 delegate 截断同模式**，纯本地计数零 LLM 成本）
- PERSONA.md 加「记忆工具调用指南」段（每轮 ≤3 次、优先用已有结果、超限后直接作答）

### B. L1 学习记录 LLM 去重（store/skip/update/merge）⭐ M 成本
**腾讯**（`l1-dedup.ts` + `l1-dedup.ts` prompt）：统一候选池 + 批量决策四动作 + 跨类型/多对多合并 + 可逆。
**我们的落地**：
- 新增 `deeptutor/services/learning_records_dedup.py`（纯函数 + LLM 调用，懒加载防循环）：
  - `build_candidates(records, top_k)` → 统一候选池（按知识图谱关联 + 最近 N 条抽样）
  - `call_dedup_llm(candidates, new_records)` → 批量决策（腾讯 prompt 适配：类型映射 diagnosis/theory_mastered/annotation_exercise，priority→confidence）
  - `apply_decision(records, decision)` → store/update/merge/skip 动作应用
- `LearningRecordStore.reflect()` 增加 LLM 路径：active 记录数 ≥15 或显式触发时先走 LLM 去重，失败/超时/非法 JSON → 回退现有规则式 reflect（**不阻塞、真理保留、可逆**）
- `write_learning_record` **不自动触发**（避免每轮 LLM 开销），由 reflect 统一驱动
- 合并可逆：旧记录归档（`archived=True`）不删除，延续现有 truth-preserving 原则

## 不借鉴
- Mermaid 符号卸载（工程量大，E5 长会话折叠已覆盖）
- Persona 四层深度扫描（画像服务教学而非聊天，收益有限）
- L1 提取 prompt 全量迁移（write_learning_record schema 已结构化；仅吸收 priority 门槛思想）

## 优先级
| 优先级 | 项 | Effort | 说明 |
|--------|----|--------|------|
| **P0** | A 记忆工具限制 | S | 纯本地护栏，复用 E3 模式 |
| **P0** | B LLM 去重 | M | 升级 reflect，四动作 + 跨类型合并 |

## 实施顺序建议
本会话先 A（S 成本立竿见影，补工具级护栏），再 B（M 成本，升级记忆去重）。

## 复用与冲突
- A 复用 E3 截断模式（agent_loop `kept_tool_calls` 重建逻辑），与 E1 正交（E1 防同参重复，A 防换参轮询）
- B 复用 E4 confidence 字段、reflect() 现有归档机制，不破坏规则式路径
