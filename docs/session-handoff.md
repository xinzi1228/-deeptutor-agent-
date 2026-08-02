# 会话交接文档（Compression Handoff v2）

> 用途: 压缩上下文前的状态快照。恢复后据此无缝继续。
> 创建: 2026-08-02（v2 更新——多专家角色体系规划完成，待实施）

---

## 一、项目定位与竞赛背景

- **项目**: DeepTutor 开源项目 fork，彻底改造为「**标注星图**」数据标注教学 Agent 产品
- **竞赛**: 科大讯飞 XA-202603（星辰 Agent 平台）——**平台开放自由选择，DeepTutor 可作为交付**
- **竞赛核心**: 6 模块（①学习计划 ②会话管理 ③任务引导 ④困难检测 ⑤学习报告 ⑥练习批改）+ 6 份交付材料
- **竞赛文件**: `标注星图_团队分工与周报模板_v5.5.docx`（团队 6 人，目标 2026-09-01）
- **产品**: 品牌「标注星图」/ "Annotation Star Map"，前端只留 Home/Annotation/Progress/Memory/Settings + 认证/admin

## 二、当前完成度（竞赛 6 模块 + 3 优化方向）

| 模块/方向 | 状态 |
|-----------|------|
| ①学习计划引擎 | ✅（course_plan 4 模块 + finalize_diagnosis） |
| ②会话管理器 | ✅（三层记忆 + 断点续学） |
| ③任务引导引擎 | ✅（TeachingFlowEngine 6 步状态机 + 像素校验 + 新题型） |
| ④困难检测介入 | ✅（StruggleDetector + struggle_detect 工具） |
| ⑤学习报告插件 | ✅（对话可视化 4 图表 + Progress 面板 + 打卡徽章） |
| ⑥练习+批改引擎 | ✅（annotation_check 5 题型 + grading 扩展 + task_bank 12 任务） |
| 优化 1: 工作台裁剪 | ✅（标注星图彻底改造） |
| 优化 2: 任务引导引擎化 | ✅ |
| 优化 3: 语音/打卡徽章 | ✅（语音基础已有不动，打卡+6 徽章完成） |
| **多专家角色体系**（借鉴 agency-agents） | 🔴 **spec+计划已提交，未实施** |

## 三、近期完成的功能（全部已提交）

### 1. 多专家角色体系（最新，规划完成待实施）
- **spec**: `docs/specs/expert-roles-design.md`（`3592b2e3`）
- **计划**: `docs/specs/expert-roles-implementation-plan.md`（`ab147392`，5 任务 TDD）
- **内容**: 借鉴 `msitarzewski/agency-agents`（agent 角色封装 frontmatter+Identity/Mission/Rules/Capabilities/Processes/Deliverables + divisions.json 索引）+ `jnMetaCode/agency-orchestrator`（编排+验收核验）
- **3 借鉴点落地**:
  - A: 6 专家角色集（learning_planner/session_steward/task_guide/struggle_detective/report_analyst/grading_expert 对应竞赛 6 模块），annotation-coach 总协调按阶段路由
  - B: 轻量编排——TeachingFlowEngine 加 `expert_route`（阶段→专家）+ annotation_check 自动 readiness 验收（F1≥0.85→advance / 0.7-0.85→advance_with_caution / 0.65-0.7→more_practice / <0.65→review_first）
  - C: `experts_manifest.json`（divisions.json 风格）+ pytest 双向一致校验 + frontmatter 完整校验

### 2. 打卡徽章引擎（`072c2669`→`745f7da8`，6 提交）
- `deeptutor/services/achievements.py`: 从 learning records 派生打卡（日期/streak 从今天往前）+ 6 徽章（first_step/streak_3/streak_7/first_pass/practice_10/module_clear）+ 阶段通关双路径（course_plan 优先/≥5 任务降级，fallback 仅 plan 不可用时）
- `GET /api/v1/achievements`（auth-at-mount）+ Progress 页 `CheckinCalendar`（GitHub 热力图 12 周）+ `BadgeWall`（徽章墙）
- 20 功能测试过；冒烟: 真实数据 2 天/streak 2/first_step 解锁

### 3. 任务引导引擎（`c6d45a30`→`d94a789f`，14 提交）
- `TeachingFlowEngine`: 任务级 6 步状态机（select_task→show_task→waiting→evaluate→feedback→record）+ gate + blocked 报告 + flow_state.json（默认持久化到 workspace，in_memory opt-in）
- `teaching_flow` 工具（query/advance/reset/start_task/block + 下一步提示），always-on 第 15 个
- `annotation_check` 像素校验（edge/overlap/tightness 无 GT 启发式）+ 新题型评测（judgment/standard/error_case）+ task_id 自动推进 evaluate→feedback
- `grading.py` 扩展（tf/规范/错误案例）
- task_bank 新增 task10-12（判断/规范/找错）
- 59 功能测试过

### 4. 工作台彻底改造（标注星图，`c89537c3`→`0af5ed78`，11 提交）
- capability 只留 chat；persona 只留 annotation-coach（固定默认，生产路径生效）
- 删 9 路由目录（book/co-writer/partners/playground/agents/knowledge/notebook/space/profile）；侧边栏 4 项
- 品牌「标注星图」；保留页面 UI 裁剪；能力选择器只留 chat

### 5. 困难检测介入（`28e06ab9`→`e417ffc2`，10 提交）
- `StruggleDetector` 3 信号 + intervention_suggestion + `struggle_detect` 工具（LLM 解释层降级）+ PERSONA 规则 12

### 6. 更早（41+ 提交）
- 知识图谱全套（knowledge_graph/graph_query/graph_tool/MCP/前端面板）
- 对话可视化 4 图表（chart_cards/ability_radar/ChatChartCard）
- 诊断式教学/决策审计/对抗评估/foresight/教学自改进/CRAG/docx 手册/Coach 绩效
- 3 份 fork 文档（docs/fork-features*.md）

## 四、当前待办（唯一挂起项）

### A. 多专家角色体系实施（下一步，立即执行）
- **spec**: `docs/specs/expert-roles-design.md`（`3592b2e3`）
- **计划**: `docs/specs/expert-roles-implementation-plan.md`（`ab147392`，5 任务 TDD）
- **执行方式**: 未选（Subagent-Driven 推荐 vs Inline）——压缩前未确认
- **任务清单**:
  1. 6 专家角色文件（`annotation-coach-flows/references/experts/*.md`）+ PERSONA 专家协作节
  2. `experts_manifest.json` + 一致性校验测试
  3. `TeachingFlowEngine.expert_route` + teaching_flow query 附带 expert
  4. `annotation_check` 自动 readiness 验收
  5. 全量回归 + 冒烟

### B. 已记录的可选后续（非阻塞）
- 死代码清理（orphaned 组件: space/* agents/* knowledge/* partners/* CapabilityConfigCard；ChatComposer config-gating props；reference-picker dialogs）
- 热力图列顺序（新→旧 vs GitHub 旧→新）+ 两组件重复 fetch 提共享 helper
- `course_plan` task10-12 模块映射 + `KP_TO_SKILL_ALIASES` 新知识点
- `error_case` 评分语义（学生只列错误 id 得 2/3）
- 全量验证: build 需清 proxy（`127.0.0.1:7890` 坏，fonts.gstatic.com 拉取失败）

## 五、演示环境与数据状态

- **数据**: `data/user/workspace/learning/`（records/decisions/brief/course_plan/knowledge_graph/flow_state.json）
  - 真实数据: 2 条记录（diagnosis + task1 F1=0.5）+ 打卡 2 天/streak 2 + 图谱 43 节点/52 边
  - **task_bank 已扩展到 12 任务**（task10-12: judgment/standard/error_case）
- **服务启动**（分离启动绕过 launcher 前端健康检查 bug）:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  python -m deeptutor_cli.main serve --port 8001          # 后端
  cd web; npx next dev --port 3782                        # 前端（另开终端）
  # 若 build/dev 拉 fonts.gstatic.com 失败: 清 HTTP_PROXY/HTTPS_PROXY
  ```
- **Label Studio**: Docker 容器 `ls` 端口 8080，token `ad69bdb5f500f6ab8a40c53da31bf60a23a468ab92`
  - Docker Desktop: `C:\Program Files\Docker\Docker\Docker Desktop.exe`
- **冒烟清单**: `docs/smoke-checklist.md`

## 六、关键技术事实（复用，避免重新探索）

- **测试**: pytest + pytest-asyncio（function-scoped event loop）；PowerShell 需 `$env:PYTHONIOENCODING="utf-8"` 防中文乱码；前端 `npx tsc --noEmit`
- **工具注册**: `builtin/__init__.py`（import + BUILTIN_TOOL_TYPES + __all__ + CONFIGURABLE_BUILTIN_TOOL_NAMES）+ `tool_composition.py` always_on tuple
- **always_on 教学工具 15 个**: competency_map/job_analysis/get_annotation_task/annotation_check/write_learning_record/generate_iou_demo/log_decision/evaluate_teaching_plan/verify_foresight/improve_teaching_flow/finalize_diagnosis/graph_query/ability_radar/struggle_detect/teaching_flow
- **循环导入规避**: 服务层懒加载（import 放函数内），避免 builtin→tool→services→runtime→registry→builtin 循环
- **工具注册测试**: `BUILTIN_TOOL_NAMES` 由 `BUILTIN_TOOL_TYPES` 派生；`_TOOLS` 在 learner_server 是 `mcp.types.Tool` 对象（用 `.name`）
- **chart 契约**: `metadata.chart = {type: scorecard|radar|progress|graph, data}`，从 tool_result 事件的 `metadata.tool_metadata.chart` 读取
- **flow 镜像**: flow-*.md 有 2 份拷贝（skill references + persona references）需同步；PERSONA.md 有 preset + workspace 副本（workspace gitignored 但运行时生效）
- **TeachingFlowEngine**: 无参构造持久化到 `data/user/workspace/learning/flow_state.json`；`in_memory=True` 显式 opt-in；`advance/block` 未知 step 抛 ValueError；`on_evaluated(task_id, f1)` 自动推进 evaluate→feedback
- **readiness_gate 6 判定**: advance/advance_with_caution/review_first/step_down/diagnose_again/more_practice（decision-matrix.md）
- **自动 readiness 阈值**（多专家计划 Task 4 将加）: F1≥0.85→advance / 0.7-0.85→advance_with_caution / 0.65-0.7→more_practice / <0.65→review_first
- **learning records 字段**: type(diagnosis/theory_mastered/annotation_exercise) + f1/error_pattern/pattern_status/readiness/knowledge_point/task_id/timestamp/foresight
- **docx 竞赛文件读取**: python-docx
- **pyBKT 结论**: 数据稀疏不引入库

## 七、git 状态

- 分支: main（用户批准直接 main 提交，不用功能分支）
- HEAD: `ab147392`（多专家角色体系实施计划）
- docs/ 被 gitignore，提交需 `git add -f docs/...`
- data/ 被 gitignore，task_bank.json/flow_state.json 提交需 `git add -f`
- 未跟踪（无关）: `coze_teach.txt`、`scripts/analyze_coze.py`、`工具开发/`、`研究与学习/`、`标注星图_*.docx`
- 已知: `web/next-env.d.ts` 是 Next.js 工具产物（next build 后可能变 M，无关）
- 全量测试预存在失败 ~33（Windows 路径/GBK/可选依赖/sandbox），均与功能无关

## 八、恢复后第一步 + 交接提示词

**交接提示词**（压缩后直接说这句即可无缝继续）:

> 读 docs/session-handoff.md + docs/specs/expert-roles-implementation-plan.md，继续多专家角色体系实施（Subagent-Driven），从 Task 1 开始。加载 subagent-driven-development 技能。

**恢复步骤**:
1. 读 `docs/session-handoff.md`（本文件）+ `docs/specs/expert-roles-implementation-plan.md`
2. 确认执行方式（Subagent-Driven 推荐）
3. 开始 Task 1: 6 专家角色文件 + PERSONA 协作节
4. 按计划推进 Task 2-5
5. 完成后（可选）做死代码清理等 B 项后续
