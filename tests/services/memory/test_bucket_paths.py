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


def test_read_bucket_returns_bucket_l2_and_global_l3(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import MemoryStore, get_memory_store

    bdir = tmp_path / "L2" / "标注学习"
    bdir.mkdir(parents=True)
    (bdir / "chat.md").write_text("# 标注学习\n遮挡目标处理已掌握", encoding="utf-8")
    l3 = tmp_path / "L3"
    l3.mkdir()
    (l3 / "profile.md").write_text("喜欢简明讲解", encoding="utf-8")

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    text = store.read_bucket("标注学习")
    assert "遮挡目标处理" in text
    assert "喜欢简明讲解" in text  # 全局 L3 共享


def test_read_bucket_empty_returns_placeholder(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    assert "暂无内容" in store.read_bucket("不存在的区")
