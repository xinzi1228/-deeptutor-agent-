# 议题⑦ Phase 2 实现计划：delegate_to_expert 升级为独立 AgentLoop + 受限工具

> 目标：把 Phase 1 的单次隔离 LLM 调用升级为**独立 AgentLoop**——专家持受限工具白名单（专人专事）跑 ≤5 轮 agentic 循环，仍保持上下文隔离（brief 自包含，不继承总控历史）。复用 `AgenticChatPipeline.run()`，**零 pipeline 改动**（explore 已确认机制：`allowed_builtin_tools` → `builtin_whitelist` 过滤 always_on）。

## 现状
- `delegate_expert_tool.py` Phase 1：`complete(user, system_prompt=专家卡)` 单次调用，无工具。
- pipeline 走 `_build_openai_client()` + `AgentLoop`，**不调用** `services.llm.complete()`（测试需换 mock 路径）。
- 隔离机制已具备：`UnifiedContext(conversation_history=[], allowed_builtin_tools=WHITELIST, enabled_tools=[], persona_context=专家卡)`。

## 改动（仅 `deeptutor/tools/delegate_expert_tool.py`）

### 1. 专家→工具白名单映射
```python
EXPERT_TOOL_WHITELISTS: dict[str, tuple[str, ...]] = {
    "learning_planner": ("competency_map", "ability_radar", "get_annotation_task", "kb_search", "graph_query", "write_learning_record", "render_ui"),
    "task_guide": ("get_annotation_task", "kb_search", "annotation_check", "render_ui", "write_learning_record"),
    "grading_expert": ("annotation_check", "get_annotation_task", "kb_search", "graph_query", "write_learning_record", "log_decision", "render_ui"),
    "struggle_detective": ("struggle_detect", "ability_radar", "get_annotation_task", "kb_search", "graph_query", "render_ui"),
    "report_analyst": ("competency_map", "ability_radar", "graph_query", "kb_search", "log_decision", "render_ui"),
    "session_steward": ("write_learning_record", "log_decision", "get_annotation_task", "graph_query", "render_ui"),
}
```
统一排除（任何白名单都不含，防递归/阻塞/污染）：`delegate_to_expert`, `ask_user`, `write_memory`, `web_fetch`, `github`, `cron`。

### 2. `execute` 主路径（保持参数接口 expert_id/brief/task_data 不变）
- 校验同 Phase 1（expert_id ∈ EXPERT_IDS、brief 非空、专家卡存在）。
- 构造新鲜 `UnifiedContext`：
  ```python
  ctx = UnifiedContext(
      session_id=f"delegate-{expert_id}-{uuid.uuid4().hex[:8]}",
      user_message=f"委派任务：{brief}\n\n任务数据：{task_data}\n\n请输出你的结论（简洁、可被总控直接采用）。",
      conversation_history=[],            # 绝不继承总控历史（上下文隔离）
      enabled_tools=[],                    # 杀掉用户开关层
      allowed_builtin_tools=list(EXPERT_TOOL_WHITELISTS[expert_id]),  # 受限白名单
      language="zh",
      persona_context=f"{card}\n\n你现在只处理这一次委派任务，不进入完整对话。按你的专家规则输出结构化结论给总控。",
      metadata={"source": "delegate", "expert": expert_id, "_min_loop_rounds": 3},
  )
  ```
- `pipeline = AgenticChatPipeline(language="zh", max_rounds=5, temperature=0.2, max_tokens=2000)`（懒加载 import 防循环）。
- `bus = StreamBus()`；`await pipeline.run(ctx, bus)`；收集 `StreamEventType.RESULT` 事件的 `metadata.response` 作为最终文本（参考 `agent_loop.py:209-220` / `capability_result.py`）。
- `await bus.close()`；返回 `ToolResult(content=f"专家 {expert_id} 结论：\n{final}", metadata={"delegate": {"expert": expert_id, "result": final}})`。
- **fallback**：`AgenticChatPipeline` 构造/run 异常时回退 Phase 1 单次 `complete()`（保证工具永远可用）；fallback 路径不吞错误，返回 success=False 提示。

### 3. `get_definition` description
- 更新说明："专家以独立 AgentLoop 运行（≤5 轮），挂受限工具白名单（专人专事），不继承对话历史。"

## 测试 `tests/tools/test_delegate_expert_tool.py`
- **保留** Phase 1 的 `complete` mock 测试（fallback 路径仍覆盖）。
- **新增 pipeline 路径测试**（复用 `tests/agents/chat/test_agent_loop.py` 的 `_ScriptedChatClient` 模式）：
  1. `test_delegate_runs_pipeline`：mock `_build_openai_client` 返回 scripted client（先 yield 工具调用 → annotation_check 结果 chunk，再 yield 最终文本），monkeypatch `_compose_enabled_tools` 返回白名单工具；断言 ToolResult.success 且 content 含专家结论。
  2. `test_delegate_isolates_context`：monkeypatch `AgenticChatPipeline.run` 捕获收到的 context；断言 `ctx.conversation_history == []`、`ctx.allowed_builtin_tools` 不含 delegate_to_expert/ask_user/write_memory、`ctx.persona_context` 含专家卡标题、`ctx.metadata["source"] == "delegate"`。
  3. `test_whitelist_per_expert`：断言 EXPERT_TOOL_WHITELISTS 每个值都是 always_on 子集且不含排除名单。
  4. `test_fallback_to_complete`：monkeypatch `AgenticChatPipeline` 构造抛错 → 走 fallback complete() → 返回结果。
- 异步测试需 `@pytest.mark.asyncio`（STRICT 模式）。

## 验证
- `python -m pytest tests/tools/test_delegate_expert_tool.py -v`（Phase1 旧 + 新 4 全过）
- 回归：`python -m pytest tests/tools/test_render_ui_tool.py tests/tools/test_route_input.py tests/tools/test_verify_output_tool.py tests/tools/test_kb_search_tool.py tests/tools/test_delegate_expert_tool.py -q`
- `ruff check deeptutor/tools/delegate_expert_tool.py`
- 冒烟（真实 LLM）：`python -m pytest tests/tools/test_delegate_expert_tool.py -k pipeline` 通过 + 可选一次真实 delegate grading_expert 冒烟。

## PERSONA（源 + 运行时副本同步）
- `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` 总控委派节补充：delegate_to_expert 会以独立 AgentLoop 运行并挂受限工具白名单，委派时 brief 要自包含。
- **同步**运行时副本 `data/user/workspace/personas/annotation-coach/PERSONA.md`（SHA 校验一致）。

## 提交（仅 commit，大版本结束统一 push）
- `feat: delegate_to_expert 升级独立 AgentLoop + 专家受限工具白名单`
