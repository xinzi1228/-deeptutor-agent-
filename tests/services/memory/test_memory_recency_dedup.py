"""round2 O2：记忆重排 recency + 1/主题去重。

Covers ``MemoryStore.read_bucket``:
- 同 confidence 时新文件（mtime 大）优先（recency 次序）
- 跨文件同 section（同主题）只保留最高 confidence 一条（去冗余）
- confidence None 仍最后、budget 截断不回归
"""

from __future__ import annotations

from pathlib import Path
import os

import pytest

from deeptutor.services.memory import paths
from deeptutor.services.memory.document import Document, Entry, serialize
from deeptutor.services.memory.ids import new_entry_id


def _seed_surface(
    path: Path, entries: list[tuple[str, float | None]], *, mtime: float | None = None
) -> None:
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
    if mtime is not None:
        os.utime(path, (mtime, mtime))


@pytest.fixture
def mem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    (tmp_path / "L2").mkdir()
    return tmp_path


def _fresh_store():
    """A fresh MemoryStore instance (not the process-wide singleton)."""
    from deeptutor.services.memory.store import MemoryStore

    return MemoryStore()


def test_read_bucket_same_confidence_prefers_newer_file(mem_root: Path) -> None:
    """同 confidence 跨文件同 section → 去重保留最高 confidence 那条；conf 相
    等时 recency 次序，新文件（mtime 大）胜出。"""
    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [("旧文件条目", 0.8)],
        mtime=1_000.0,
    )
    _seed_surface(
        mem_root / "L2" / "标注学习" / "notebook.md",
        [("新文件条目", 0.8)],
        mtime=2_000.0,
    )
    text = _fresh_store().read_bucket("标注学习")
    assert "新文件条目" in text
    assert "旧文件条目" not in text


def test_read_bucket_cross_file_section_dedup_keeps_one(mem_root: Path) -> None:
    """跨文件同 section（同主题）只保留最高 confidence 一条。"""
    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [("低置信条目", 0.3)],
    )
    _seed_surface(
        mem_root / "L2" / "标注学习" / "notebook.md",
        [("高置信条目", 0.9)],
    )
    text = _fresh_store().read_bucket("标注学习")
    assert "高置信条目" in text
    assert "低置信条目" not in text
    # 只渲染 1 条该 section 条目
    assert text.count("- 高置信条目") == 1


def test_read_bucket_dedup_keeps_single_file_sections(mem_root: Path) -> None:
    """section 只出现在单个文件时全部保留（同文件内多条目不是跨文件冗余）。"""
    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [("主题一条目", 0.3), ("主题二条目", 0.5)],
    )
    text = _fresh_store().read_bucket("标注学习")
    assert "主题一条目" in text
    assert "主题二条目" in text


def test_read_bucket_none_confidence_still_last_no_regression(mem_root: Path) -> None:
    """confidence None 仍然最后（recency 排序不破坏原语义）。"""
    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [("低置信", 0.3), ("高置信", 0.9), ("无置信", None)],
    )
    text = _fresh_store().read_bucket("标注学习")
    assert text.index("高置信") < text.index("低置信") < text.index("无置信")


def test_read_bucket_budget_truncation_no_regression(mem_root: Path, monkeypatch) -> None:
    """budget 截断语义不回归：recency/去重改动后截断提示仍出现。"""
    import deeptutor.services.memory.store as store_mod

    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [(f"条目{i}" + "很长的记忆内容" * 5, 0.9) for i in range(8)],
    )
    monkeypatch.setattr(store_mod, "MEMORY_TOKEN_BUDGET", 20)
    text = _fresh_store().read_bucket("标注学习")
    assert "已截断" in text
    assert "共 8 条记忆" in text
