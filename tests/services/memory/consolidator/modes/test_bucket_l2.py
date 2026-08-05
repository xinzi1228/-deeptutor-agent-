import pytest

from deeptutor.services.memory import paths


@pytest.fixture
def fake_memory_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "memory_root", lambda: tmp_path)
    return tmp_path


def test_l2_file_bucket_path(fake_memory_root):
    assert paths.l2_file("chat", "标注学习") == fake_memory_root / "L2" / "标注学习" / "chat.md"
    assert paths.l2_file("chat") == fake_memory_root / "L2" / "chat.md"


def test_meta_path_bucket_scoped(fake_memory_root):
    from deeptutor.services.memory.consolidator import meta

    assert meta.l2_meta_path("chat", "标注学习") == fake_memory_root / "L2" / "标注学习" / "chat.meta.json"
    assert meta.l2_meta_path("chat") == fake_memory_root / "L2" / "chat.meta.json"
