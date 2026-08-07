from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from deeptutor.services.memory import paths, store
from deeptutor.services.memory.store import MemoryStore, _scrub_session_noise


@pytest.fixture
def tmp_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``paths.memory_root`` at an isolated tmp dir."""
    root = tmp_path / "memory"
    monkeypatch.setattr(paths, "memory_root", lambda: root)
    paths.ensure_dirs()
    monkeypatch.setattr(store, "_singleton", None)
    return root


def _run(coro):
    return asyncio.run(coro)


def test_scrub_removes_url_and_path_fragments() -> None:
    text = (
        "参见 https://example.com/data 和 /images/task1.png，"
        "使用 annotation_tool.html，task_id: abc 完成"
    )
    out = _scrub_session_noise(text)
    assert "https://example.com/data" not in out
    assert "/images/task1.png" not in out
    assert "annotation_tool.html" not in out
    assert "task_id" not in out


def test_scrub_keeps_pure_capability_conclusion() -> None:
    text = "掌握了遮挡检测的边界规范，F1 从 0.5 提升到 0.83"
    assert _scrub_session_noise(text) == text


def test_scrub_url_stops_at_cjk_preserving_following_content() -> None:
    text = "参见 https://example.com/data完成遮挡检测，F1 提升到 0.83"
    out = _scrub_session_noise(text)
    assert "https://example.com/data" not in out
    assert "完成遮挡检测" in out
    assert "F1 提升到 0.83" in out


def test_scrub_leaves_no_double_punctuation_or_space_gaps() -> None:
    text = "参考 annotation_tool.html，完成遮挡检测，注意 /images/task1.png 中"
    out = _scrub_session_noise(text)
    assert "， " not in out
    assert " ，" not in out
    assert "  " not in out
    assert "，，" not in out
    assert "annotation_tool.html" not in out
    assert "/images/task1.png" not in out


def test_append_learning_summary_scrubs_persisted_entry(tmp_memory: Path) -> None:
    s = MemoryStore()
    text = "参考 annotation_tool.html 和 task_id: abc 完成遮挡检测，F1 提升到 0.83"
    report = _run(s.append_learning_summary(text, ref="turn:abc"))
    assert report.accepted

    recent = (tmp_memory / "L3" / "recent.md").read_text(encoding="utf-8")
    assert "annotation_tool.html" not in recent
    assert "task_id: abc" not in recent
    assert "遮挡检测" in recent
    assert "F1 提升到 0.83" in recent


def test_scrub_fallback_returns_original_on_empty_result() -> None:
    assert _scrub_session_noise("") == ""
    assert _scrub_session_noise("   ") == "   "
    assert _scrub_session_noise("task_id: abc") == "task_id: abc"
    assert _scrub_session_noise("好") == "好"
