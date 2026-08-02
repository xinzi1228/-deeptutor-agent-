# 会话交接文档（Compression Handoff）

> 用途: 压缩上下文前的状态快照。恢复后据此无缝继续。
> 创建: 2026-08-02

---

## 一、项目定位与竞赛背景

- **项目**: DeepTutor 开源项目 fork，改造为「数据标注教学平台」（数据标注教学智能体）
- **竞赛**: 科大讯飞 XA-202603（星辰 Agent 平台）——**平台开放自由选择，DeepTutor 可作为交付**
- **竞赛核心**: 6 模块（①学习计划 ②会话管理 ③任务引导 ④困难检测 ⑤学习报告 ⑥练习批改）+ 6 份交付材料
- **竞赛文件**: `标注星图_团队分工与周报模板_v5.5.docx`（团队 6 人，目标 2026-09-01）
- **开发平台说明**: 竞赛文件写的是"星辰 Agent 平台"，但用户确认平台开放自由选择，DeepTutor 可作为交付平台

## 二、当前完成度（6 模块覆盖）

| 模块 | 覆盖 | 状态 |
|------|------|------|
| ①学习计划引擎 | ✅ 高 (~80%) | course_plan 4模块+DAG+docx 完整 |
| ②会话管理器 | ✅ 高 (~85%) | 三层记忆+断点续学完整 |
| ③任务引导引擎 | ⚠️ 中 (~50%) | 协议有、引擎缺（后续子项目） |
| ④困难检测介入 | 🔴 待实施 | spec+计划已写完，未实施 |
| ⑤学习报告插件 | ✅ 高 (~90%) | 对话可视化+Progress面板完整 |
| ⑥练习+批改引擎 | ⚠️ 中 (~50%) | 只有 bbox/分类两题型 |

## 三、近期已完成功能（全部已提交）

### 1. 对话内可视化（11 提交，spec=`docs/specs/visualization-design.md`）
- **后端**: `deeptutor/tools/chart_cards.py`（radar_chart/progress_chart/build_scorecard_chart/graph_chart + matplotlib 成绩单 PNG）
- **4 类图表**（确定性数据，LLM 不画图）:
  - 练习成绩单 → `annotation_check`（matplotlib PNG，media 目录）
  - 能力雷达 → `ability_radar` 工具（新，LearningStats.radar）
  - 学习进度 → `finalize_diagnosis`（progress chart）
  - 图谱风险链 → `graph_query`（cytoscape 契约）
- **前端**: `web/components/chat/home/ChatChartCard.tsx` + `ChatMessages.tsx` AssistantMessage 接线
- **关键修复**: chart 数据从 `tool_result` 事件的 `metadata.tool_metadata.chart` 读取（不是 result 事件顶层）
- 成绩单图标题用 ASCII `[达标]/[待加强]`（避免 CJK glyph 豆腐块）

### 2. 知识图谱（更早，`docs/specs/knowledge-graph-*.md`）
- `knowledge_graph.py`（build/incremental_update/get/save，JSONL 派生索引）
- `graph_query.py`（risk_path/concepts/mastery 确定性查询）
- `graph_tool.py`（graph_query 第 12 个 always-on）+ MCP 暴露 + Progress 面板
- `kp→技能别名映射`（KP_TO_SKILL_ALIASES）修复真实数据 risk_path 覆盖

### 3. 其他 fork 功能（41 提交，见 `docs/fork-features*.md`）
- annotation-coach persona + 12 教学工具（competency_map/job_analysis/get_annotation_task/annotation_check/write_learning_record/generate_iou_demo/log_decision/evaluate_teaching_plan/verify_foresight/improve_teaching_flow/finalize_diagnosis/graph_query）+ ability_radar
- 诊断式教学/决策审计/对抗性评估/记忆进化Reflection/foresight预测/教学自改进/CRAG/docx手册/Coach绩效

## 四、当前待办

### A. 困难检测介入（下一步，立即执行）
- **spec**: `docs/specs/struggle-detector-design.md`（`3f6a6d5a`）
- **计划**: `docs/specs/struggle-detector-implementation-plan.md`（`c98300da`，6 任务 TDD）
- **执行方式**: 用户选 Subagent-Driven（每任务 subagent + 双层审查）
- **任务清单**:
  1. `StruggleDetector` 3 信号检测器（`deeptutor/services/struggle_detector.py`）
  2. `intervention_suggestion` 信号→介入建议映射
  3. `StruggleDetectTool`（`deeptutor/tools/struggle_tool.py`）+ LLM 解释层
  4. 注册 `struggle_detect` 第 14 个 always-on
  5. 接入 flow-practice/onboarding + PERSONA 规则 12
  6. 审计闭环 + 回归验证

### B. 专门化改造（剩余两个子项目，brainstorm 讨论过但未写 spec）
**注意: 压缩后这些 brainstorming 细节会丢失，恢复时需重新澄清用户偏好**
1. **工作台裁剪**: 导航白名单（只留 Annotation/Progress/Home）+ capability/tool/persona 白名单 + 固定 annotation-coach + 默认路由
   - 技术基础: `SidebarShell.tsx` 硬编码数组可改配置、`capability-routes.ts` 门控、`CapabilityAccessContext`
2. **任务引导引擎化**: 分步状态机 + 像素级校验（贴边/遮挡/最小外接矩形）+ 题型扩展（判断/规范/错误案例）
   - 复用 `learning/grading.py`（choice/short/open）、`quiz_judge.py`
3. （可选后期）语音引导/打卡徽章（基础设施已有 `services/voice/`）

## 五、演示环境与数据状态

- **当前演示数据偏少**: 2 条记录（1 diagnosis + 1 task1 F1=0.5 review_first）、2 决策、0 评估、图谱 43 节点/52 边
- **演示需补充数据**: 建议跑完整多任务学习（task1→task4，含错误模式+foresight+介入）让 F1 曲线/雷达/决策/图谱有料
- **服务启动**（演示用，注意 launcher 前端健康检查 bug）:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  python -m deeptutor_cli.main serve --port 8001          # 后端
  # 另开终端:
  cd web; npx next dev --port 3782                        # 前端（分离启动，避免 launcher 120s 超时自杀）
  ```
- **Label Studio**: Docker 容器 `ls` 端口 8080，token `ad69bdb5f500f6ab8a40c53da31bf60a23a468ab92`
  - Docker Desktop: `C:\Program Files\Docker\Docker\Docker Desktop.exe`
  - 启动: `& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" start ls`
- **数据位置**: `data/user/workspace/learning/`（records/decisions/brief/course_plan/knowledge_graph）

## 六、关键技术事实（复用，避免重新探索）

- **测试**: pytest + pytest-asyncio（function-scoped event loop）；PowerShell 需 `$env:PYTHONIOENCODING="utf-8"` 防中文乱码
- **工具注册模式**: `builtin/__init__.py`（import + BUILTIN_TOOL_TYPES + __all__ + CONFIGURABLE_BUILTIN_TOOL_NAMES）+ `tool_composition.py` always_on tuple
- **循环导入规避**: 服务层懒加载（`from X import Y` 放函数内），避免 `builtin → tool → services → runtime → registry → builtin` 循环
- **工具注册测试**: `BUILTIN_TOOL_NAMES` 由 `BUILTIN_TOOL_TYPES` 自动派生；`_TOOLS` 在 learner_server 是 `mcp.types.Tool` 对象（用 `.name`）
- **always_on 教学工具清单**（当前 13 个）: competency_map/job_analysis/get_annotation_task/annotation_check/write_learning_record/generate_iou_demo/log_decision/evaluate_teaching_plan/verify_foresight/improve_teaching_flow/finalize_diagnosis/graph_query/ability_radar
- **chart 契约**: `metadata.chart = {type: scorecard|radar|progress|graph, data}`
- **docx 竞赛文件读取**: `python-docx`（`Document(p).paragraphs` + `.tables`）
- **学习记录字段**: `type`(diagnosis/theory_mastered/annotation_exercise) + `f1/error_pattern/pattern_status/readiness/knowledge_point/task_id/timestamp/foresight`
- **决策审计**: `append_decision` 无 kind 校验，可直接加 `struggle_intervention`
- **pyBKT 评估结论**: 数据稀疏（29 技能/每技能 1-3 样本），不引入库，只借鉴状态追踪思路

## 七、git 状态

- 分支: main（用户批准直接 main 提交，不用功能分支）
- 近期提交: `3f6a6d5a`(困难检测spec) → `c98300da`(困难检测计划) → HEAD
- docs/ 被 gitignore，提交需 `git add -f docs/...`
- 未跟踪文件（无关）: `coze_teach.txt`、`scripts/analyze_coze.py`、`工具开发/`、`研究与学习/`、`标注星图_*.docx`

## 八、恢复后第一步

1. 读本文件 + `docs/specs/struggle-detector-implementation-plan.md`
2. 询问用户执行方式（Subagent-Driven 已选，确认是否继续）
3. 开始 Task 1: StruggleDetector 3 信号检测器
4. 完成后按计划推进 Task 2-6
5. 困难检测完成后，重新 brainstorm 专门化改造的剩余两个子项目（工作台/任务引导）
