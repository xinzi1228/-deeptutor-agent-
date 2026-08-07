# 第二轮优化 P1 实现计划：O3 遗忘标记（stale 标记，非物理删）

> 依据：`docs/superpowers/specs/2026-08-06-optimize-round2-design.md` O3（Forgetting #19 + Mem0 expiration：过时隐藏不硬删 + safeguard）。MVP：L2 条目支持 `stale` 标记 → 读端隐藏，不物理删除；L3 preferences 永不 stale。LLM 审计自动判断留 P2，本轮提供显式 mark/unmark API。

## 现状
- `document.py`：`Entry{id, section, text, refs}`；bullet 行由 `_NEW_BULLET_RE`/`_OLD_BULLET_RE` 解析；serialize 为 ref-keyed 新格式。
- `store.read_bucket` 直接拼接文件文本；`bucket_overview` 用 `document.parse(...).all_entries()` 计数。
- `meta.py` 有 `l2_meta_path(surface, bucket)` sidecar（L2 专用；L3 用 `l3_meta_path`）。

## 设计
**stale 标记 = Entry 字段 + bullet 行尾 HTML 注释**（` <!-- stale -->`），parse/serialize 往返兼容（旧文档无标记 → stale=False）。
- 读端（read_bucket / bucket_overview）只展示**可见条目**（stale 过滤）。
- safeguard：mark 只对 L2 surface 有效；L3（含 preferences）拒绝。
- 显式 API：`store.mark_stale` / `store.unmark_stale`（Coach 或用户显式标记过时）。

## Task 1 — document.py stale 支持
- `Entry` 加 `stale: bool = False`
- `parse`：新/旧 bullet 分支，行尾含 `<!-- stale -->` → stale=True
- `serialize`：stale 条目行尾追加 ` <!-- stale -->`
- `Document.visible_entries() -> list[Entry]`（过滤 stale）
- `Document.mark_stale(entry_id) -> bool` / `unmark_stale(entry_id) -> bool`（更新字段）
- 测试 `tests/services/memory/test_document.py`：往返 preserve stale；visible_entries 过滤；mark/unmark
  - 注意：serialize→parse 往返必须保留 stale（现有往返测试仍过）

## Task 2 — store 层 stale 集成 + safeguard
- `store.mark_stale(surface, entry_id, *, bucket=None) -> bool`：仅 L2 surface；parse→mark→serialize→原子写；返回是否命中
- `store.unmark_stale(surface, entry_id, *, bucket=None) -> bool`：同上反向
- `store.read_bucket`：改为 parse 每 md → 重组可见条目（`## [{stem}]\n` + 按 section 组织 `- {text}`），stale 条目隐藏；返回 str 不变
- `store.bucket_overview`：entries 计数/预览用 `visible_entries()`
- safeguard：L3 surface 传参 → ValueError（mark/unmark 拒绝）
- 测试 `tests/services/memory/test_bucket_paths.py`：
  - mark 后 read_bucket 不含该条目文本；unmark 后恢复
  - overview entries 计数含 stale 前 / 剔除 stale 后
  - mark L3 surface → ValueError

## Task 3 — 工具/API 联动 + PERSONA + 集成验证
- `ReadMemoryTool` description 注明"过时条目已隐藏"
- 新增轻量 HTTP 端点？—— 本轮不做（Coach 通过记忆工作台人工清理），仅 store API 供测试/后续 audit 用
- PERSONA 源 + 运行时副本：记忆节补一句"过时条目可标记 stale 隐藏，不物理删除"（同步 SHA）
- 集成验证：全量相关回归 + ruff

## 验证
- `python -m pytest tests/services/memory/test_document.py tests/services/memory/test_bucket_paths.py tests/services/memory/test_read_bucket_fallback.py -v` 全过
- 回归：`python -m pytest tests/services/memory/consolidator/modes/test_bucket_l2.py tests/api/test_memory_buckets.py tests/api/test_memory_resolver.py tests/tools/test_delegate_expert_tool.py tests/tools/test_render_ui_tool.py -q`
- `ruff check deeptutor/services/memory/document.py deeptutor/services/memory/store.py deeptutor/tools/builtin/__init__.py`

## 提交（仅 commit，全部完成后统一 push）
- Task1: `feat: document 支持 stale 标记 (parse/serialize/visible_entries)`
- Task2: `feat: store mark/unmark_stale + 读端隐藏 stale + L3 safeguard`
- Task3: `docs: PERSONA 记忆节补 stale 说明`
