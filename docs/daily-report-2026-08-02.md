# 标注星图 — 2026-08-02 开发日报

> 面向团队汇报。本日完成竞赛 6 模块中的 3 项深度优化 + 多专家角色体系 + 平台整体打磨，共 **~70 个提交**。

---

## 一、今日成果一览

| # | 工作块 | 时间 | 对应竞赛模块 | 核心成果 |
|---|--------|------|-------------|---------|
| 1 | **对话内可视化** | 09:51–11:01 | ⑤学习报告 | 4 类图表（成绩单/雷达/进度/知识图谱）+ matplotlib PNG 成绩单 |
| 2 | **困难检测介入** | 11:39–12:11 | ④困难检测 | StruggleDetector 3 信号 + 介入建议 + 第 14 个教学工具 |
| 3 | **工作台改造 → 标注星图** | 12:55–16:00 | 平台定位 | 品牌重塑 + capability/persona 收敛 + 删 9 路由（~13.7k 行） |
| 4 | **任务引导引擎化** | 16:46–18:14 | ③任务引导 | TeachingFlowEngine 6 步状态机 + 像素校验 + 新题型 + 第 15 个工具 |
| 5 | **打卡徽章引擎** | 19:37–20:07 | ⑤学习报告 | 6 徽章 + 打卡热力图 + 成就墙（GET /api/v1/achievements） |
| 6 | **多专家角色体系** | 20:54–21:51 | 全模块 | 6 专家卡 + 索引校验 + 阶段→专家路由 + 自动 readiness 验收 |

**收尾打磨**：error_case 评分语义修复 + auto_readiness docstring + 前端死代码清理（~19k 行）。

---

## 二、各工作块详情

### 1. 对话内可视化（竞赛模块⑤学习报告）

> 设计 `visualization-design.md` 09:51 → 计划 `visualization-implementation-plan.md` 09:55

- **chart 契约统一**：`metadata.chart = {type, data}`，scorecard/radar/progress/graph 四类型
- **后端**：`ability_radar` 能力雷达工具、`graph_query` 风险链返回图数据、`finalize_diagnosis` 返回学习进度 chart、matplotlib 成绩单 PNG（CJK 字体 + 失败降级）
- **前端**：`ChatChartCard` 组件 + `AssistantMessage` 对话内渲染图表卡片
- 成果：教练回复内直接呈现成绩单/雷达图/进度/知识图谱，无需跳转个人中心

### 2. 困难检测介入（竞赛模块④困难检测）

> 设计 `struggle-detector-design.md` 11:39 → 计划 `struggle-detector-implementation-plan.md` 11:41

- **StruggleDetector**：确定性 3 信号检测（连续低分 / 错误重复 / 停留超时），tz 归一化防护
- **介入建议映射**：信号→readiness_gate 对接（降难度/换模式/主动询问/回理论）
- **StruggleDetectTool**：第 14 个 always-on 教学工具，severe 时 LLM 解释层降级
- **审计闭环**：`log_decision(kind=struggle_intervention)` + 接入教学流程协议 + PERSONA 规则 12

### 3. 工作台改造 → 标注星图（平台整体定位）

> 设计 `workbench-restructure-design.md` 12:55 → 计划 `workbench-restructure-implementation-plan.md` 12:58

- **品牌重塑**：DeepTutor → 「标注星图」(Annotation Star Map)，i18n 值批量替换
- **capability 收敛**：只留 `chat`（移除 6 个通用能力注册）
- **persona 收敛**：只留 `annotation-coach` 固定默认（生产 turn 解析路径生效）
- **前端瘦身**：删除 9 个路由目录（book/co-writer/partners/playground/agents/knowledge/notebook/space/profile，~13.7k 行），侧边栏只留 4 项，保留页 UI 入口裁剪 + 能力选择器只留 chat

### 4. 任务引导引擎化（竞赛模块③任务引导）

> 设计 `teaching-flow-engine-design.md` 16:46 → 计划 `teaching-flow-engine-implementation-plan.md` 16:49

- **TeachingFlowEngine**：任务级 6 步状态机（select_task→show_task→waiting→evaluate→feedback→record）+ gate 前置校验 + 阻塞报告 + flow_state.json 持久化
- **teaching_flow 工具**：query/advance/reset/start_task/block + 下一步提示，第 15 个 always-on
- **像素校验**：贴边/重叠/紧致度 3 项无 GT 启发式（含嵌套豁免修复 + 重复框不豁免）
- **题型扩展**：judgment/standard/error_case 评测 + grading.py 扩展（fail-closed）
- **任务库**：新增 task10-12（判断/规范/找错），annotation_check task_id 自动推进 evaluate→feedback

### 5. 打卡徽章引擎（竞赛模块⑤学习报告辅助）

> 设计 `checkin-achievements-design.md` 19:54 → 计划 `checkin-achievements-implementation-plan.md` 19:40

- **AchievementService**：从 learning records 确定性派生打卡日期/streak + 6 徽章
  （first_step / streak_3 / streak_7 / first_pass / practice_10 / module_clear）
- **API**：`GET /api/v1/achievements`（打卡 + 徽章）
- **前端**：Progress 页 CheckinCalendar 热力图（GitHub 风格 12 周）+ BadgeWall 成就墙
- 修复：热力图日期偏移（过去 12 周而非未来）、module_clear 双路径 fallback、timestamp 缺失防护

### 6. 多专家角色体系（全模块组织升级）

> 设计 `expert-roles-design.md` 20:54 → 计划 `expert-roles-implementation-plan.md` 20:56，Subagent-Driven 实施

- **A. 6 专家角色卡**：learning_planner / session_steward / task_guide / struggle_detective / report_analyst / grading_expert，对应竞赛 6 模块，agency-agents 结构（frontmatter + 身份/使命/规则/能力/流程），PERSONA 专家协作路由节
- **B. 轻量编排**：`EXPERT_ROUTE` 阶段→专家映射（teaching_flow query 返回附带 `expert`）+ `auto_readiness(f1)` 自动 readiness 验收（F1≥0.85→advance / 0.7→advance_with_caution / 0.65→more_practice / 其余→review_first），写入 flow_state + metadata
- **C. 索引 + CI 校验**：`experts_manifest.json`（divisions.json 风格）+ pytest 双向一致校验（目录↔索引 + frontmatter + coordinator id 对齐）

---

## 三、收尾打磨

| 项 | 内容 |
|----|------|
| error_case 评分语义 | 未列出案例视为隐式无误 → 只列错误 id 且全对可得满分；漏标真实错误仍判错 |
| auto_readiness docstring | 补注 4/6 判定说明（step_down/diagnose_again 留给 Coach/struggle 决策） |
| 前端死代码清理 | 删 64 文件 / ~19k 行（space/agents/knowledge/partners orphan 组件 + CapabilityConfigCard + 3 个 ConfigPanel + 死 props + 死回调） |

---

## 四、质量验证

- **后端全量回归**：2979 passed / 33 预存在失败（Windows 路径、GBK locale、缺失可选依赖 telegram/slack、sandbox 环境），多专家实施 **无新增失败**
- **多专家 feature 测试**：67 passed
- **前端**：`tsc --noEmit` 0 错误；`next build` 成功（需清 HTTP_PROXY/HTTPS_PROXY）
- **冒烟**：SMOKE OK（expert 路由 / readiness 阈值 / manifest 一致性全对）

---

## 五、今日里程碑时间线

```
09:51 对话内可视化设计       → 11:01 可视化落地完成
11:39 困难检测设计            → 12:11 困难检测接入完成（第14工具）
12:55 工作台改造设计          → 16:00 标注星图改造完成（删9路由）
16:46 任务引导引擎设计        → 18:14 引擎化完成（第15工具）
19:37 打卡徽章设计            → 20:07 徽章引擎+前端完成
20:54 多专家角色体系设计      → 21:51 全部实施+验证+死代码清理完成
```

**成果**：竞赛 6 模块 + 3 项平台优化 + 多专家组织体系全部完成，产品「标注星图」可完整演示教学闭环（诊断→计划→理论→练习→批改→报告）。
