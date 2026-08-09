"""round2 O4：读记忆 30s 进程内缓存 + 写后失效。

Covers ``MemoryStore.read_bucket`` TTL cache:
- TTL 内重复读只一次磁盘读（不重复渲染）
- 写入后缓存失效（写后立即可见新记忆）
- TTL 过期重新读
"""

from __future__ import annotations

from pathlib import Path
import asyncio

import pytest

from deeptutor.services.memory import paths
from deeptutor.services.memory.document import Document, Entry, serialize
from deeptutor.services.memory.ids import new_entry_id


def _seed_surface(path: Path, entries: list[tuple[str, float | None]]) -> None:
    """Write an L2 surface doc where each bullet is ``(text, confidence)``."""
    doc = Document(
        title=f"{path.stem} memory",
        sections=[
            (
                "Topics",
                [
                    Entry(
                        id=new_entry_id(),
                        section="Topics",
                        text=text,
                        refs=["chat:01"],
                        confidence=conf,
                    )
                    for text, conf in entries
                ],
            )
        ],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(doc), encoding="utf-8")


@pytest.fixture
def mem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    (tmp_path / "L2").mkdir()
    return tmp_path


def _fresh_store():
    """A fresh MemoryStore instance (not the process-wide singleton)."""
    from deeptutor.services.memory.store import MemoryStore

    return MemoryStore()


def test_read_bucket_cached_within_ttl_single_disk_read(mem_root: Path, monkeypatch) -> None:
    """TTL 内重复读只产生一次磁盘读（_render_surface 只被调用一次）。"""
    from deeptutor.services.memory.store import MemoryStore

    _seed_surface(mem_root / "L2" / "标注学习" / "chat.md", [("条目一", 0.9)])
    store = _fresh_store()

    calls = {"n": 0}
    original = MemoryStore._render_surface

    def counting(self, md, budget_left, keep_entry_ids=None):
        calls["n"] += 1
        return original(self, md, budget_left, keep_entry_ids=keep_entry_ids)

    monkeypatch.setattr(MemoryStore, "_render_surface", counting)
    first = store.read_bucket("标注学习")
    second = store.read_bucket("标注学习")
    assert first == second
    assert calls["n"] == 1


def test_read_bucket_cache_invalidated_after_write(mem_root: Path) -> None:
    """写入后缓存失效：30s 内写入新记忆，下一次读立即可见。"""
    from deeptutor.services.memory.store import MemoryStore

    _seed_surface(mem_root / "L2" / "标注学习" / "chat.md", [("既有条目", 0.9)])
    store = _fresh_store()
    assert "既有条目" in store.read_bucket("标注学习")
    assert "新偏好" not in store.read_bucket("标注学习")

    report = asyncio.run(
        store.write_preference(
            op="add",
            text="新偏好",
            trace_id="chat:01HZK4AAAAAAAAAAAAAAAAAAAA",
        )
    )
    assert report.accepted
    assert "新偏好" in store.read_bucket("标注学习")


def test_read_bucket_cache_expires_after_ttl(mem_root: Path) -> None:
    """TTL 过期后重新读磁盘（缓存条目被判定过期）。"""
    from deeptutor.services.memory import read_cache
    from deeptutor.services.memory.store import MemoryStore

    _seed_surface(mem_root / "L2" / "标注学习" / "chat.md", [("第一版", 0.9)])
    store = _fresh_store()
    assert "第一版" in store.read_bucket("标注学习")

    # 直接把缓存条目时间戳拨到 TTL 之前，模拟 30s 已过。
    key = (str(paths.memory_root()), "标注学习", True, False)
    ts, value = read_cache._read_cache[key]
    read_cache._read_cache[key] = (ts - read_cache._READ_CACHE_TTL_S - 1, value)

    # 磁盘内容已变 → 过期重读应看到新内容（非缓存旧值）。
    _seed_surface(mem_root / "L2" / "标注学习" / "chat.md", [("第二版", 0.9)])
    text = store.read_bucket("标注学习")
    assert "第二版" in text
    assert "第一版" not in text
