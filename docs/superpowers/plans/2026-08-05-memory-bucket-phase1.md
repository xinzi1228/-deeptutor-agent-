# 议题①② 记忆分区 Phase 1（读取隔离 + bucket 路径）— 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给记忆系统加 `bucket`（记忆区）维度：路径层支持 `L2/<bucket>/<surface>.md`，store 提供 `read_bucket`（读某区 L2 + 全局 L3），`read_memory` 工具支持按 bucket 过滤读取。**Phase 1 = 读取隔离**（防污染第一步：读不到别的区）。写入分区（consolidator 按 bucket 聚合）+ API CRUD + 前端管理为后续 Phase。

**Architecture:** `paths.l2_file(surface, bucket=None)` 向后兼容；`store.read_bucket(bucket)` 读该区所有 surface 的 L2 md + 全局 L3（profile/preferences 全局共享，符合设计）；`read_memory` 加可选 `bucket` 参数。改动小、纯文件、可 TDD。

**Tech Stack:** Python 3.11+ / pytest / pathlib

**依赖设计文档:** `docs/superpowers/specs/2026-08-05-memory-partition-design.md`

---

## File Structure

- Modify: `deeptutor/services/memory/paths.py` — `l2_file(surface, bucket=None)` + `list_buckets()`
- Modify: `deeptutor/services/memory/store.py` — `read_bucket(bucket)` 方法
- Modify: `deeptutor/tools/builtin/__init__.py` — `ReadMemoryTool` 加 `bucket` 参数
- Create: `tests/services/memory/test_bucket_paths.py` — paths/store/工具 bucket 测试

---

### Task 1: paths.py bucket 路径支持

**Files:**
- Modify: `deeptutor/services/memory/paths.py`
- Test: `tests/services/memory/test_bucket_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/services/memory/test_bucket_paths.py
import pytest

from deeptutor.services.memory import paths


def test_l2_file_no_bucket_backward_compatible(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    p = paths.l2_file("chat")
    assert p == tmp_path / "L2" / "chat.md"


def test_l2_file_with_bucket(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    p = paths.l2_file("chat", bucket="标注学习")
    assert p == tmp_path / "L2" / "标注学习" / "chat.md"


def test_list_buckets(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    bdir = tmp_path / "L2"
    (bdir / "标注学习").mkdir(parents=True)
    (bdir / "Python学习").mkdir()
    (bdir / "chat.md").write_text("x", encoding="utf-8")
    assert paths.list_buckets() == ["Python学习", "标注学习"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/memory/test_bucket_paths.py -v`
Expected: FAIL — `l2_file()` doesn't accept `bucket`, `list_buckets` missing

- [ ] **Step 3: Write implementation**

Modify `deeptutor/services/memory/paths.py`:

```python
def l2_file(surface: Surface, bucket: str | None = None) -> Path:
    """L2 summary file for a surface, optionally scoped to a memory bucket."""
    if bucket:
        return l2_dir() / bucket / f"{surface}.md"
    return l2_dir() / f"{surface}.md"


def list_buckets() -> list[str]:
    """Existing memory bucket names (subdirectories of L2)."""
    d = l2_dir()
    if not d.exists():
        return []
    return sorted(
        entry.name
        for entry in d.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/memory/test_bucket_paths.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/memory/paths.py tests/services/memory/test_bucket_paths.py
git commit -m "feat: memory paths 支持 bucket 子目录 (L2/<bucket>/<surface>.md)"
```

---

### Task 2: store.read_bucket（读某区 L2 + 全局 L3）

**Files:**
- Modify: `deeptutor/services/memory/store.py`
- Test: `tests/services/memory/test_bucket_paths.py`（追加）

- [ ] **Step 1: Write the failing test**

```python
# tests/services/memory/test_bucket_paths.py (append)
import asyncio
from deeptutor.services.memory.store import MemoryStore, get_memory_store


def test_read_bucket_returns_bucket_l2_and_global_l3(monkeypatch, tmp_path):
    bdir = tmp_path / "L2" / "标注学习"
    bdir.mkdir(parents=True)
    (bdir / "chat.md").write_text("# 标注学习\n遮挡目标处理已掌握", encoding="utf-8")
    l3 = tmp_path / "L3"
    l3.mkdir()
    (l3 / "profile.md").write_text("喜欢简明讲解", encoding="utf-8")

    async def fake_path():
        return tmp_path

    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    store = MemoryStore()
    text = store.read_bucket("标注学习")
    assert "遮挡目标处理" in text
    assert "喜欢简明讲解" in text  # 全局 L3 共享


def test_read_bucket_empty_returns_placeholder(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    store = MemoryStore()
    assert "暂无内容" in store.read_bucket("不存在的区")
```

（注意：如果 `MemoryStore()` 构造需要参数或依赖，用 `get_memory_store()` 并在测试中 monkeypatch `paths.memory_root`。实际以 store 实现为准——若 `read_bucket` 只依赖 `paths.memory_root()` 则可直接构造。若构造复杂，改为调用 `get_memory_store()`。）

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/services/memory/test_bucket_paths.py -q`
Expected: FAIL — `read_bucket` missing

- [ ] **Step 3: Write implementation**

Add to `deeptutor/services/memory/store.py` (MemoryStore class, near `read_l3_concat`):

```python
def read_bucket(self, bucket: str) -> str:
    """Read a memory bucket: its L2 summaries across surfaces + global L3."""
    parts: list[str] = []
    bdir = paths.buckets_dir() / bucket
    if bdir.is_dir():
        for md in sorted(bdir.glob("*.md")):
            body = md.read_text(encoding="utf-8").strip()
            if body:
                parts.append(f"## [{md.stem}]\n{body}")
    for slot in paths.L3_SLOTS:
        body = self.read_raw("L3", slot).strip()
        if body:
            parts.append(body)
    if not parts:
        return "（该记忆区暂无内容）\n"
    return "\n\n---\n\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/services/memory/test_bucket_paths.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deeptutor/services/memory/store.py tests/services/memory/test_bucket_paths.py
git commit -m "feat: MemoryStore.read_bucket 读记忆区 (该区L2+全局L3)"
```

---

### Task 3: read_memory 工具支持 bucket 参数

**Files:**
- Modify: `deeptutor/tools/builtin/__init__.py`（`ReadMemoryTool`）

- [ ] **Step 1: 改 ReadMemoryTool（在 `name="read_memory"` 的工具类里）**

`get_definition` 的 parameters 从 `[]` 改为：

```python
parameters=[
    ToolParameter(
        name="bucket",
        type="string",
        description="可选记忆区名，按区读取（如 标注学习）；不传则读全局记忆。",
        required=False,
    ),
],
```

`execute` 改为：

```python
async def execute(self, **kwargs: Any) -> ToolResult:
    from deeptutor.services.memory import get_memory_store

    bucket = str(kwargs.get("bucket") or "").strip()
    if bucket:
        text = get_memory_store().read_bucket(bucket)
    else:
        text = get_memory_store().read_l3_concat()
    return ToolResult(
        content=text,
        metadata={"char_count": len(text), "bucket": bucket or None},
    )
```

（先读 `ReadMemoryTool` 现有实现，确认 `_PromptHintsMixin` 等结构后按同风格修改。）

- [ ] **Step 2: 验证 import + 工具定义**

Run:
```powershell
python -c "from deeptutor.tools.builtin import ReadMemoryTool; d=ReadMemoryTool().get_definition(); print([p.name for p in d.parameters])"
```
Expected: `['bucket']`

- [ ] **Step 3: Commit**

```bash
git add deeptutor/tools/builtin/__init__.py
git commit -m "feat: read_memory 支持 bucket 参数 (按记忆区读取)"
```

---

### Task 4: 冒烟验证

- [ ] **Step 1: 真实冒烟（构造记忆区 + 读取隔离验证）**

Run（PowerShell `$env:PYTHONIOENCODING="utf-8"`、`$env:PYTHONPATH=<项目根>`）：

```python
import asyncio
from deeptutor.services.memory import get_memory_store
from deeptutor.services.memory import paths

async def main():
    # 造一个测试记忆区
    bdir = paths.l2_dir() / "冒烟测试区"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "chat.md").write_text("# 冒烟测试区\n标注学习进度: 已完成 3 个 bbox 任务", encoding="utf-8")
    store = get_memory_store()
    text = store.read_bucket("冒烟测试区")
    print("读记忆区:", "标注学习进度" in text)
    # 读取隔离: 另一个区读不到
    text2 = store.read_bucket("另一个区")
    print("不存在区:", "暂无内容" in text2)

asyncio.run(main())
```

Expected: `读记忆区: True`、`不存在区: True`

- [ ] **Step 2: 跑回归 + 收尾**

Run: `python -m pytest tests/services/memory/ tests/tools/test_route_input.py tests/tools/test_verify_output_tool.py tests/tools/test_kb_search_tool.py -q`
Expected: 全部 PASS（记忆改动不破坏现有）

冒烟通过即完成 Phase 1。consolidator 按 bucket 聚合写入（Phase 2）与 API/前端（Phase 3）另立计划。
