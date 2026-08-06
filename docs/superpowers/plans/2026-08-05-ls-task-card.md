# 议题④ Phase 2 实现计划：LS 任务卡片跳转（ls_task_card）

> 目标：`render_ui` 新增 `ls_task_card` 组件类型，Coach 出卡片 → 学生点击直接跳转 Label Studio 具体标注任务。小独立改动，TDD。

## 现状
- `render_ui_tool.py` 只支持 `quiz_card`（validate_component 白名单）。
- 前端 `ChatChartCard.tsx` 按 `chart.type` 渲染卡片（quiz_card 已有）。
- LS labeling URL：`{LS_BASE_URL}/projects/{project_id}/labeling?task={task_index}`（task_index 0-based 项目任务序号，与导入顺序一致）。
- 议题④ Phase 1 已完成 `ls_import_tasks`（导入任务），卡片跳转补完"导入→跳转"闭环。

## 改动

### 后端 `deeptutor/tools/render_ui_tool.py`
1. `validate_component` 增加 `ls_task_card` 分支（校验 + 规范化）：
   - data 必填：`project_id`(int)、`task_index`(int, ≥0)、`title`(str 非空)
   - 可选：`task_type`(str, 默认 "bbox")、`instructions`(str)
   - 返回 `{"type":"ls_task_card","data":{...}}`（data 里补 `url = f"{LS_BASE_URL}/projects/{project_id}/labeling?task={task_index}"`）
2. `get_definition` description 增加 ls_task_card 用法示例。
3. 复用模块级 `LS_BASE_URL`（从 label_studio_tool import 或本地读 env，用 `os.environ.get("LABEL_STUDIO_URL","http://localhost:8080")`）。

### 前端 `web/components/chat/home/ChatChartCard.tsx`
4. `ChartData` union 增加：
   `{ type: "ls_task_card"; data: { project_id: number; task_index: number; title: string; task_type: string; instructions?: string | null; url: string } }`
5. 新增 `LsTaskCard` 组件：卡片显示 title、task_type 徽标、instructions；底部按钮 `<a href={url} target="_blank" rel="noopener noreferrer">打开标注任务</a>`。空 instructions 不渲染。
6. `ChatChartCard` 顶层增加 `ls_task_card` 分发分支。

### 测试 `tests/tools/test_render_ui_tool.py`
7. 新增用例：
   - `ls_task_card_valid`：合法入参 → success，chart.type="ls_task_card"，data.url 含 `/projects/3/labeling?task=0`
   - `ls_task_card_missing_project_id`：缺 project_id → fail
   - `ls_task_card_negative_task_index`：task_index=-1 → fail
   - `ls_task_card_empty_title`：title 空 → fail
8. 现有 quiz_card 测试不受影响。

### PERSONA（源 + 运行时副本同步）
9. `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` 在 render_ui 指引行后补一条 ls_task_card 用法：
   `引导学生在 Label Studio 标注时用 render_ui 输出任务卡片（component JSON: {"type":"ls_task_card","data":{"project_id":3,"task_index":0,"title":"...","task_type":"bbox","instructions":"..."}}），学生点击卡片跳转 LS 具体任务。`
10. **同步改运行时副本** `data/user/workspace/personas/annotation-coach/PERSONA.md`（seed 只在不存在时拷贝，改源后副本需手动同步）。

## 验证
- `python -m pytest tests/tools/test_render_ui_tool.py -v`（旧 3 + 新 4 全过）
- `cd web && npx tsc --noEmit`（TypeScript 通过）
- `ruff check deeptutor/tools/render_ui_tool.py`
- 回归：`python -m pytest tests/tools/test_label_studio_import_tool.py tests/tools/test_render_ui_tool.py -q`

## 提交（仅 commit，大版本结束统一 push）
- `feat: render_ui 支持 ls_task_card 卡片跳转 Label Studio 具体任务`
- `test: ls_task_card 校验用例 (project_id/task_index/title)`
- 前端 `docs: PERSONA 增加 ls_task_card 使用指引 (源+运行时副本)`
