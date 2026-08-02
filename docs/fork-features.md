# Fork 优化功能清单（vs 上游 DeepTutor）

> **受众**: 开发团队
> **范围**: `43805736`（数据标注教学智能体）至 HEAD 的 41 次提交
> **目的**: 明确每个优化功能在哪看 / 怎么触发 / 预跑状态 / 代码在哪

---

## 一、标注星图工作台彻底改造（Tasks 1-7）

> 目标: 从通用 DeepTutor 工作台收窄为「标注星图」数据标注教学产品（竞品空白领域原创）。
> 设计/计划: `docs/specs/workbench-restructure-design.md`、`docs/specs/workbench-restructure-implementation-plan.md`（`877237a3`/`176a32cf`）。

### 1.1 Capability 白名单（只留 chat）

`deeptutor/runtime/bootstrap/builtin_capabilities.py` 只注册 `chat`（`c89537c3`）。已下线 capability: `deep_solve` / `deep_question` / `deep_research` / `visualize` / `math_animator` / `mastery_path`。CLI 文档已同步清理，`deeptutor run` 只宣传 `chat`。

### 1.2 Persona 白名单（只留 annotation-coach，固定默认）

- persona 只保留 annotation-coach（`39d6c3a8`）
- 生产 turn 解析路径在无 persona 时自动注入 annotation-coach（`bb28b73d`）

### 1.3 前端路由裁剪（删除 9 个通用目录）

`da926980` 删除: `book` / `co-writer` / `partners` / `playground` / `agents` / `knowledge` / `notebook` / `space` / `profile`

workspace 现在只留:
- `/annotation` — 标注工作台
- `/home` — Chat（annotation-coach）
- `/progress` — 学习进度

utility 只留 `memory`（中心/图谱/L1/L2/L3/resolve）与 `settings`。

### 1.4 侧边栏裁 4 项

`SidebarShell.tsx`: PRIMARY_NAV = Home / Annotation / Progress，SECONDARY_NAV = Memory / Settings（`f2e64107`）。`860c835f`/`8fafbdfd` 移除 Home/Memory 内已删功能的残留入口与 `/profile` 死链接。

### 1.5 品牌 → 标注星图

`45e885b6`/`9482cf98`: i18n 值批量替换 + layout / 登录页 / 侧边栏品牌（logo alt / aria-label / 文案）统一为「标注星图」，英文品牌串同步清理。

---

## 二、前端可见功能

> 入口均在侧边栏（`web/components/sidebar/SidebarShell.tsx`）。Annotation / Progress / Memory 三个入口**无条件可见**（不在 `lib/capability-routes.ts` 权限门槛列表内）。

### 2.1 个人中心 Progress 页（`/progress`）

**入口**: 侧边栏 → **Progress**（TrendingUp 图标）→ `web/app/(workspace)/progress/page.tsx`

| 面板 | 组件文件 | 展示内容 | 数据来源 |
|------|---------|---------|---------|
| 统计卡片 | `components/learning-stats/StatCards.tsx` | 最新F1/练习通过率/理论掌握/教学模式/预测命中率 | `/api/v1/profile` |
| 教练绩效 | `components/learning-stats/CoachMetrics.tsx` | F1提升率/模式确认率/预测命中率/自改进次数/决策审计条数 | `/api/v1/profile/coach-metrics` |
| 五维雷达 | `components/learning-stats/RadarChart.tsx` | 框精度/标签准确/完整性/一致性/知识掌握 vs 五级标准 | `/api/v1/profile/radar` |
| 能力图谱 | `components/learning-stats/SkillTree.tsx` | 29 技能掌握状态（绿勾=已掌握） | `/api/v1/profile/skill-tree` |
| F1 成长曲线 | `components/learning-stats/F1Curve.tsx` | 按任务 F1% 折线（≥85 绿色） | `/api/v1/profile/f1-trend` |
| **知识图谱·风险链**（新增） | `components/learning-stats/KnowledgeGraphPanel.tsx` | 掌握/挣扎 + 缺失前置 + 下游受影响 | `/api/v1/profile/knowledge-graph` |
| 教学决策 | `components/learning-stats/DecisionLog.tsx` | 任务推荐/推进判定/路线选择 + rationale | `/api/v1/profile/decisions` |
| 课程计划 | `page.tsx:166-197` 内联 | 4 模块 + **下载手册**（docx） | `/api/v1/profile/course-plan(/docx)` |
| 方案评估 | `components/learning-stats/EvaluationPanel.tsx` | 独立评估员质疑点/修正建议 | `/api/v1/profile/evaluations` |
| 时间线 | `components/learning-stats/Timeline.tsx` | 按日记录流 + readiness 徽章 | `/api/v1/profile/episodes` |
| **记忆整理按钮** | `page.tsx:123-135` | POST `/api/v1/profile/reflect` → 记忆归档合并 | — |

**操作**: 打开 `/progress` 即可看到全部面板。无数据时显示空态占位，不白屏。
**预跑状态**: ✅ 已填充（records 2 条 / 图谱 43 节点含 struggling / 决策 2 条 / 课程计划）。

### 2.2 Annotation 标注工作台（`/annotation`）

**入口**: 侧边栏 → **Annotation**（Tag 图标）→ `web/app/(workspace)/annotation/page.tsx`

- **Basic 模式**（默认）: iframe 内嵌 `web/public/annotation_tool.html`（纯前端，8 个真实任务）
  - 操作: 选任务 → canvas 拖框 → 选标签 → 「检查标注」→ 本地 IOU/F1 评分 + 逐框反馈 → 「问Coach」
  - 问Coach 闭环: 结果写入 localStorage → 跳 `/home` → 聊天页 30s 内自动发给 Coach（`home/[[...sessionId]]/page.tsx:926-942`）
- **Pro 模式**: iframe 直接嵌入 **Label Studio**（`http://localhost:8080`）
  - 预跑状态: ✅ Label Studio 已启动（Docker 容器 `ls`，token `ad69bdb5...`）

### 2.3 Memory 记忆中心（`/memory`）

**入口**: 侧边栏 → **Memory**（Brain 图标）→ `web/app/(utility)/memory/`

| 页面 | 文件 | 内容 |
|------|------|------|
| 主页 | `MemoryHub.tsx` | 三层记忆卡片（L1 轨迹/L2 摘要/L3 画像）+ MemoryGraph 入口 |
| 图谱 | `graph/page.tsx` → `MemoryGraph.tsx` | 三层同心圆图谱（L3 中心/L2 中层/L1 外圈），可缩放拖拽 |
| L1/L2/L3 工作台 | `l1/page.tsx` 等 | 各层文档查看/编辑/审计 |
| 记忆设置 | `/settings/memory` | L2/L3 预算、去重、合并策略 |

### 2.4 Settings 工具开关页（`/settings/tools`）

**入口**: 侧边栏 → **Settings** → Tools

- 11 个标注/教学工具全部可见（`annotation_check` `get_annotation_task` `write_learning_record` `graph_query` 等）
- 分类为「内置工具」区 → **Always on 锁定**（不可开关，`USER_TOGGLEABLE_TOOL_NAMES` 未含）
- 可展开查看每个工具的 when_to_use / input_format / 参数

> ~~Mastery Path 精通之路~~ 已随工作台彻底改造移除（`/space/learning` 路由与 `mastery_path` capability 已下线）。

---

## 三、需对话触发功能

> 全部通过 annotation-coach persona 对话触发。工具已注册为 always-on（第 12 个 = `graph_query`）。

| 功能 | 触发方式（对话输入） | 触发的工具/动作 | 产物 | 预跑状态 |
|------|---------------------|----------------|------|---------|
| **诊断式教学** | "我是零基础想学标注找工作" | `read_memory` → `read_skill` → `competency_map` → `job_analysis` | 学习路线 + brief | ✅（6 回合预跑） |
| **诊断落盘+建课** | 诊断完成 | `finalize_diagnosis` | brief.json + course_plan.json | ✅ |
| **理论教学** | "讲一下 IOU" | `generate_iou_demo` | `iou_demo.html` 交互演示 | ✅（已生成） |
| **图查询风险链** | 问新任务是否有风险 | `graph_query`（risk_path/concepts/mastery） | 风险链 + LLM 解释 | ✅（task1 验证） |
| **评测闭环** | 提交标注 | `annotation_check` → `write_learning_record` + `log_decision` | records + 决策 + 图谱更新 | ✅（回合 6） |
| **决策审计** | 任务推荐/推进判定 | `log_decision` | decisions.jsonl（可追溯理由） | ✅ |
| **foresight 预测** | 记录时带预测 | `write_learning_record` 附带 foresight | 预测命中率统计 | ⚠️ 需下次会话验证 |
| **方案对抗评估** | 对话内 | `evaluate_teaching_plan` | EvaluationPanel 质疑点/建议 | ⚠️ 未触发 |
| **教学自改进** | 指标停滞 | `improve_teaching_flow` | TeachingChangelog | ⚠️ 未触发 |
| **verify_foresight** | 下次会话开始 | `verify_foresight` | 预测命中/未中 | ⚠️ 未触发 |

### CLI 触发方式（无需浏览器）

```powershell
$env:PYTHONIOENCODING="utf-8"
python -m deeptutor_cli.main chat -l zh -p annotation-coach   # 交互对话
# 对话内斜杠命令:
#   /progress     学习进度仪表盘（雷达+F1曲线）
#   /concept-map  能力图谱掌握状态（29技能树）
#   /challenge    出一道迁移挑战题
```

**预跑状态**: `/progress` `/concept-map` 已验证（✅）。`/challenge` 需对话触发（⚠️）。

---

## 四、无法前端可见功能

| 功能 | 位置/接口 | 说明 | 预跑状态 |
|------|----------|------|---------|
| **MCP learner_server** | `deeptutor/services/mcp/learner_server.py` | 19 工具 + 7 资源（stdin/stdout 协议）。运行 `python -m deeptutor.services.mcp.learner_server` | ✅ 19 工具验证 |
| **知识图谱引擎** | `deeptutor/services/knowledge_graph.py` | `KnowledgeGraphStore` build/incremental_update（JSONL 派生索引，确定性可重建） | ✅ 图已生成 |
| **图查询服务** | `deeptutor/services/graph_query.py` | `GraphQueryService` risk_path/concepts/mastery（确定性） | ✅ |
| **记忆演化** | `deeptutor/services/learning_records.py` | Reflection 合并/去重/归档 + episodes 时间线 + atomic facts + TeachingChangelog 自改进 | ✅（changelog 可验证） |
| **课程计划引擎** | `deeptutor/services/course_plan.py` | 确定性建课（4 模块 + DAG）+ `export_docx` 学习手册 | ✅ |
| **对抗性评估** | `deeptutor/tools/evaluate_teaching_plan_tool.py` | TradingAgents 多角色辩论（独立评估员视角） | ✅（代码） |
| **后端 API** | `deeptutor/api/routers/profile.py` | 15 端点（overview/radar/f1-trend/skill-tree/knowledge-graph/decisions/evaluations/course-plan/docx/episodes/foresights/coach-metrics/facts/teaching-changes/reflect） | ✅ 全 200 |
| **IOU/标注检查** | `deeptutor/tools/annotation_check.py` | IOU/F1/Precision/Recall 确定性评测 + 逐框反馈 | ✅ |
| **任务库** | `deeptutor/tools/task_bank_tool.py` | `data/user/workspace/task_bank.json` 9 任务 + 难度 + 知识关联 | ✅ |
| **能力树** | `deeptutor/tools/competency_tool.py` | `competency_tree.json` 4 层树 + 前置依赖 + kp别名映射 | ✅ |
| **CRAG 相关性校验** | `deeptutor/services/...` | awesome-llm-apps 借鉴，检索相关性校准 | ⚠️ 需检索场景 |

---

## 附 A: 41 次提交 → 功能映射

| 功能簇 | 关键提交 |
|--------|---------|
| 标注教练 Persona + Canvas + Label Studio + 记忆追踪 | `43805736` |
| 学习记录持久化 + 个人中心仪表盘 + 开源Agent借鉴 | `694c1165` |
| 前置依赖链/教育学自检/有界诊断brief/课程RAG | `e9cc43f5` |
| 学习者状态 MCP server | `e32894fd` |
| 可重跑建课 | `82bcecaf` |
| IOU 交互演示 | `19c0ed40` |
| 决策审计 | `87416e2a` |
| 对抗性教学评估 + 前端集成 | `2f44656b` `17b84b4e` |
| Label Studio 实机修复 | `9eb1b72f` |
| 记忆进化 Reflection + foresights 预测验证 | `940acc6e` |
| episodes 时间线 + foresights 前端 + atomic facts | `efd9922c` |
| 教学流程自改进 | `0143de71` |
| CRAG + 学习路径手册 docx | `4c08ea40` |
| Coach 成功指标 + 角色氛围 | `5e613103` |
| **知识图谱全套**（存储/查询/工具/钩子/MCP/面板） | `33ae2d86`→`0b1d509f` |
| 回归修复（漏落盘/诊断建课/kp别名） | `b79a178a` `d70ef05f` `4eed12c0` |

---

## 附 B: 演示启动命令速查

```powershell
# 1. 启动后端 + 前端（前端健康检查可能因 Turbopack 首编译超时，改用分离启动）
$env:PYTHONIOENCODING="utf-8"
python -m deeptutor_cli.main serve --port 8001          # 后端（终端 1）
# 另开终端:
cd web; npx next dev --port 3782                        # 前端（终端 2）

# 2. Label Studio（如需 pro 模式）
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# 等引擎就绪后:
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" start ls

# 3. 访问
#   前端: http://localhost:3782   (无需登录, local-admin)
#   API:  http://127.0.0.1:8001/docs
#   LS:   http://localhost:8080   (token: ad69bdb5...)

# 4. 数据产物位置
#   data/user/workspace/learning/  (records/decisions/brief/course_plan/knowledge_graph)
#   data/memory/                   (L1 trace / L2 摘要 / L3 画像)
```
