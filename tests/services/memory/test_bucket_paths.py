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


def test_fallback_reads_global_when_bucket_empty(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    l2 = tmp_path / "L2"
    l2.mkdir()
    (l2 / "chat.md").write_text("全局记忆内容", encoding="utf-8")
    (l2 / "标注学习").mkdir()

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    text = store.read_bucket("标注学习")
    assert "全局记忆内容" in text
    assert "已回退到全局记忆" in text


def test_no_fallback_when_bucket_has_content(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    bdir = tmp_path / "L2" / "标注学习"
    bdir.mkdir(parents=True)
    (bdir / "chat.md").write_text("标注学习内容", encoding="utf-8")
    (tmp_path / "L2" / "global.md").write_text("全局记忆内容", encoding="utf-8")

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    text = store.read_bucket("标注学习")
    assert "标注学习内容" in text
    assert "全局记忆内容" not in text
    assert "已回退到全局记忆" not in text


def test_strict_fallback_false(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    l2 = tmp_path / "L2"
    l2.mkdir()
    (l2 / "chat.md").write_text("全局记忆内容", encoding="utf-8")
    (l2 / "标注学习").mkdir()

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    text = store.read_bucket("标注学习", fallback=False)
    assert "该记忆区暂无内容" in text
    assert "全局记忆内容" not in text


# ── bucket_overview ─────────────────────────────────────────────────────


def _seed_surface(path, texts):
    """Write an L2 surface doc with ``texts`` as bullets (document format)."""
    from deeptutor.services.memory.document import Document, Entry, serialize
    from deeptutor.services.memory.ids import new_entry_id

    doc = Document(
        title=f"{path.stem} memory",
        sections=[
            (
                "Topics",
                [
                    Entry(id=new_entry_id(), section="Topics", text=t, refs=["chat:01"])
                    for t in texts
                ],
            )
        ],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(doc), encoding="utf-8")


def test_overview_bucket_source(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握", "置信度阈值设置原则"],
    )

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    ov = get_memory_store().bucket_overview("标注学习")
    assert ov["source"] == "bucket"
    chat = next(s for s in ov["surfaces"] if s["surface"] == "chat")
    assert chat["entries"] >= 2
    assert chat["preview"].strip()


def test_overview_fallback_source(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    (tmp_path / "L2" / "标注学习").mkdir(parents=True)
    _seed_surface(tmp_path / "L2" / "chat.md", ["全局记忆条目"])

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    ov = get_memory_store().bucket_overview("标注学习")
    assert ov["source"] == "fallback"
    assert any(s["surface"] == "chat" for s in ov["surfaces"])


def test_overview_empty_source(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    ov = get_memory_store().bucket_overview("不存在的区")
    assert ov["source"] == "empty"
    assert ov["surfaces"] == []


@pytest.mark.asyncio
async def test_read_memory_overview_only(monkeypatch, tmp_path):
    from deeptutor.tools.builtin import ReadMemoryTool

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握", "置信度阈值设置原则"],
    )

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    result = await ReadMemoryTool().execute(bucket="标注学习", overview_only=True)
    assert result.metadata["overview"] is True
    assert result.metadata["bucket"] == "标注学习"
    assert "[chat]" in result.content
    assert "2 条" in result.content


# ── stale marking (O3) ───────────────────────────────────────────────


def _entry_id(monkeypatch, tmp_path, surface, bucket):
    from deeptutor.services.memory.document import parse as doc_parse

    md = tmp_path / "L2" / bucket / f"{surface}.md"
    return doc_parse(md.read_text(encoding="utf-8")).all_entries()[0].id


@pytest.mark.asyncio
async def test_mark_stale_hides_from_read_bucket(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握", "置信度阈值设置原则"],
    )
    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()

    entry_id = _entry_id(monkeypatch, tmp_path, "chat", "标注学习")
    assert await store.mark_stale("chat", entry_id, bucket="标注学习") is True

    text = store.read_bucket("标注学习")
    assert "遮挡目标处理已掌握" not in text
    assert "置信度阈值设置原则" in text


@pytest.mark.asyncio
async def test_unmark_stale_restores(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握", "置信度阈值设置原则"],
    )
    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()

    entry_id = _entry_id(monkeypatch, tmp_path, "chat", "标注学习")
    await store.mark_stale("chat", entry_id, bucket="标注学习")
    assert "遮挡目标处理已掌握" not in store.read_bucket("标注学习")

    assert await store.unmark_stale("chat", entry_id, bucket="标注学习") is True
    assert "遮挡目标处理已掌握" in store.read_bucket("标注学习")


@pytest.mark.asyncio
async def test_mark_stale_l3_rejected(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    with pytest.raises(ValueError):
        await store.mark_stale("preferences", "m_01HZK1ABCDEFGHJKMNPQRSTVWX")
    with pytest.raises(ValueError):
        await store.unmark_stale("preferences", "m_01HZK1ABCDEFGHJKMNPQRSTVWX")


@pytest.mark.asyncio
async def test_overview_counts_visible_only(monkeypatch, tmp_path):
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握", "置信度阈值设置原则"],
    )
    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()

    chat = next(
        s for s in store.bucket_overview("标注学习")["surfaces"] if s["surface"] == "chat"
    )
    assert chat["entries"] == 2

    entry_id = _entry_id(monkeypatch, tmp_path, "chat", "标注学习")
    await store.mark_stale("chat", entry_id, bucket="标注学习")

    chat = next(
        s for s in store.bucket_overview("标注学习")["surfaces"] if s["surface"] == "chat"
    )
    assert chat["entries"] == 1


@pytest.mark.asyncio
async def test_read_bucket_omits_surface_when_all_stale(monkeypatch, tmp_path):
    """All entries stale → the surface contributes nothing to read_bucket."""
    from deeptutor.services.memory.document import Document, Entry, serialize
    from deeptutor.services.memory.ids import new_entry_id
    from deeptutor.services.memory.store import get_memory_store

    doc = Document(
        title="chat memory",
        sections=[
            (
                "Topics",
                [
                    Entry(id=new_entry_id(), section="Topics", text="旧结论一", stale=True),
                    Entry(id=new_entry_id(), section="Topics", text="旧结论二", stale=True),
                ],
            )
        ],
    )
    chat = tmp_path / "L2" / "标注学习" / "chat.md"
    chat.parent.mkdir(parents=True, exist_ok=True)
    chat.write_text(serialize(doc), encoding="utf-8")

    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    text = get_memory_store().read_bucket("标注学习")
    assert "## [chat]" not in text
    assert "旧结论一" not in text
    assert "旧结论二" not in text


@pytest.mark.asyncio
async def test_fallback_hides_stale_global_entry(monkeypatch, tmp_path):
    """Stale entries in a global L2 file stay hidden through the O1 fallback path."""
    from deeptutor.services.memory.document import parse as doc_parse
    from deeptutor.services.memory.store import get_memory_store

    (tmp_path / "L2" / "标注学习").mkdir(parents=True)
    _seed_surface(tmp_path / "L2" / "chat.md", ["保留的全局条目", "已过期全局条目"])
    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()

    global_chat = tmp_path / "L2" / "chat.md"
    entries = doc_parse(global_chat.read_text(encoding="utf-8")).all_entries()
    await store.mark_stale("chat", entries[1].id)

    text = store.read_bucket("标注学习")
    assert "已回退到全局记忆" in text
    assert "## [chat]" in text
    assert "保留的全局条目" in text
    assert "已过期全局条目" not in text


@pytest.mark.asyncio
async def test_mark_already_stale_does_not_rewrite(monkeypatch, tmp_path):
    """Marking an already-stale entry is a no-op write (bytes + mtime unchanged)."""
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握"],
    )
    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    chat = tmp_path / "L2" / "标注学习" / "chat.md"

    entry_id = _entry_id(monkeypatch, tmp_path, "chat", "标注学习")
    assert await store.mark_stale("chat", entry_id, bucket="标注学习") is True
    bytes_before = chat.read_bytes()
    mtime_before = chat.stat().st_mtime_ns

    assert await store.mark_stale("chat", entry_id, bucket="标注学习") is True
    assert chat.read_bytes() == bytes_before
    assert chat.stat().st_mtime_ns == mtime_before


@pytest.mark.asyncio
async def test_unmark_already_visible_does_not_rewrite(monkeypatch, tmp_path):
    """Unmarking an already-visible entry is a no-op write."""
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握"],
    )
    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()
    chat = tmp_path / "L2" / "标注学习" / "chat.md"

    entry_id = _entry_id(monkeypatch, tmp_path, "chat", "标注学习")
    bytes_before = chat.read_bytes()
    mtime_before = chat.stat().st_mtime_ns

    assert await store.unmark_stale("chat", entry_id, bucket="标注学习") is True
    assert chat.read_bytes() == bytes_before
    assert chat.stat().st_mtime_ns == mtime_before


@pytest.mark.asyncio
async def test_overview_preview_empty_when_all_stale(monkeypatch, tmp_path):
    """All entries stale → preview is "" (never falls back to the title line)."""
    from deeptutor.services.memory.store import get_memory_store

    _seed_surface(
        tmp_path / "L2" / "标注学习" / "chat.md",
        ["遮挡目标处理已掌握", "置信度阈值设置原则"],
    )
    monkeypatch.setattr("deeptutor.services.memory.paths.memory_root", lambda: tmp_path)
    store = get_memory_store()

    chat_path = tmp_path / "L2" / "标注学习" / "chat.md"
    from deeptutor.services.memory.document import parse as doc_parse

    for entry in doc_parse(chat_path.read_text(encoding="utf-8")).all_entries():
        await store.mark_stale("chat", entry.id, bucket="标注学习")

    chat = next(
        s for s in store.bucket_overview("标注学习")["surfaces"] if s["surface"] == "chat"
    )
    assert chat["entries"] == 0
    assert chat["preview"] == ""
