# 打卡徽章引擎设计（Check-in & Achievements）

> 状态: 设计已获用户批准
> 日期: 2026-08-02

---

## 1. 背景与目标

标注星图产品的学习激励缺失——学生无"持续学习"的反馈机制。竞赛文档提及可视化要求（进度条/成绩单/薄弱项图表），学习动机激励（打卡/成就）是产品差异化亮点。

**本次目标**：从已有 learning records **派生**打卡与徽章（确定性、无新数据文件）——
1. **自动打卡**：每天有学习记录即自动记当天打卡，计算打卡总天数 + 连续 streak。
2. **基础徽章集 6 个**：新手上路 / 小有坚持 / 持之以恒 / 初战告捷 / 熟能生巧 / 阶段通关。
3. **Progress 页展示**：GitHub 贡献热力图风格打卡日历 + streak + 徽章墙。

**借鉴来源**：
- `Streaky`（GitHub-inspired habit tracker）：**streak 计算算法**（日期集合排序 → 从今天往前连续天数）+ streak meters 可视化
- **GitHub contribution calendar**：打卡日历**热力图** UI（每天一格，颜色深浅）
- **Duolingo**（学习游戏化标杆，领域知识）：streak + 徽章解锁机制
- `exampass`（本地 skill）：`kc_mastery` 掌握度可视化
- `OATutor`：技能状态追踪（已有 LearningStats/knowledge_graph，不重复造）

**明确不做**（用户确认）：
- 语音功能（基础已有：录音→STT、TTS 自动播放，不动）
- Coach 对话播报打卡（纯自动打卡，不带播报）
- 新数据文件（纯派生，无 achievements.json）

## 2. 设计决策汇总（已确认）

| # | 维度 | 决策 |
|---|------|------|
| 1 | 打卡机制 | 自动打卡：每次学习记录自动记当天打卡 + streak |
| 2 | 徽章集 | 基础 6 个（新手上路/小有坚持/持之以恒/初战告捷/熟能生巧/阶段通关） |
| 3 | 语音 | 不新增语音功能（基础已有不动） |
| 4 | 数据存储 | 从 learning records 派生（确定性、无新数据文件） |
| 5 | 展示 | Progress 页：GitHub 贡献热力图风格打卡日历 + streak + 徽章墙 |

## 3. 架构

```
learning records (diagnosis/theory_mastered/annotation_exercise, 含 timestamp/f1/task_id/knowledge_point)
        │
        ▼
AchievementService (纯函数派生)
  ├── 打卡日历: 每天有记录的日期集合 → total_days + streak (从今天往前连续)
  └── 徽章判定: 6 个条件从记录统计触发 (unlocked + unlocked_at)
        │
        ▼
API: GET /api/v1/achievements
        │
        ▼
Progress 页: CheckinCalendar (热力图) + BadgeWall (徽章墙)
```

## 4. `deeptutor/services/achievements.py` — 派生引擎

### 4.1 打卡

- **数据源**：所有 `type in (diagnosis, theory_mastered, annotation_exercise)` 记录的 `timestamp`
- **打卡日期集合**：提取每个 timestamp 的本地日期（`YYYY-MM-DD`），去重
- **total_days**：打卡日期集合大小
- **streak**：从"今天"（或最近日期）往前连续的天数：
  - 排序日期集合；从今天开始，若今天未打卡则从昨天开始
  - 连续向前，遇到断档停止
- **注入 `now`**：可测试（传 `now=datetime`）

### 4.2 徽章（6 个，条件从记录统计）

| 徽章 id | 名称 | 条件 |
|---------|------|------|
| `first_step` | 新手上路 | 有任意学习记录 |
| `streak_3` | 小有坚持 | streak ≥ 3 天 |
| `streak_7` | 持之以恒 | streak ≥ 7 天 |
| `first_pass` | 初战告捷 | 存在练习记录（annotation_exercise）且 F1 ≥ 0.7 |
| `practice_10` | 熟能生巧 | 累计 annotation_exercise 记录 ≥ 10 |
| `module_clear` | 阶段通关 | 完成任一模块（见 4.3） |

> **first_pass 范围说明**：初战告捷适用于任意练习任务类型（bbox / 分类 / 多边形等），只要该练习为 `annotation_exercise` 且 F1 ≥ 0.7 即触发；不限于 bbox 练习。

### 4.3 阶段通关（module_clear）定义

从 learning records 派生"完成模块"：
- 方式 A（优先）：读取 `course_plan.json`（已有 4 模块课程计划）——若存在，检查任一模块的练习任务集合，该模块所有任务均有 `annotation_exercise` 记录且任一 F1 ≥ 0.7 → 完成
- 方式 B（fallback，course_plan 不可用或解析失败）：累计 ≥ 5 个不同 `task_id` 有练习记录 → 完成
- 实现时选 A，B 为降级路径；判定结果确定性、可测试

### 4.4 返回结构

```json
{
  "checkin": {
    "dates": ["2026-07-31", "2026-08-01"],
    "total_days": 2,
    "streak": 2,
    "today_checked": false
  },
  "badges": [
    {"id": "first_step", "name": "新手上路", "description": "完成首次学习", "unlocked": true, "unlocked_at": "2026-07-31T10:00:00+00:00"},
    {"id": "streak_3", "name": "小有坚持", "description": "连续打卡 3 天", "unlocked": false, "unlocked_at": null}
  ]
}
```

### 4.5 确定性原则
- 纯函数 + 可注入 records/now；无 LLM、无 I/O 副作用（除读取 records）
- 打卡/徽章全部从记录派生，可重跑、可测试、可审计

## 5. API + 前端

### 5.1 API

`deeptutor/api/routers/achievements.py`：`GET /api/v1/achievements` → `{checkin, badges}`（读 LearningRecordStore 派生）

### 5.2 前端（Progress 页）

- `web/components/learning-stats/CheckinCalendar.tsx`：GitHub 贡献热力图风格——最近 ~12 周打卡日历，每天一格（打卡/未打卡/今天），streak 显示
- `web/components/learning-stats/BadgeWall.tsx`：徽章墙——6 个徽章卡片，已解锁亮色 + 解锁时间，未解锁灰色（占位）
- Progress 页接入两个组件

## 6. 测试

| 组件 | 测试 |
|------|------|
| achievements 打卡 | 日期集合/total_days/streak 连续边界（今天打卡/昨天断档/跨月）/注入 now |
| achievements 徽章 | 6 徽章各自触发 + 不触发 + unlocked_at |
| 阶段通关 | course_plan 存在/缺失两条路径 |
| 确定性 | 相同记录 → 相同结果 |
| 空记录 | 无记录 → dates 空/streak 0/无徽章 |
| API | GET /api/v1/achievements 返回结构 |
| 前端 | tsc + build（无新依赖） |

## 7. 实施任务划分（供 writing-plans 细化）

1. `AchievementService` 服务（打卡日期/streak/6 徽章判定/阶段通关）
2. `achievements` API 端点
3. Progress 页 `CheckinCalendar` + `BadgeWall` 组件
4. 全量回归 + 冒烟
