# E3 L 部分实现计划：专家委派进度事件（"专家 X 分析中"）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `delegate_to_expert` 运行时把"专家 X 分析中"进度实时转发到主 StreamBus，前端 Trace 面板展示专家正在工作；验证多专家并行 dispatch 已生效。

**Architecture:** 复用现有 `_retrieve_trace_metadata` 事件通道——pipeline 的 `retrieve_meta_factory` 对 `delegate_to_expert` 返回 trace meta，使 `execute_tool_call` 给工具注入 `event_sink`；delegate 工具在专家 AgentLoop 运行前后通过 `event_sink` 发中文进度。并行已由 `dispatch_tool_calls` 的 `asyncio.gather`（`MAX_PARALLEL_TOOL_CALLS=8`）天然实现——E3 M 部分已把单轮 delegate 数截到 ≤2，本轮只补测试证明并行。

**Tech Stack:** Python 3.11+ asyncio / pytest（`@pytest.mark.asyncio`）/ ruff。前端（可选微调）TypeScript / TracePanels.tsx。

---

## 背景（已核实）

- `agentic_pipeline.py:_retrieve_trace_metadata`（L1085-1124）已为 `rag` / `imagegen` / `videogen` / `consult_subagent` 返回 trace meta；`execute_tool_call`（`tool_dispatch.py:347-376`）在 `retrieve_meta is not None` 时给工具注入 `event_sink`（`_event_sink`），工具调 `await event_sink("tool_log", "…")` → 主 bus `progress` 事件 → 前端 TracePanels 显示 dim 进度行（`TracePanels.tsx:996-1004`）。**`delegate_to_expert` 目前不在其中 → 专家运行期间前端无任何反馈。**
- `delegate_expert_tool.py:execute(**kwargs)`：主路径在**独立** `StreamBus` 上跑专家 AgentLoop（隔离设计，不改），`event_sink` 会作为 `**kwargs` 之一传入（`tool_dispatch.py:378-381` `registry.execute(tool_name, event_sink=..., **tool_args)`，`_resolve_request` 透传全部 kwargs → `tool.execute(**resolved_kwargs)`）。
- 并行：`dispatch_tool_calls` L179 `asyncio.gather(...)` 并行执行一批 tool_calls；M 部分 `_MAX_DELEGATE_PER_ROUND=2` 已截断。单轮 2 个 delegate 并行 = 天然支持。

## 任务分解

### Task 1: 后端——`_retrieve_trace_metadata` 为 delegate 注入 trace meta

**Files:**
- Modify: `deeptutor/agents/chat/agentic_pipeline.py:1117-1123`（在 `consult_subagent` 分支后加 `delegate_to_expert` 分支）
- Test: `tests/agents/chat/test_agentic_pipeline_dangling.py`（或就近新测试）

- [ ] **Step 1: 写失败测试**——`_retrieve_trace_metadata` 对 delegate 返回 meta、含 `call_kind="subagent_delegate"`，对普通工具仍返回 None

在 `tests/agents/chat/test_agentic_pipeline_dangling.py` 末尾追加：

```python
from deeptutor.core.context import UnifiedContext


def test_retrieve_trace_metadata_delegate_expert() -> None:
    pipeline = _pipeline()  # 复用本文件顶部既有 _pipeline() helper
    ctx = UnifiedContext(session_id="s1", user_message="评测")
    meta = pipeline._retrieve_trace_metadata(
        {"trace_id": "x"},
        context=ctx,
        tool_name="delegate_to_expert",
        tool_args={"expert_id": "grading_expert", "brief": "评测"},
    )
    assert meta is not None
    assert meta.get("call_kind") == "subagent_delegate"
    assert "grading_expert" in str(meta.get("query") or "")

    plain = pipeline._retrieve_trace_metadata(
        {"trace_id": "x"},
        context=ctx,
        tool_name="annotation_check",
        tool_args={},
    )
    assert plain is None
```

- [ ] **Step 2: 运行确认失败**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/agents/chat/test_agentic_pipeline_dangling.py -q
```

Expected: FAIL（`meta is None`）。

- [ ] **Step 3: 实现**——在 `agentic_pipeline.py:1123` 后加：

```python
        # delegate_to_expert runs an isolated expert AgentLoop that can take
        # many rounds: wiring retrieve_meta gives it an event_sink so the tool
        # can stream "专家 X 分析中…" progress to the client (and keeps the
        # idle-timeout watchdog fed during a long expert run).
        if tool_name == "delegate_to_expert":
            return derive_trace_metadata(
                tool_meta,
                label=self._t("labels.tool_call", default="Tool call"),
                call_kind="subagent_delegate",
                query=str(tool_args.get("expert_id", "") or ""),
            )
```

- [ ] **Step 4: 运行确认通过**

```
python -m pytest tests/agents/chat/test_agentic_pipeline_dangling.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add deeptutor/agents/chat/agentic_pipeline.py tests/agents/chat/test_agentic_pipeline_dangling.py
git commit -m "feat: delegate_to_expert 接入 retrieve 进度通道 (E3 L)"
```

---

### Task 2: 后端——delegate 工具运行前后发"专家 X 分析中"进度

**Files:**
- Modify: `deeptutor/tools/delegate_expert_tool.py:170-217`（主路径；fallback 也发）
- Test: `tests/tools/test_delegate_expert_tool.py`

- [ ] **Step 1: 写失败测试**——execute 收到 `event_sink` 后在 pipeline 运行前后调用

在 `tests/tools/test_delegate_expert_tool.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_delegate_emits_progress_via_event_sink(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_event_sink(event_type: str, message: str = "", **kwargs):
        calls.append((event_type, message))

    async def fake_run(self, context, stream):
        await asyncio.sleep(0.01)

    monkeypatch.setattr(AgenticChatPipeline, "run", fake_run)

    tool = DelegateExpertTool()
    result = await tool.execute(
        expert_id="grading_expert",
        brief="评测标注",
        task_data='{"f1": 0.83}',
        event_sink=fake_event_sink,
    )

    assert result.success is True
    # 运行中 + 完成 至少两条进度
    assert len(calls) >= 2, f"expected >=2 progress calls, got {calls}"
    running_msgs = [m for _, m in calls if "分析中" in m or "运行" in m]
    done_msgs = [m for _, m in calls if "完成" in m]
    assert running_msgs, f"missing running progress: {calls}"
    assert done_msgs, f"missing done progress: {calls}"
    assert any("grading_expert" in m for _, m in calls)


@pytest.mark.asyncio
async def test_delegate_no_event_sink_still_works(monkeypatch):
    async def fake_run(self, context, stream):
        await asyncio.sleep(0.01)

    monkeypatch.setattr(AgenticChatPipeline, "run", fake_run)
    tool = DelegateExpertTool()
    result = await tool.execute(expert_id="grading_expert", brief="评测标注")
    assert result.success is True
```

- [ ] **Step 2: 运行确认失败**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/tools/test_delegate_expert_tool.py -q
```

Expected: FAIL（现有实现不读 `event_sink`，无进度）。

- [ ] **Step 3: 实现**——修改 `delegate_expert_tool.py`：

在 `execute` 内、`system, user = _build_messages(...)` 之后加：

```python
        event_sink = kwargs.get("event_sink")

        async def _report(stage_text: str) -> None:
            if event_sink is None:
                return
            try:
                await event_sink("tool_log", f"专家 {expert_id} {stage_text}…")
            except Exception:
                logger.debug("delegate progress event_sink failed", exc_info=True)
```

主路径 `try:` 内、`pipeline = AgenticChatPipeline(...)` 之前：

```python
            await _report("分析中")
```

主路径正常返回前（`content = f"专家 {expert_id} 结论：..."` 之前）：

```python
            await _report("分析完成")
```

fallback `except Exception as exc:` 分支内、`from deeptutor.services.llm import complete` 之前：

```python
            await _report("分析完成（降级）")
```

- [ ] **Step 4: 运行确认通过**

```
python -m pytest tests/tools/test_delegate_expert_tool.py -q
```

Expected: PASS（含既有 pipeline/fallback/timeout 测试）。

- [ ] **Step 5: Commit**

```bash
git add deeptutor/tools/delegate_expert_tool.py tests/tools/test_delegate_expert_tool.py
git commit -m "feat: delegate 运行中/完成进度转发 (E3 L)"
```

---

### Task 3: 验证——单轮多专家并行 dispatch

**Files:**
- Test: `tests/core/agentic/test_tool_dispatch_events.py`（既有 dispatch 事件测试文件）

并行由 `dispatch_tool_calls` 的 `asyncio.gather`（L179）天然提供；M 部分 `test_loop_keeps_two_delegates` 已锁"两个 delegate 都 dispatch"，但未证**同时运行**。本任务用阻塞 registry 证明同一批内两个 delegate 的 execute 重叠执行。

- [ ] **Step 1: 写测试**——两个工具同时运行（阻塞一个，另一个在其等待期内完成）

在 `tests/core/agentic/test_tool_dispatch_events.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_parallel_tool_calls_overlap() -> None:
    import asyncio

    overlap: list[str] = []
    release = asyncio.Event()

    class _SlowRegistry:
        async def execute(self, name: str, **kwargs):
            if name == "blocker":
                # 通知主测试"blocker 已开始"，然后等 release
                overlap.append("blocker-start")
                await release.wait()
                overlap.append("blocker-end")
                return ToolResult(content="blocked done", success=True)
            # delegate 模拟：在 blocker 等待期间运行完成
            overlap.append("fast-run")
            return ToolResult(content="fast done", success=True)

    async with asyncio.timeout(2.0):
        outcome = await dispatch_tool_calls(
            tool_calls=[
                {"id": "b1", "name": "blocker", "arguments": "{}"},
                {"id": "f1", "name": "fast", "arguments": "{}"},
            ],
            context=UnifiedContext(session_id="s1", user_message="hi"),
            stream=StreamBus(),
            source="chat",
            stage="responding",
            iteration_index=0,
            registry=_SlowRegistry(),
        )
        assert "blocker-start" in overlap, "blocker must start"
        assert "fast-run" in overlap, "fast tool must run while blocker waits"
        release.set()

    results = {m["name"] for m in outcome.tool_messages}
    assert results == {"blocker", "fast"}
```

> 说明：`assert "fast-run" in overlap` 成立的前提是 gather 并发——若串行，fast 会等到 blocker 结束才跑（deadlock 由 timeout 防住）。这正是 L 部分要锁的"并行委派"。

- [ ] **Step 2: 运行确认通过（先跑一次看是否已是行为）**

```
$env:PYTHONIOENCODING="utf-8"; python -m pytest tests/core/agentic/test_tool_dispatch_events.py -q
```

Expected: PASS（并行已是现状，测试作行为锁定）。

- [ ] **Step 3: Commit**

```bash
git add tests/core/agentic/test_tool_dispatch_events.py
git commit -m "test: dispatch 并行执行行为锁定 (E3 L)"
```

---

### Task 4: 前端微调（可选但推荐）——`describeToolCall` 为 delegate 显示中文标题

**Files:**
- Modify: `web/components/chat/home/TracePanels.tsx:159-352`（`describeToolCall` 的 `switch` 加 `delegate_to_expert` case）
- Verify: `cd web && npx tsc --noEmit`

- [ ] **Step 1: 加 case**——在 `describeToolCall` 的 `switch` 中、任一工具 case 后加：

```tsx
    case "delegate_to_expert":
      return {
        Icon: ToolMark,
        verb: t("Delegating to expert"),
        chip: str(a.expert_id) || null,
        mono: false,
      };
```

（i18n key 若存在中文译文则自动中文化；无译文时英文兜底。`ToolMark`、`str`、`clip`、`t` 均已在函数作用域。）

- [ ] **Step 2: 验证 tsc**

```
cd web; $env:HTTP_PROXY=""; $env:HTTPS_PROXY=""; npx tsc --noEmit
```

Expected: 无新错误。

- [ ] **Step 3: Commit**

```bash
git add web/components/chat/home/TracePanels.tsx
git commit -m "feat: 前端 delegate_to_expert 委派标题 (E3 L)"
```

---

## 验证
- `python -m pytest tests/tools/test_delegate_expert_tool.py tests/agents/chat/test_agentic_pipeline_dangling.py tests/agents/chat/test_agent_loop.py -q` 全过
- 回归：`python -m pytest tests/agents/chat/ tests/tools/ -q`（允许预存在 GBK/可选依赖失败）
- `ruff check deeptutor/agents/chat/agentic_pipeline.py deeptutor/tools/delegate_expert_tool.py`
- `cd web && npx tsc --noEmit`

## 提交（仅 commit，不 push）
- 按 Task 拆 3-4 个 commit（均 `E3 L` 后缀），大版本完成后等用户指示统一 push
