# 议题①② 设计：记忆污染治理 + 记忆分区

> 用户诉求：① 解决记忆污染；② 记忆分区——用户可创建多个记忆区，无关对话排除在区外，一个用户可建多个记忆区，并询问是否有更好的办法。

## 1. 现状

- 记忆体系：L1（`trace/<surface>/<YYYY-MM-DD>.jsonl` 事件日志，append-only）→ L2（`L2/<surface>.md` 面摘要）→ L3（`L3/<recent|profile|scope|preferences>.md` 跨面综合）
- `write_memory` 工具：仅写用户偏好（preferences slot），有 L1 trace + 去重，但**无分区维度、无提取过滤、无记忆区概念**
- surface = chat / notebook / kb（技术 surface，非用户意图维度）

## 2. 调研借鉴

| 来源 | 核心机制 | 融入点 |
|------|---------|--------|
| **Mem0**（业界标准） | **ADD-only 不覆盖**（记忆只增不覆盖）；`metadata.topic` 分区；`includes/excludes`（提取时排除无关）；`expiration_date` 遗忘；`immutable` | 污染 4 层解法 + 分区模型，印证用户方案 |
| feynman-tutor | 三层笔记 + **证据链**（每条记忆附原话/场景，禁止一次观察升级成画像） | 防污染根源：过早归纳 |
| EverOS | reflection 演进 + 遗忘 | 记忆会过时需演进 |

## 3. 记忆污染 4 层解法

1. **ADD-only 不覆盖**（Mem0）——记忆只增不改，冲突保留历史 + 时间戳，污染不抹掉正确记忆
2. **证据链**（feynman-tutor）——每条记忆附原话/场景，**禁止一次观察升级成画像**（针对当前 L3 过早合并）；核心规则：*永远不要从一次观察直接升级成画像*
3. **提取时排除**（Mem0 `excludes`）——写入时按记忆区约束提取，无关内容不入区（联动议题⑤ `route_input` off_topic 判定）
4. **遗忘演进**（EverOS/Mem0 `expiration`）——过期记忆隐藏，需 reflection 演进

## 4. 记忆分区设计

```
记忆区(bucket) = { name, topic, includes, excludes }
  - 用户可创建多个区（"标注学习" / "Python 学习"）
  - 会话绑定记忆区（开局选择 / Coach 按 route_input 意图自动归类）
  - 无关对话排除：route_input 判 off_topic → 不写入当前区
  - 检索隔离：查询时按当前区过滤（不只写入隔离）
```

**存储落地**：
- L2 路径加 bucket 维度：`L2/<bucket>/<surface>.md`
- L1 事件带 `bucket` 元数据
- **L3 的 profile / preferences 做全局共享层**（跨区共享：用户性格/偏好全局知道，不因分区丢失）；L3 的 recent/scope 按 bucket 隔离

**半自动归类**（"更好的办法"）：不靠用户手动分类——Coach 按 `route_input` 意图自动归类到正确区；用户可手动建区/改名/合并

## 5. 与议题⑤的联动

- `route_input` 的 category 增加记忆写入策略：`off_topic` → 不写；`task_start/answer_submit` → 写当前区；`question` → 可选写
- 记忆区在会话上下文（`UnifiedContext`）中携带，Coach 写记忆时按当前区约束提取

## 6. 实现与测试

- 存储层：`services/memory/` 加 bucket 维度（paths/settings/store）
- `write_memory` 工具：参数加 `bucket`（可选，默认当前会话区）
- 新 API：记忆区 CRUD（`/api/v1/memory/buckets`）+ 前端 Memory 页记忆区管理
- 测试：`tests/services/memory/test_buckets.py`（分区隔离、跨区不混、L3 全局层共享、off_topic 不写入、ADD-only 不覆盖）
- 冒烟：新建"标注学习"区 → 对话记录入区 → 切"Python 学习"区 → 检索不到标注区内容

## 7. 衔接

- 议题⑤ `route_input`：记忆写入的意图前置判定
- 议题⑦ 总控：记忆读写按区路由
