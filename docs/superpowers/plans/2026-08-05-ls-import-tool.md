# 议题④ LS 联动 Phase 1（ls_import_tasks 导入工具）— 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `ls_import_tasks` 工具：把任务（如 task_bank 数据）导入指定 Label Studio 项目（`POST /api/projects/{id}/import`）。这是 LS 联动闭环（建项目→导入→跳转→标注→回传）的第二环。自建标注台/拟人化/卡片跳转为后续 Phase。

**Architecture:** 在 `deeptutor/tools/label_studio_tool.py` 加 `LabelStudioImportTool`（`name="ls_import_tasks"`），复用 `_ls_request` + `LS_API_TOKEN`。参数 `project_id` + `tasks`(JSON)。TDD：mock `_ls_request`。

**Tech Stack:** Python 3.11+ / pytest-asyncio / aiohttp（经 _ls_request）

**依赖设计文档:** `docs/superpowers/specs/2026-08-05-labelstudio-workbench-design.md`

---

## File Structure

- Modify: `deeptutor/tools/label_studio_tool.py` — 加 `LabelStudioImportTool`
- Create: `tests/tools/test_label_studio_import_tool.py` — 工具测试（mock `_ls_request`）
- Modify: `deeptutor/tools/builtin/__init__.py` — 4 处注册
- Modify: `deeptutor/agents/_shared/tool_composition.py` — **不**加 always_on（LS 工具按需，与 ls_create_project 一致进 CONFIGURABLE 即可，无需 always_on）

---

### Task 1: `LabelStudioImportTool`（TDD）

**Files:**
- Modify: `deeptutor/tools/label_studio_tool.py`
- Test: `tests/tools/test_label_studio_import_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_label_studio_import_tool.py
import json
import pytest

import deeptutor.tools.label_studio_tool as ls_mod
from deeptutor.tools.label_studio_tool import LabelStudioImportTool


@pytest.fixture(autouse=True)
def _force_token(monkeypatch):
    monkeypatch.setattr(ls_mod, "LS_API_TOKEN", "test-token")


@pytest.mark.asyncio
async def test_import_success(monkeypatch):
    async def fake_request(method, path, **kwargs):
        assert method == "POST"
        assert path == "/api/projects/7/import"
        body = kwargs["json"]
        assert isinstance(body, list) and len(body) == 2
        return {"task_count": 2, "annotation_count": 0}

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    tasks = json.dumps([{"data": {"image": "a.jpg"}}, {"data": {"image": "b.jpg"}}], ensure_ascii=False)
    result = await tool.execute(project_id=7, tasks=tasks)
    assert result.success is True
    assert "2" in result.content
    assert result.metadata["imported"]["task_count"] == 2


@pytest.mark.asyncio
async def test_import_invalid_json_fails(monkeypatch):
    async def fake_request(method, path, **kwargs):
        raise AssertionError("should not call api")

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    result = await tool.execute(project_id=7, tasks="not-json")
    assert result.success is False


@pytest.mark.asyncio
async def test_import_missing_token_fails(monkeypatch):
    monkeypatch.setattr(ls_mod, "LS_API_TOKEN", "")
    async def fake_request(method, path, **kwargs):
        raise AssertionError("should not call api")

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    result = await tool.execute(project_id=7, tasks="[]")
    assert result.success is False


@pytest.mark.asyncio
async def test_import_missing_project_id_fails(monkeypatch):
    async def fake_request(method, path, **kwargs):
        raise AssertionError("should not call api")

    monkeypatch.setattr(ls_mod, "_ls_request", fake_request)
    tool = LabelStudioImportTool()
    result = await tool.execute(tasks="[]")
    assert result.success is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_label_studio_import_tool.py -v`
Expected: FAIL with `ImportError: cannot import name 'LabelStudioImportTool'`

- [ ] **Step 3: Write minimal implementation**

Append to `deeptutor/tools/label_studio_tool.py` (follow the existing tool classes' style):

```python
class LabelStudioImportTool(BaseTool):
    """Import annotation tasks into an existing Label Studio project."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="ls_import_tasks",
            description=(
                "Import a batch of annotation tasks into an existing Label Studio project. "
                "Pass project_id and tasks as a JSON list, e.g. "
                '[{"data": {"image": "/path/a.jpg"}}, {"data": {"image": "/path/b.jpg"}}]. '
                "Returns the import report (task_count)."
            ),
            parameters=[
                ToolParameter(
                    name="project_id",
                    type="integer",
                    description="Label Studio project ID.",
                    required=True,
                ),
                ToolParameter(
                    name="tasks",
                    type="string",
                    description="JSON array of task objects (each with a `data` key).",
                    required=True,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        if not LS_API_TOKEN:
            return ToolResult(
                content=(
                    "Label Studio API token not configured. "
                    "Set LABEL_STUDIO_API_TOKEN (Account & Settings → Access Token)."
                ),
                success=False,
            )
        try:
            project_id = int(kwargs.get("project_id"))
        except (TypeError, ValueError):
            return ToolResult(content="Error: project_id is required (integer).", success=False)
        tasks_raw = kwargs.get("tasks", "[]")
        try:
            tasks = json.loads(tasks_raw) if isinstance(tasks_raw, str) else tasks_raw
        except json.JSONDecodeError as e:
            return ToolResult(content=f"Error: tasks JSON 解析失败: {e}", success=False)
        if not isinstance(tasks, list):
            return ToolResult(content="Error: tasks 必须是 JSON 数组。", success=False)
        if not tasks:
            return ToolResult(content="Error: tasks 为空。", success=False)
        try:
            result = await _ls_request("POST", f"/api/projects/{project_id}/import", json=tasks)
        except Exception as e:
            return ToolResult(content=f"导入失败: {e}", success=False)
        return ToolResult(
            content=f"已导入 {result.get('task_count', 0)} 个任务到项目 {project_id}。",
            metadata={"imported": result, "project_id": project_id},
        )
```

（把 `__all__` 里的 LabelStudioImportTool 加入——先确认 label_studio_tool.py 是否有 `__all__`，有则加，无则跳过。）

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tools/test_label_studio_import_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/label_studio_tool.py tests/tools/test_label_studio_import_tool.py
git commit -m "feat: ls_import_tasks 工具 (导入任务到 LS 项目)"
```

---

### Task 2: 注册 `ls_import_tasks`（4 处，CONFIGURABLE）

**Files:**
- Modify: `deeptutor/tools/builtin/__init__.py`

- [ ] **Step 1: 注册 4 处**（在 `LabelStudioCheckTool` 附近，LS 工具组）

`deeptutor/tools/builtin/__init__.py`：

```python
# 1) import（label_studio_tool import 区，LabelStudioCheckTool 后）
    LabelStudioImportTool,

# 2) BUILTIN_TOOL_TYPES 列表（LabelStudioCheckTool 后）
    LabelStudioImportTool,

# 3) CONFIGURABLE_BUILTIN_TOOL_NAMES 元组（"ls_check_annotations" 后）
    "ls_import_tasks",

# 4) __all__ 列表（"LabelStudioCheckTool" 后）
    "LabelStudioImportTool",
```

**不加入 always_on**（与 ls_create_project/ls_check_annotations 一致，按需配置）。

- [ ] **Step 2: 验证注册 + 测试**

Run:
```powershell
python -c "from deeptutor.tools.builtin import BUILTIN_TOOL_TYPES, CONFIGURABLE_BUILTIN_TOOL_NAMES, __all__; print('LabelStudioImportTool' in [t.__name__ for t in BUILTIN_TOOL_TYPES], 'ls_import_tasks' in CONFIGURABLE_BUILTIN_TOOL_NAMES, 'LabelStudioImportTool' in __all__)"
```
Expected: `True True True`

Run: `python -m pytest tests/tools/test_label_studio_import_tool.py -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add deeptutor/tools/builtin/__init__.py
git commit -m "chore: 注册 ls_import_tasks (CONFIGURABLE, 非 always_on)"
```

---

### Task 3: 冒烟验证（真实 LS 导入）

- [ ] **Step 1: 确认 LS 运行 + token**

LS 应在 `http://localhost:8080` 运行。设 `$env:LABEL_STUDIO_API_TOKEN`（若之前用 `--user-token` 启动则用它；否则在 LS 界面 Account & Settings 取）。

Run（PowerShell `$env:PYTHONIOENCODING="utf-8"`、`$env:PYTHONPATH=<项目根>`）：

```python
import asyncio, os
from deeptutor.tools.label_studio_tool import LabelStudioCreateProjectTool, LabelStudioImportTool, LabelStudioCheckTool

async def main():
    # 1. 建项目
    r1 = await LabelStudioCreateProjectTool().execute(title="spike-import", labels='["car","person"]', task_type="bbox")
    print("建项目:", r1.success, r1.metadata.get("project_id"))
    pid = r1.metadata.get("project_id")
    # 2. 导入（图片路径用 LS 能访问的）
    r2 = await LabelStudioImportTool().execute(project_id=pid, tasks='[{"data":{"image":"/data/upload/x.jpg"}}]')
    print("导入:", r2.success, r2.content)

asyncio.run(main())
```

Expected: 建项目成功（有 project_id），导入成功（task_count=1）。若图片路径 LS 无法访问，仅验证导入 API 返回 task_count 即可（图片显示属存储配置，后续处理）。

- [ ] **Step 2: 收尾**

冒烟通过即完成 Phase 1。自建标注台/卡片跳转/拟人化为后续 Phase。
