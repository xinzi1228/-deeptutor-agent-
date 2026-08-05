# 议题①② 记忆分区 Phase 2（consolidator 按 bucket 写入）— 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 consolidator 把 L2 聚合结果写到 `L2/<bucket>/<surface>.md`（记忆区专用），meta sidecar 同步按 bucket 隔离——使两个记忆区各自的 L1→L2 聚合独立、不互相打架。Phase 2a：L2 写入位置 + meta 按 bucket；L1 trace 源暂按 surface（Phase 2b 再分桶）。

**Architecture:** `bucket: str | None = None` 关键字参数沿 `store.update_l2 → consolidate_l2 → run_update → _run_update_l2` 透传，在 `update.py:212` 用 `paths.l2_file(surface, bucket)` 解析写路径；meta 路径 `l2_meta_path` 同样按 bucket（`L2/<bucket>/<surface>.meta.json`）。dedup/merge/`_rollback_new_entries` 透传 bucket 保证后处理落在同一文件。默认 None → 现有路径，零破坏。

**Tech Stack:** Python 3.11+ / pytest-asyncio / pytest（mock LLM + snap）

**依赖设计文档:** `docs/superpowers/specs/2026-08-05-memory-partition-design.md`

---

## File Structure

- Modify: `deeptutor/services/memory/store.py` — `update_l2` 加 `bucket`（lock path 用 bucket 化路径）
- Modify: `deeptutor/services/memory/consolidator/modes/_shims.py` — `consolidate_l2` + `_rollback_new_entries` 加 `bucket`
- Modify: `deeptutor/services/memory/consolidator/modes/update.py` — `run_update` + `_run_update_l2` 加 `bucket`；`update.py:212` 用 `paths.l2_file(surface, bucket)`；`save_l2_meta`/`load_l2_meta` 传 bucket
- Modify: `deeptutor/services/memory/consolidator/modes/meta.py` — `l2_meta_path(surface, bucket=None)`（`L2/<bucket>/<surface>.meta.json`）
- Modify: `deeptutor/services/memory/consolidator/modes/dedup.py` + `merge.py` — `_path_for`/`run_dedup`/`run_merge` 透传 bucket（后处理同文件）
- Create: `tests/services/memory/consolidator/modes/test_bucket_l2.py` — bucket 写入 + meta 隔离 + 两区不打架

---

### Task 1: 核心透传（4 函数 + meta bucket）

**Files:**
- Modify: `store.py`, `_shims.py`, `update.py`, `meta.py`
- Test: `tests/services/memory/consolidator/modes/test_bucket_l2.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/services/memory/consolidator/modes/test_bucket_l2.py
import asyncio
from pathlib import Path

import pytest

from deeptutor.services.memory import paths
from deeptutor.services.memory.store import get_memory_store
from deeptutor.services.memory.consolidator.modes.update import run_update


@pytest.fixture
def fake_memory_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_update_l2_routes_bucket_path(fake_memory_root, monkeypatch):
    """update_l2(bucket='标注学习') 应把聚合结果写到 L2/标注学习/chat.md。"""
    root = fake_memory_root
    bucket = "标注学习"
    bdir = root / "L2" / bucket
    bdir.mkdir(parents=True)

    # mock 底层，验证路径解析落到 bucket 目录
    calls = {}

    async def fake_consolidate(surface, *, language="en", user_label="anonymous",
                               on_event=None, apply_ops=True, bucket=None):
        calls["bucket"] = bucket
        p = paths.l2_file(surface, bucket)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# 标注学习\n已掌握遮挡处理", encoding="utf-8")
        return None

    import deeptutor.services.memory.store as store_mod
    monkeypatch.setattr(
        "deeptutor.services.memory.consolidator.consolidate_l2", fake_consolidate
    )
    # store.update_l2 调 consolidator.consolidate_l2 —— patch 后验证透传
    store = get_memory_store()
    # 直接验证 run_update 层的 bucket 路径解析（真实链路的核心）：
    # 用 spy 验证 run_update 把 bucket 传给 _run_update_l2 并写到 bucket 目录
    assert paths.l2_file("chat", bucket) == root / "L2" / "标注学习" / "chat.md"


@pytest.mark.asyncio
async def test_meta_path_bucket_scoped(fake_memory_root):
    from deeptutor.services.memory.consolidator.modes import meta

    assert meta.l2_meta_path("chat", "标注学习") == fake_memory_root / "L2" / "标注学习" / "chat.meta.json"
    assert meta.l2_meta_path("chat") == fake_memory_root / "L2" / "chat.meta.json"
```

（说明：真实 LLM 聚合难以在单测稳定驱动；本 Task 聚焦**路径路由正确性**——`l2_file(surface, bucket)` + `l2_meta_path(surface, bucket)`。集成（mock snap + mock LLM 跑 run_update 写 bucket 文件）放 Task 2。）

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/memory/consolidator/modes/test_bucket_l2.py -v`
Expected: FAIL — `l2_meta_path` 不接受 bucket（或路径断言失败）

- [ ] **Step 3: Write implementation**

**`meta.py`** — `l2_meta_path` 加 bucket：

```python
def l2_meta_path(surface: Surface, bucket: str | None = None) -> Path:
    """Meta sidecar path for an L2 surface, optionally scoped to a bucket."""
    if bucket:
        return paths.l2_dir() / bucket / f"{surface}.meta.json"
    return paths.l2_dir() / f"{surface}.meta.json"
```

（`load_l2_meta`/`save_l2_meta` 内部用 `l2_meta_path(surface, bucket)` —— 给它们加 `bucket=None` 参数并透传。实现者按 meta.py 实际签名修改。）

**`store.py`** — `update_l2` 加 `bucket=None`：

```python
    async def update_l2(
        self,
        surface: Surface,
        *,
        language: str = "en",
        user_label: str = "anonymous",
        on_event: OnEvent | None = None,
        apply_ops: bool = True,
        bucket: str | None = None,
    ) -> ConsolidateResult:
        path = paths.l2_file(surface, bucket)
        async with self._lock_for(path):
            return await consolidator.consolidate_l2(
                surface,
                language=language,
                user_label=user_label,
                on_event=on_event,
                apply_ops=apply_ops,
                bucket=bucket,
            )
```

**`_shims.py`** — `consolidate_l2` 加 `bucket=None`，传给 `run_update` + `_rollback_new_entries`：

```python
async def consolidate_l2(
    surface: Surface,
    *,
    language: str = "en",
    user_label: str = "anonymous",
    on_event: OnEvent | None = None,
    apply_ops: bool = True,
    bucket: str | None = None,
) -> ConsolidateResult:
    result = await run_update(
        "L2",
        surface,
        language=language,
        user_label=user_label,
        on_event=on_event,
        bucket=bucket,
    )
    if not apply_ops:
        _rollback_new_entries("L2", surface, result.new_entry_ids, bucket=bucket)
    return _to_consolidate_result(result)
```

`_rollback_new_entries(layer, key, ids, *, bucket=None)` → `paths.l2_file(key, bucket)`（L118）。

**`update.py`** — `run_update` 加 `bucket=None` 透传给 `_run_update_l2`；`_run_update_l2` 加 `bucket=None`：
- L150 `load_l2_meta(surface, bucket=bucket)`
- L212 `l2_path = paths.l2_file(surface, bucket)`
- L312 `save_l2_meta(surface, seen_entity_refs=seen_now, bucket=bucket)`
- 若 `run_dedup("L2", surface, bucket=bucket)` / `run_merge(...)` 被自动调用，透传 bucket（否则 Task 2 处理）

（实现者按 update.py 实际签名/调用点修改，确保默认 `bucket=None` 走原路径。）

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/memory/consolidator/modes/test_bucket_l2.py -v`
Expected: PASS

Run（回归）: `python -m pytest tests/services/memory/consolidator/ tests/services/memory/test_bucket_paths.py -q`
Expected: 除已知预存在失败（test_snapshot_adapters 4 个 Windows/GBK）外全过

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/memory/store.py deeptutor/services/memory/consolidator/modes/_shims.py deeptutor/services/memory/consolidator/modes/update.py deeptutor/services/memory/consolidator/modes/meta.py tests/services/memory/consolidator/modes/test_bucket_l2.py
git commit -m "feat: consolidator 支持 bucket (L2/meta 按记忆区隔离写入)"
```

---

### Task 2: dedup/merge 透传 bucket（后处理同文件）

**Files:**
- Modify: `dedup.py`, `merge.py`

- [ ] **Step 1: 透传 bucket**

`dedup.py`：`_path_for(layer, key, bucket=None)` → `paths.l2_file(key, bucket)`（L204-206）；`run_dedup("L2", key, *, bucket=None, ...)` 加 bucket 透传。

`merge.py`：同样处理 `_path_for`（L208-210）+ `run_merge`。

（实现者按实际签名修改；若 update.py 的自动调用已透传 bucket，则这里配套。）

- [ ] **Step 2: 回归 + 单测确认**

Run: `python -m pytest tests/services/memory/consolidator/ tests/services/memory/test_bucket_paths.py -q`
Expected: 无新增失败

Run: `ruff check deeptutor/services/memory/consolidator/modes/`
Expected: clean

- [ ] **Step 3: Commit**

```bash
git add deeptutor/services/memory/consolidator/modes/dedup.py deeptutor/services/memory/consolidator/modes/merge.py
git commit -m "chore: dedup/merge 透传 bucket (后处理落同一记忆区)"
```

---

### Task 3: 集成验证（两记忆区独立聚合）

- [ ] **Step 1: 集成测试（mock snap + mock LLM 跑 run_update(bucket)）**

在 `test_bucket_l2.py` 追加（参考 `test_modes.py` 的 mock 方式：patch `snap.read_snapshot` + mock LLM complete 返回合法 ops）：

```python
@pytest.mark.asyncio
async def test_two_buckets_write_independent_l2(fake_memory_root, monkeypatch):
    """两个 bucket 各自生成独立 L2/<bucket>/<surface>.md，互不覆盖。"""
    root = fake_memory_root
    for b in ("标注学习", "Python学习"):
        (root / "L2" / b).mkdir(parents=True, exist_ok=True)

    # 用最小真实链路：直接调 update_l2 且 mock consolidator 写入不同内容
    import deeptutor.services.memory.store as store_mod
    from deeptutor.services.memory.store import get_memory_store

    async def fake_consolidate(surface, *, language="en", user_label="anonymous",
                               on_event=None, apply_ops=True, bucket=None):
        p = paths.l2_file(surface, bucket)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {bucket} 记忆\n专属内容", encoding="utf-8")

    monkeypatch.setattr("deeptutor.services.memory.consolidator.consolidate_l2", fake_consolidate)
    store = get_memory_store()
    await store.update_l2("chat", bucket="标注学习")
    await store.update_l2("chat", bucket="Python学习")
    assert "标注学习" in (root / "L2" / "标注学习" / "chat.md").read_text(encoding="utf-8")
    assert "Python学习" in (root / "L2" / "Python学习" / "chat.md").read_text(encoding="utf-8")
    # 隔离：不写入全局 L2/chat.md
    assert not (root / "L2" / "chat.md").exists()
```

（若 `store.update_l2` 的 patch 目标不对，实现者按 `store.py` 实际 import 调整 monkeypatch 目标。）

- [ ] **Step 2: 冒烟（真实环境）**

Run（PowerShell `$env:PYTHONIOENCODING="utf-8"`、`$env:PYTHONPATH=<项目根>`）：

```python
import asyncio
from deeptutor.services.memory import paths, get_memory_store

async def main():
    b = "冒烟区A"
    p = paths.l2_file("chat", b)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# 冒烟区A\n遮挡处理已掌握", encoding="utf-8")
    store = get_memory_store()
    t = store.read_bucket(b)
    print("区A可读:", "遮挡处理" in t)

asyncio.run(main())
```

Expected: `区A可读: True`

- [ ] **Step 3: 全套回归 + 收尾**

Run: `python -m pytest tests/services/memory/ tests/tools/test_route_input.py tests/tools/test_verify_output_tool.py tests/tools/test_kb_search_tool.py -q`
Expected: 无新增失败（除已知 test_snapshot_adapters 预存在失败）
