# DeepTutor Fork → 标注星图：完整接力交接文档

> 用途: 发给 AI 接力工作的完整上下文。含 clone 起点以来的全部改动、架构、功能、技术事实、待办。
> 更新: 2026-08-04
> fork 起点: `43805736`（数据标注教学智能体）之后共 **164 个提交**
> 远程: https://github.com/xinzi1228/-deeptutor-agent-.git（分支 main）

---

## 〇、项目是什么

- **上游**: HKUDS/DeepTutor（开源 AI 教学 Agent 平台，Python + Next.js）
- **本 fork**: 彻底改造为「**标注星图**」数据标注教学 Agent 产品
- **竞赛**: 科大讯飞 XA-202603（星辰 Agent 平台）——平台开放自由选择，DeepTutor 作为交付
- **竞赛核心**: 6 模块（①学习计划 ②会话管理 ③任务引导 ④困难检测 ⑤学习报告 ⑥练习批改）+ 6 份交付材料
- **竞赛文件**: `标注星图_团队分工与周报模板_v5.5.docx`（团队 6 人，目标 2026-09-01）
- **产品**: 界面全中文（保留 en/zh 切换），前端只留 Home/Annotation/Progress/Memory/Settings/Standards/Tasks + 认证/admin

## 一、架构基础（上游 DeepTutor 保留能力）

- **Agent-native**: 每个 turn 走 agentic loop（label 驱动 LLM 协议，max 8 轮），工具调用并行分发
- **两图层**: Tools（单次 LLM 调用）+ Capabilities（多阶段 turn 拥有）——本项目只用 `chat` capability
- **StreamBus**: 统一事件流（STAGE/THINKING/TOOL_CALL/TOOL_RESULT/CONTENT/RESULT 等），CLI/WS/SDK 订阅
- **三层记忆**: L1 轨迹 → L2 摘要 → L3 画像（含 consolidation/reflection）
- **Persona + Skills**: voice preset（eager）+ SKILL.md playbook（lazy，read_skill 按需加载）
- **工具注册**: `deeptutor/tools/builtin/__init__.py` + `agents/_shared/tool_composition.py` always_on
- **多用户**: ContextVar 隔离 + grants + admin
- **RAG 多后端** / **Cron 服务** / **Partners IM 多渠道** / **MCP server**（learner_server）

## 二、竞赛 6 模块落地（fork 核心）

| 模块 | 实现 | 关键提交 |
|------|------|---------|
| ①学习计划 | `course_plan` 4 模块 + `finalize_diagnosis` 建课 + `competency_map`/`job_analysis` | 早期 |
| ②会话管理 | 三层记忆 + 断点续学 + `session_steward` 专家 | 早期 |
| ③任务引导 | `TeachingFlowEngine` 6 步状态机 + `teaching_flow` 工具 + 像素校验 | `c6d45a30`→`7648b2dc` |
| ④困难检测 | `StruggleDetector` 3 信号 + `struggle_detect` 工具 + 介入建议 | `28e06ab9`→`e417ffc2` |
| ⑤学习报告 | Progress 页全面板 + 对话内图表 + 打卡徽章 + 教学轨迹 | 多轮 |
| ⑥练习批改 | `annotation_check` 5 题型 + `grading` 扩展 + task_bank 12 任务 | `3e6f7e6e`→`d70a762e` |

## 三、15 个 always-on 教学工具

`competency_map` / `job_analysis` / `get_annotation_task` / `annotation_check` / `write_learning_record` / `generate_iou_demo` / `log_decision` / `evaluate_teaching_plan` / `verify_foresight` / `improve_teaching_flow` / `finalize_diagnosis` / `graph_query` / `ability_radar` / `struggle_detect` / `teaching_flow` / **`render_ui`**（新增）

## 四、近期主要改动（按主题）

### 1. 多专家角色体系（8/2）
- 6 专家角色卡（learning_planner/session_steward/task_guide/struggle_detective/report_analyst/grading_expert 对应竞赛 6 模块），agency-agents 结构
- `experts_manifest.json`（divisions.json 风格）+ pytest 双向一致校验
- `EXPERT_ROUTE` 阶段→专家映射 + `expert_route()` + state 附带 expert
- `auto_readiness(f1)` 自动 readiness 判定（F1≥0.85→advance 等），写入 flow_state + metadata

### 2. 界面全中文化（8/3）
- 4 处默认语言 en→zh（app-shell-storage/AppShellContext/init.ts）
- zh locale 静态加载（首帧即中文）+ 后端 ui.language 默认 zh
- 补齐 **131 个未翻译 i18n key**（设置/聊天/记忆/标注页英文残留）
- 保留 en/zh 切换

### 3. 进度页 Tab 化（8/3）
- 13 面板分 4 Tab（概览/记录/成就/图谱），默认概览一屏
- 记录 Tab：教学流程面板（6 步状态条）+ 教学轨迹（可展开回合链）+ 决策 + 课程计划

### 4. 教学轨迹（8/3）
- `GET /api/v1/profile/trace-log`: 聚合 records + decisions 成教学回合（F1/readiness/卡住介入/决策），±10 分钟邻近匹配
- Timeline 升级为可展开教学回合链

### 5. 教学流程面板（8/4）
- `GET /api/v1/profile/teaching-flow`: 只读 flow_state.json，返回 6 步状态
- 前端横向 6 步状态条（done 绿/in_progress 蓝/blocked 红/pending 灰）+ 专家路由

### 6. 引用溯源（8/3）
- `GET /api/v1/standards`: 从 annotation-guide skill references 读 5 个规范文档 + 章节
- 侧边栏「标注规范」库页
- 对话 `〔规范: 文档名§章节〕` → remark 插件 → 📖 chip → 点击弹窗原文
- `parseStandardHref` 解码 percent-encoded href（markdown URL 编码）

### 7. 定时学习提醒（8/3）
- cron 工具已存在（schedule/list/cancel），补 8 项测试 + PERSONA 教 Coach 用
- 对话「30秒后提醒我」→ Coach 注册 every-30s job → `execute_job` 到点生成教学提醒进会话

### 8. 定时任务管理 UI（8/4）
- `CronService.set_job_enabled`（启停持久化）
- `cron.py` REST API（GET/DELETE/PATCH jobs，owner 隔离 chat:local-admin）
- 侧边栏「定时任务」页（查看/启停/删除/空态）

### 9. 免登录分享（8/4）
- `ShareStore`（token_urlsafe(16) + JSON 持久化 + 过期 + 撤销）
- `POST /api/v1/shares`（鉴权）+ `GET /api/v1/share/{token}`（公共路由，token 白名单只读）
- Home 会话「分享」按钮 → 弹窗链接 + iframe 片段；`/share/[token]` 只读页
- 修复 Next.js 16 `params` Promise 需 `React.use()` 解包

### 10. 生成式 UI（8/4）
- 借鉴 AG-UI structured-message 思想，零框架依赖，落地现有 `metadata.chart` 通道
- `render_ui` 工具（校验组件 JSON → metadata.chart）+ `validate_component`
- ChatChartCard 扩展 `quiz_card`（可交互练习卡片：题目+选项+点击即时对错+解释）
- PERSONA 教 Coach 出题用 render_ui

### 11. 死代码清理（8/2）
- 删 64 文件/~19k 行（space/agents/knowledge/partners orphan 组件 + CapabilityConfigCard + 死 props）
- ChatComposer 剥离 3 个死配置门控 props

## 五、竞赛 6 模块 + 3 优化 + 差距项 完成度

| 类别 | 项 | 状态 |
|------|-----|------|
| 竞赛 6 模块 | ①-⑥ | ✅ 全部完成 |
| 3 优化 | 工作台裁剪/任务引导引擎化/打卡徽章 | ✅ |
| 差距 P0 | 全中文/教学轨迹/引用溯源 | ✅ |
| 差距 P1 | 流程可视化/定时提醒/定时任务管理 | ✅ |
| 差距 P2 | 分享/生成式 UI | ✅ |
| 差距 P2 | 语音 agent 循环 | ⏳ 未做（大工作量，需外部 STT/TTS） |
| 竞赛材料 | 01报名表/02Demo说明/05合规/06材料包 | ⏳ 未写（9/1 硬要求） |

## 六、关键技术事实（避免重新探索）

- **测试**: pytest + pytest-asyncio（function-scoped loop）；PowerShell 需 `$env:PYTHONIOENCODING="utf-8"`；前端 `npx tsc --noEmit`、`npm run test:node`
- **全量基线**: 2979-2985 passed / 33 预存在失败（Windows 路径、GBK、缺失可选依赖 telegram/slack、sandbox env）——均与功能无关
- **工具注册**: `builtin/__init__.py`（import + BUILTIN_TOOL_TYPES + __all__ + CONFIGURABLE）+ `tool_composition.py` always_on tuple
- **循环导入规避**: 服务层懒加载（import 放函数内）
- **chart 契约**: `metadata.chart = {type, data}`，从 tool_result 事件 `metadata.tool_metadata.chart` 读取
- **flow 镜像**: flow-*.md 有 2 份拷贝（skill references + persona references）需同步；PERSONA.md 有 preset + workspace 副本（workspace gitignored 但运行时生效）
- **TeachingFlowEngine**: 无参构造持久化到 `data/user/workspace/learning/flow_state.json`；`in_memory=True` opt-in；`on_evaluated(task_id, f1, readiness=None)` 自动推进
- **readiness_gate 6 判定**: advance/advance_with_caution/review_first/step_down/diagnose_again/more_practice
- **learning records**: type(diagnosis/theory_mastered/annotation_exercise) + f1/readiness/knowledge_point/task_id/timestamp/foresight
- **环境**: 前端 proxy 需 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`（localhost 解析到 ::1 而后端只绑 IPv4）；next build 需清 HTTP_PROXY/HTTPS_PROXY（127.0.0.1:7890 坏）
- **docx 竞赛文件读取**: python-docx

## 七、启动命令

```powershell
$env:PYTHONIOENCODING="utf-8"
python -m deeptutor_cli.main serve --port 8001          # 后端
# 另开终端（必须带 DEEPTUTOR_API_BASE_URL 解决 IPv6 问题）:
cd web; cmd /c "set DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001& npx next dev --port 3782"
# 访问: http://localhost:3782  |  API: http://127.0.0.1:8001/docs
```

## 八、当前待办

### A. 竞赛交付材料（9/1 硬要求，未写）
- 01 报名表 / 02 Demo 说明文档 / 05 合规 / 06 材料包
- 素材已齐全: `docs/fork-features.md`（功能清单）、`docs/daily-report-2026-08-02.md`、`docs/smoke-checklist.md`、`docs/maturity-gap-analysis.md`、6 份 spec/计划

### B. 可选后续（非阻塞）
- 语音 agent 循环（差距文档最后一项，大工作量）
- 死代码清理残留（组件级 aria-label 小英文、可视化模块 fallback 标签）
- 多专家已知小缺口（auto_readiness docstring 4/6、学习记录 readiness 落盘依赖 Coach）
- 热力图列顺序、course_plan task10-12 映射、error_case 部分正确评分

## 九、git 状态

- HEAD: `69ae38e0`（生成式 UI 冒烟截图）
- 备份 tag: `backup-2026-08-04-share-done`（已推送远程）
- docs/ 被 gitignore，提交需 `git add -f docs/...`
- data/ 被 gitignore，task_bank.json/flow_state.json 提交需 `git add -f`
- 未跟踪（无关）: `.playwright-mcp/`、`coze_teach.txt`、`scripts/analyze_coze.py`、`工具开发/`、`研究与学习/`、`标注星图_*.docx`
- 工作树干净（已跟踪文件无未提交改动）

## 十、给接力 AI 的提示词

> 这是 DeepTutor fork「标注星图」数据标注教学 Agent 产品的接力工作。上游是 HKUDS/DeepTutor，fork 起点 `43805736`，之后 164 个提交。产品已完成竞赛 6 模块 + 3 优化 + 全部差距项（多专家/全中文/教学轨迹/流程可视化/规范引用/定时提醒/定时任务管理/免登录分享/生成式 UI），界面全中文。当前最紧要的是**竞赛交付材料**（01报名表/02Demo说明/05合规/06材料包，9/1 截止）——素材在 docs/ 已齐全。项目从 `docs/session-handoff.md` + `docs/maturity-gap-analysis.md` 了解全貌，从 `docs/fork-features.md` 看功能清单。启动需带 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001` 解决 IPv6。测试基线 2985 passed / 33 预存在失败。可用 subagent-driven-development 分任务实施。
