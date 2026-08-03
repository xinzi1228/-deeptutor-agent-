# 教学轨迹（Teaching Trace）设计 — 合并进「记录」Tab

> 状态: 设计已获用户批准
> 日期: 2026-08-03

---

## 1. 背景与目标

Progress 页「记录」Tab 目前有 决策日志 + 课程计划 + 学习时间线。时间线已显示 F1/readiness/预测命中，但**缺教师视角的完整因果链**：评测(F1/readiness) → 卡住信号 → 介入决策 → 落盘，分散在 records/decisions 两处。

**目标**：把「学习时间线」升级为**可展开的教学回合链**，每条练习回合展示 评测结果 + 关联介入决策，让教师/评委一眼看到"这个学生这次练习为什么卡住、教练怎么介入的"。

**来源**：差距分析 §十二②（调用链运营视图）+ ④（流程状态可视化）合并方案，用户确认合并进「记录」Tab（不新增 Tab）。

## 2. 设计决策汇总

| # | 维度 | 决策 |
|---|------|------|
| 1 | 位置 | 合并进「记录」Tab（不新增 Tab，保持 4 Tab 简洁） |
| 2 | 形态 | 升级现有 `Timeline.tsx`，练习回合可展开显示因果 |
| 3 | 数据 | 复用 `episodes`（records 按日聚合）+ `decisions`（kind/target/rationale） |
| 4 | 关联 | 练习回合与介入决策按**时间邻近**匹配（同日内 + 分钟差 ≤ 阈值） |
| 5 | 后端 | 新增 `GET /api/v1/profile/trace-log?limit=30` 聚合（records + decisions 运行时聚合，不新建 store） |
| 6 | flow_state | 不强制——demo 无 flow_state 时轨迹退化显示 records 即可 |

## 3. 后端：`GET /api/v1/profile/trace-log`

**位置**：`deeptutor/api/routers/profile.py` 新增端点

**返回结构**：
```json
{
  "traces": [
    {
      "timestamp": "2026-08-01T14:18:23",
      "date": "2026-08-01",
      "type": "annotation_exercise",
      "task_id": "task1",
      "knowledge_point": "边界框绘制",
      "f1": 0.5, "precision": 1.0, "recall": 0.33,
      "readiness": "review_first",
      "knowledge_points": ["边界框绘制", "目标检测标注"],
      "foresight_verified": true, "foresight_hit": true,
      "intervention": {
        "kind": "struggle_intervention",
        "target": "task7",
        "rationale": "降难度介入",
        "timestamp": "2026-08-02T..."
      },
      "decision": {
        "kind": "task_recommendation",
        "target": "task1",
        "rationale": "readiness=review_first → 先解决漏标"
      }
    },
    ... 按时间倒序
  ]
}
```

**实现逻辑**：
1. 从 `LearningRecordStore` 读全部 records（已有 `_all_records`/`episodes` 内部逻辑）
2. 读 decisions.jsonl（已有 `/decisions` 端点内部逻辑）
3. 对每条 **annotation_exercise** record：
   - 关联决策：找 kind ∈ {task_recommendation, 推进判定, struggle_intervention} 且时间与 record 邻近（同日 ± 10 分钟）的 decision
   - 若有多条，分别放 `decision`（推荐类）和 `intervention`（介入类）
4. 按 timestamp 倒序，limit 截断
5. 非练习类（diagnosis/theory_mastered）也返回（用于完整轨迹），但无 F1/介入

## 4. 前端：升级 Timeline.tsx

**改造**：`web/components/learning-stats/Timeline.tsx`
- 数据源：仍用 `episodes`（records 按日）做外层日期分组，但**练习回合行变为可展开**
- 展开后显示：
  - `knowledge_points` 列表
  - `intervention`（卡住介入）：红/橙徽章 + rationale
  - `decision`（推荐/推进）：蓝徽章 + rationale
- 数据获取：`progress/page.tsx` 的 Promise.all 增加 `getTraceLog()`，把 trace 数据传入 Timeline（或 Timeline 内部按日期 merge）
- 交互：点击练习行展开/收起（useState 记录展开的 key）

**保留**：诊断/理论学习回合并行（无 F1 仍显示类型 + knowledge_point）

## 5. 测试

| 层 | 测试 |
|----|------|
| 后端 | `tests/api/test_profile_trace_log.py`：聚合正确性（records+decisions 匹配、时间倒序、limit） |
| 前端 | tsc + build |
| 冒烟 | Playwright：Progress → 记录 Tab → 练习行可展开显示 F1/readiness/介入 |

## 6. 明确不做

- 不新增 Tab（合并进记录 Tab）
- 不新建 store（运行时聚合）
- 不做 flow_state 强依赖（无 flow_state 时正常显示 records 轨迹）
- 不引入前端图表库（纯列表 + 展开）

## 7. 风险

- decisions 与 records 时间匹配可能不精确（不同秒）——用"同日 + 就近分钟"启发式，匹配不到就显示无介入（不误报）
- demo 数据仅 2 条 records + 3 条 decisions——轨迹面板初始数据少，但结构正确
