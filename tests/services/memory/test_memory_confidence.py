"""E4: read 端置信度排序 + token 预算截断。

Covers ``MemoryStore.read_bucket`` / ``read_l3_concat``:
- high-confidence 条目排在 low/None 之前
- 超预算 → 截断 + 提示；未超 → 全量返回
- 无 confidence 的旧文档仍返回（顺序保留，不丢失）
"""

from __future__ import annotations

from pathlib import Path

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


def _seed_l3_slot(tmp_path: Path, slot: str, entries: list[tuple[str, float | None]]) -> None:
    doc = Document(
        title=f"{slot} memory",
        sections=[
            (
                "Records",
                [
                    Entry(
                        id=new_entry_id(),
                        section="Records",
                        text=text,
                        refs=["chat:01"],
                        confidence=conf,
                    )
                    for text, conf in entries
                ],
            )
        ],
    )
    (tmp_path / "L3").mkdir(parents=True, exist_ok=True)
    (tmp_path / "L3" / f"{slot}.md").write_text(serialize(doc), encoding="utf-8")


@pytest.fixture
def mem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    (tmp_path / "L2").mkdir()
    return tmp_path


def test_read_bucket_sorts_by_confidence(mem_root: Path) -> None:
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [("低置信", 0.3), ("高置信", 0.9), ("无置信", None)],
    )
    text = get_memory_store().read_bucket("标注学习")
    assert text.index("高置信") < text.index("低置信") < text.index("无置信")


def test_read_bucket_budget_truncates_with_note(mem_root: Path, monkeypatch) -> None:
    import deeptutor.services.memory.store as store_mod
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [(f"条目{i}" + "很长的记忆内容" * 5, 0.9) for i in range(8)],
    )
    monkeypatch.setattr(store_mod, "MEMORY_TOKEN_BUDGET", 20)
    text = get_memory_store().read_bucket("标注学习")
    assert "已截断" in text
    assert "共 8 条记忆" in text


def test_read_bucket_large_budget_returns_all(mem_root: Path) -> None:
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [(f"条目{i}", None) for i in range(5)],
    )
    text = get_memory_store().read_bucket("标注学习")
    for i in range(5):
        assert f"条目{i}" in text
    assert "已截断" not in text


def test_read_bucket_no_confidence_kept_in_order(mem_root: Path) -> None:
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        mem_root / "L2" / "标注学习" / "chat.md",
        [("第一条", None), ("第二条", None), ("第三条", None)],
    )
    text = get_memory_store().read_bucket("标注学习")
    assert text.index("第一条") < text.index("第二条") < text.index("第三条")
    assert "第一条" in text and "第二条" in text and "第三条" in text
    assert "已截断" not in text


def test_read_l3_concat_sorts_by_confidence(mem_root: Path) -> None:
    from deeptutor.services.memory.store import get_memory_store

    _seed_l3_slot(
        mem_root,
        "recent",
        [("低置信记录", 0.2), ("高置信记录", 0.95), ("无置信记录", None)],
    )
    text = get_memory_store().read_l3_concat()
    assert text.index("高置信记录") < text.index("低置信记录") < text.index("无置信记录")


def test_read_l3_concat_budget_truncates_with_note(mem_root: Path, monkeypatch) -> None:
    import deeptutor.services.memory.store as store_mod
    from deeptutor.services.memory.store import get_memory_store

    _seed_l3_slot(
        mem_root,
        "recent",
        [(f"记录{i}" + "很长很长的内容" * 4, 0.9) for i in range(6)],
    )
    monkeypatch.setattr(store_mod, "MEMORY_TOKEN_BUDGET", 15)
    text = get_memory_store().read_l3_concat()
    assert "已截断" in text
    assert "共 6 条记忆" in text
