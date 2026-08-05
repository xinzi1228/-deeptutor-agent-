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


@pytest.mark.asyncio
async def test_two_buckets_write_independent_l2(fake_memory_root, monkeypatch):
    """两个 bucket 各自生成独立 L2/<bucket>/<surface>.md，互不覆盖。"""
    from deeptutor.services.memory.store import get_memory_store

    async def fake_consolidate(surface, *, language="en", user_label="anonymous",
                               on_event=None, apply_ops=True, bucket=None):
        p = paths.l2_file(surface, bucket)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {bucket} 记忆\n专属内容", encoding="utf-8")

    monkeypatch.setattr(
        "deeptutor.services.memory.consolidator.consolidate_l2", fake_consolidate
    )
    store = get_memory_store()
    await store.update_l2("chat", bucket="标注学习")
    await store.update_l2("chat", bucket="Python学习")
    assert "标注学习" in (fake_memory_root / "L2" / "标注学习" / "chat.md").read_text(encoding="utf-8")
    assert "Python学习" in (fake_memory_root / "L2" / "Python学习" / "chat.md").read_text(encoding="utf-8")
    assert not (fake_memory_root / "L2" / "chat.md").exists()
