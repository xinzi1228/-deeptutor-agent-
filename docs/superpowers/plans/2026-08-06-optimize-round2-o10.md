# 第二轮优化 P1 实现计划：O10 记忆渐进式加载（概览优先）

> 依据：`docs/superpowers/specs/2026-08-06-optimize-round2-design.md` O10（Bloom logging.md 渐进式加载）。MVP：新增 `bucket_overview`（结构化概览：每区条目数 + 首行预览 + 来源判定），ReadMemoryTool 加 `overview_only` 参数——Coach 先概览再决定是否精读全文，避免每次全量塞 context。**兼容：read_bucket 返回 str 不变。**

## 现状
- `store.read_bucket(bucket, *, fallback=True) -> str`（O1 已加 fallback）。
- `ReadMemoryTool`（`deeptutor/tools/builtin/__init__.py` L780）：bucket + fallback 参数，调 read_bucket。
- store.py 已 import document parse（delete_entry 用 `document.parse`）。

## 改动

### 1. `deeptutor/services/memory/store.py` 新增 `bucket_overview`
```python
def bucket_overview(self, bucket: str, *, fallback: bool = True) -> dict:
    """结构化概览：source=bucket|fallback|empty，surfaces=[{surface, entries, preview}]，l3_slots。"""
```
- 扫描 `paths.buckets_dir()/bucket/*.md`（同 read_bucket 逻辑）：每文件 `document.parse(text).all_entries()` 计数 + `preview`=正文首行（strip 后取前 80 字）
- 区空且 fallback=True → 读全局 `paths.l2_dir()/*.md` 同格式，source="fallback"
- 区有文件 → source="bucket"；都无 → source="empty"
- `l3_slots` = 非空 L3 slot 数
- 返回 `{"bucket": name, "source": ..., "surfaces": [...], "l3_slots": n}`

### 2. `ReadMemoryTool`（builtin/__init__.py）加 `overview_only: bool = False`
- `overview_only=True` 且传 bucket → 调 `bucket_overview`，格式化为可读文本返回（每 surface 一行：`[surface] 3 条 — 首行预览...` + 来源说明），metadata 带 `overview: true`
- 否则保持现状（全文）
- description 补 overview_only 说明

### 3. 测试 `tests/services/memory/test_read_bucket_fallback.py`（或 test_bucket_paths.py）加 3 用例 + ReadMemoryTool overview 1 用例
- `test_overview_bucket_source`: seed `L2/标注学习/chat.md`（含 ≥2 条目）→ overview source=="bucket", surfaces 含 {surface:"chat", entries≥2}, preview 非空
- `test_overview_fallback_source`: 区空 + 全局 `L2/chat.md` → source=="fallback", surfaces 含 chat
- `test_overview_empty_source`: 区空 + 无全局 → source=="empty", surfaces==[]
- `test_read_memory_overview_only`: ReadMemoryTool(overview_only=True, bucket="标注学习") → content 含 "[chat]" 与条目数，metadata overview==true

（fixture 复用 monkeypatch paths.memory_root；条目用 document.Document 构造或直接写 md 文本，参照 test_bucket_paths 现有 seed 方式）

## 验证
- `python -m pytest tests/services/memory/test_bucket_paths.py tests/services/memory/test_read_bucket_fallback.py -v` 全过
- 回归：`python -m pytest tests/services/memory/consolidator/modes/test_bucket_l2.py tests/api/test_memory_buckets.py tests/api/test_memory_resolver.py tests/tools/test_render_ui_tool.py tests/tools/test_delegate_expert_tool.py -q`
- `ruff check deeptutor/services/memory/store.py deeptutor/tools/builtin/__init__.py`

## 提交（仅 commit）
- `feat: 记忆渐进式加载 — bucket_overview 概览 + ReadMemoryTool overview_only`
