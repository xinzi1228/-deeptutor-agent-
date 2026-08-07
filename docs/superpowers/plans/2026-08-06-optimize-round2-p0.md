# 第二轮优化 P0 实现计划：O1 记忆路由 Fallback + O5 专家写权限收敛

> 依据：`docs/superpowers/specs/2026-08-06-optimize-round2-design.md` O1/O5。TDD，后端可控，仅 commit 不 push。

## O1 记忆路由 Fallback

### 设计
`store.read_bucket(bucket, *, fallback=True)`：当前区 L2 无 `.md`（无内容）时自动回退读全局 L2 根 + L3。返回 str 保持兼容（现有 API `GET /buckets/{name}` 和测试用 content 字符串）。
- fallback 触发时内容头部加一行来源说明（中文）：`（当前记忆区暂无内容，已回退到全局记忆）`
- `fallback=False` 保持严格区隔离（供需要强制区隔离的调用）

### 改动
1. `deeptutor/services/memory/store.py` `read_bucket`：
   - 加 `*, fallback: bool = True` 参数
   - 先读 `L2/<bucket>/*.md` + L3；若区 L2 无 .md 文件且 fallback=True → 追加读全局 `L2/*.md`（根目录），内容头部加回退说明
   - L3 全局始终包含
2. `deeptutor/tools/builtin/` 下 ReadMemoryTool（找到其文件）：`bucket` 参数透传 `fallback` 参数（默认 True），description 注明"当前区无内容时自动回退全局"
3. 测试 `tests/services/memory/test_bucket_paths.py`（或新建 test）：
   - 区 A 无 .md，全局 L2 有 chat.md → read_bucket("A") 含全局内容 + 含"回退"说明
   - 区 A 有 .md → read_bucket("A") 不含全局根内容、无回退说明
   - fallback=False 区 A 空 → 返回"该记忆区暂无内容"且不含全局内容

## O5 专家写权限收敛

### 设计
`delegate_expert_tool.py` `EXPERT_TOOL_WHITELISTS` 全部移除 `write_learning_record`（学习记录只由总控落盘）；`log_decision` 保留给审计类专家（grading_expert / report_analyst / session_steward），其余移除。

### 改动
1. `delegate_expert_tool.py` 白名单：
   - learning_planner: 移除 write_learning_record
   - task_guide: 移除 write_learning_record
   - grading_expert: 移除 write_learning_record（保留 log_decision）
   - report_analyst: 保留 log_decision（本就无 write）
   - session_steward: 移除 write_learning_record（保留 log_decision）
   - struggle_detective: 无变化
2. `get_definition` description 补一句：专家不直接写学习记录，结论由总控统一落盘。
3. PERSONA 源文件 `deeptutor/services/persona/presets/annotation-coach/PERSONA.md` 总控委派节补：委派专家不写学习记录，收到结论后由你自己 write_learning_record 落盘。**同步运行时副本**（`data/user/workspace/personas/annotation-coach/PERSONA.md`，SHA 校验，不 git add）。
4. 测试 `tests/tools/test_delegate_expert_tool.py`：
   - `test_whitelist_per_expert` 增强：断言所有白名单**不含** write_learning_record；log_decision 仅在 {grading_expert, report_analyst, session_steward} 白名单中
   - 回归现有 11 测试（isolates_context 断言 banned 6，仍过）

## 验证
- `python -m pytest tests/services/memory/test_bucket_paths.py tests/tools/test_delegate_expert_tool.py -v` 全过
- 回归：`python -m pytest tests/services/memory/consolidator/modes/test_bucket_l2.py tests/api/test_memory_buckets.py tests/api/test_memory_resolver.py -q`
- `ruff check deeptutor/services/memory/store.py deeptutor/tools/delegate_expert_tool.py`

## 提交（仅 commit）
- `feat: read_bucket 路由 fallback (当前区空时回退全局记忆)`
- `feat: delegate 专家移除 write_learning_record (学习记录只由总控落盘)`
