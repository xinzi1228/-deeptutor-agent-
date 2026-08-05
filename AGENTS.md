# 标注星图 (DeepTutor fork) — AGENTS.md

DeepTutor 的 fork，改造为**数据标注教学平台**（讯飞职教竞赛项目，9/1 交付）。核心是 `chat` capability + `annotation-coach` persona 驱动的标注教学 Agent，全中文界面。

**当前注册状态**（已核实）：capability 只注册 `chat`（`runtime/bootstrap/builtin_capabilities.py` 仅一行）；persona 只留 `annotation-coach`；上/下游模块（solve/research/visualize、teacher/peer persona 等）代码仍在但**未注册、非主路径**。

---

## 开发操作（避免踩坑）

### 启动
```bash
# 一键（Windows）：后端 8001 + 前端 3782 + 可选 Label Studio 8080
start_all.bat
# 手动拆分：
python -m uvicorn deeptutor.api.main:app --host 127.0.0.1 --port 8001
# 前端（必须加 IPv6 修复 env，见下）
set DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001 && npx next dev --port 3782
```

### 硬性坑
- **IPv6**：前端必须设 `DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001`——`localhost` 会解析到 `::1` 而后端只绑 IPv4，不设连不上（`web/proxy.ts` 按此 rewrite `/api/*`、`/ws/*`）。
- **坏代理**：本机 `HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:7890` 是坏的。`next build`/`npm ci` 前必须清掉：`$env:HTTP_PROXY=""; $env:HTTPS_PROXY=""`。
- **中文乱码**：PowerShell 跑 python 前设 `$env:PYTHONIOENCODING="utf-8"`。
- **前端 dev 冷启动慢**：首次打开等 60–90 秒属正常。
- **Label Studio 可选**：`start_label_studio.bat`（首次自动 init，账号 `admin@localhost/admin123`）。前端入口 = Annotation 页「专业模式」（iframe `localhost:8080`）。不装不影响核心教学。

### 验证
- 后端测试：`pytest`（配置 `strict-markers` + `--import-mode=importlib`）。基线 **~2985 passed / ~33 预存在失败**（Windows 路径/GBK/可选依赖 telegram·slack/sandbox，均与功能无关）。聚焦验证：`pytest tests/tools/test_annotation_check.py -k <case>`。
- 前端：`cd web && npx tsc --noEmit` + `next build`。
- 工具注册自检：`python test_registration.py`。

### Git 约定
- 用户批准**直接提交 main**（不用功能分支），push 到 `origin/main`（`github.com/xinzi1228/-deeptutor-agent-`）。
- **`data/` 和 `docs/` 被 gitignore**。教学资产 `data/user/workspace/task_bank.json`、`competency_tree.json` 和交接文档 `docs/*.md` 已 `git add -f` 纳入，**改动后需 `git add -f` 重新提交**。

---

## 架构速览

```
CLI / WebSocket /api/v1/ws / SDK → DeepTutorApp.start_turn
  → TurnRuntimeManager → ChatOrchestrator（解析 capability，仅 chat）
  → AgenticChatPipeline（system prompt 组装 + 工具挂载 + agentic loop ≤8 轮）
  → 全部事件经 StreamBus → 订阅者
```

- **核心对象**：`UnifiedContext`（`core/context.py`）流经全链；`StreamBus`（`core/stream_bus.py`）扇出事件（StreamEventType 见 `core/stream.py`）。
- **两层插件**：Tool（单次、LLM 调用）vs Capability（多阶段、持有回合）。本 fork 教学逻辑全在 Tool 层。
- **教学核心文件**：`agents/chat/agentic_pipeline.py`（prompt 组装）、`agents/_shared/tool_composition.py`（always_on 挂载）、`tools/builtin/__init__.py`（工具注册）。

### always_on 工具 = 21 个（`tool_composition.py` ~L190）
- 系统 5：`write_memory` `web_fetch` `github` `ask_user` `cron`
- 教学 16：`render_ui` `competency_map` `ability_radar` `struggle_detect` `teaching_flow` `job_analysis` `get_annotation_task` `annotation_check` `write_learning_record` `generate_iou_demo` `log_decision` `evaluate_teaching_plan` `verify_foresight` `improve_teaching_flow` `finalize_diagnosis` `graph_query`

**加新工具必须同步 4 处**：`tools/builtin/__init__.py`（import + `BUILTIN_TOOL_TYPES` + `__all__` + `CONFIGURABLE_BUILTIN_TOOL_NAMES`）+ always_on tuple + `PERSONA.md` 教 Coach 使用 + 冒烟。
**循环导入规避**：服务层 import 放函数内（懒加载）。
**chart 契约**：`metadata.chart = {type: scorecard|radar|progress|graph|quiz_card, data}`，前端 `ChatChartCard` 读 `tool_result.metadata.tool_metadata.chart`。

### 教学数据资产（全在 git，clone 即用）
- `data/user/workspace/task_bank.json`（12 任务 5 题型）+ `competency_tree.json`（能力树）
- `deeptutor/skills/builtin/annotation-guide/`（规范库 → 引用溯源 `/api/v1/standards` 数据源）
- `web/public/images/`（17 张任务图）

### 双份拷贝陷阱
- `PERSONA.md`：源 = `services/persona/presets/annotation-coach/`；运行时读 `data/user/workspace/personas/annotation-coach/` 副本（gitignored，首次启动自动拷贝）。**改 persona 要改源文件**。
- `flow-*.md`：skill references 与 persona references 各一份，需同步。

---

## 关键文件

| 路径 | 用途 |
|------|------|
| `deeptutor/runtime/orchestrator.py` | ChatOrchestrator 统一入口 |
| `deeptutor/agents/chat/agentic_pipeline.py` | 默认 chat 管道 |
| `deeptutor/agents/_shared/tool_composition.py` | always_on 工具挂载 |
| `deeptutor/tools/builtin/__init__.py` | 全部内置工具注册 |
| `deeptutor/api/routers/profile.py` | trace-log / teaching-flow / standards 端点 |
| `deeptutor/api/routers/shares.py` + `services/share.py` | 免登录分享 |
| `deeptutor/api/routers/cron.py` + `services/cron/` | 定时任务管理 |
| `deeptutor/tools/render_ui_tool.py` + `web/components/chat/home/ChatChartCard.tsx` | 生成式 UI |
| `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` | Coach 人设（多专家+规范引用+定时提醒+render_ui） |

## 交接与优先级

- 交接文档体系（压缩/换人后先读）：`docs/session-handoff.md`（恢复入口）+ `docs/august-changes-record.md`（8 月 130 提交全记录 + 借鉴来源 GitHub 地址）+ `docs/handoff-to-ai.md`。
- **当前最紧要**：竞赛交付材料（01报名表/02Demo说明/05合规/06材料包，9/1 截止），素材在 `docs/` 已齐全。
