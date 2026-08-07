"""High-level facade for the three-layer memory subsystem.

All callers — API routers, LLM tools, surface event hooks — go through
:class:`MemoryStore`. The store is stateless; per-user isolation is
inherited from :func:`paths.memory_root` which resolves :class:`PathService`
lazily via context variables.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
from pathlib import Path
import re
import shutil
from typing import Callable, Literal

from deeptutor.services.memory import consolidator, paths, trace
from deeptutor.services.memory.consolidator import ConsolidateResult, OnEvent
from deeptutor.services.memory.document import Document, parse, serialize
from deeptutor.services.memory.ops import AddOp, ApplyReport, EditOp, OpResult
from deeptutor.services.memory.ops import apply as ops_apply
from deeptutor.services.memory.paths import L3Slot, Surface
from deeptutor.services.memory.trace import TraceEvent

logger = logging.getLogger(__name__)

Layer = Literal["L2", "L3"]

_V1_FILES = ("PROFILE.md", "SUMMARY.md")

BUCKET_NAME_RE = re.compile(r"^[\w\u4e00-\u9fa5\-]{1,32}$")

# E8: session-scoped noise stripped before learning records are persisted, so a
# later session never resumes from stale URLs / annotation files / task ids.
_SCRUB_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"https?://\S+"),
    re.compile(r"/[\w/]*annotation_tool[\w.]*"),
    re.compile(r"/images/[\w./-]+"),
    re.compile(r"workspace/[\w./-]+"),
    re.compile(r"[\w./-]+\.(png|jpg|jpeg|html|jsonl)"),
    re.compile(r"task_id[:：]?\s*[\w-]+"),
)

# E4: read 端 token 预算。约 2 chars/token（中文近似），估算 ``ceil(len(text)/2)``。
MEMORY_TOKEN_BUDGET = 2000


def _est_tokens(text: str) -> int:
    """Rough token estimate for the read-end budget (2 chars/token)."""
    return math.ceil(len(text) / 2)


def _scrub_session_noise(text: str) -> str:
    """Remove session-scoped references (URLs, temp paths, task ids) from text.

    Only the temp fragments are dropped; surrounding capability content is
    kept. Leftover whitespace and stray spacing around CJK punctuation are
    collapsed so no blank gaps remain. If scrubbing would leave the text
    empty, the original is returned so content is never swallowed.
    """
    scrubbed = text
    for pattern in _SCRUB_PATTERNS:
        scrubbed = pattern.sub("", scrubbed)
    scrubbed = re.sub(r"\s+", " ", scrubbed).strip()
    scrubbed = re.sub(r"\s*([，。、；：])\s*", r"\1", scrubbed)
    if not scrubbed:
        return text
    return scrubbed


def _confidence_key(entry) -> tuple[bool, float]:
    """Stable sort key: confidence descending, ``None``/absent last."""
    return (entry.confidence is None, -(entry.confidence or 0.0))


def validate_bucket_name(name: str) -> None:
    """Reject names that are not safe directory names for a bucket.

    Guards path traversal (``.``, ``/``, ``\\``), whitespace, and
    over-long names. Raises :class:`ValueError` on invalid input.
    """
    if not isinstance(name, str) or not BUCKET_NAME_RE.match(name):
        raise ValueError(f"invalid bucket name {name!r}")


def _normalize_pref_text(text: str) -> str:
    """Whitespace/case-insensitive key for duplicate-preference detection."""
    return " ".join(str(text or "").split()).casefold()


def _find_duplicate_preference(doc: Document, section: str, text: str):
    """Return an existing entry in ``section`` whose text matches ``text``.

    Read-only — does not create the section if it is absent.
    """
    target = _normalize_pref_text(text)
    if not target:
        return None
    for entry in doc.all_entries():
        if entry.section == section and _normalize_pref_text(entry.text) == target:
            return entry
    return None


_NO_MEMORY = (
    "(No memory available — interact with DeepTutor and update from the Memory page to build one.)"
)


@dataclass
class DocOverview:
    layer: Layer
    key: str  # surface name (L2) or slot name (L3)
    exists: bool
    updated_at: str | None
    entry_count: int
    backlog: int  # L1 events since last update (L2 only; 0 for L3)


class MemoryStore:
    """Stateless facade. Safe to call as a process-wide singleton."""

    def __init__(self) -> None:
        self._write_locks: dict[str, asyncio.Lock] = {}

    # ── L1 ────────────────────────────────────────────────────────────────

    async def emit(self, event: TraceEvent) -> None:
        await trace.append(event)

    # ── L2 / L3 read ──────────────────────────────────────────────────────

    def read_doc(self, layer: Layer, key: str) -> Document:
        path = self._path(layer, key)
        if not path.exists():
            return Document(title=_default_title(layer, key))
        return parse(path.read_text(encoding="utf-8"))

    def read_raw(self, layer: Layer, key: str) -> str:
        path = self._path(layer, key)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def read_l3_concat(self) -> str:
        """Concatenate all four L3 docs for the ``read_memory`` tool.

        L3 slots with parseable per-entry structure are rendered
        confidence-sorted (descending, ``None`` last) within each section
        and truncated to ``MEMORY_TOKEN_BUDGET``. Plain-paragraph slots
        (no parseable entries) are kept verbatim under the same global
        token budget. When the budget was exceeded a truncation note is
        appended at the tail.
        """
        parts: list[str] = []
        budget = MEMORY_TOKEN_BUDGET
        total = 0
        kept = 0
        truncated = False
        for slot in paths.L3_SLOTS:
            raw = self.read_raw("L3", slot).strip()
            if not raw:
                continue
            doc = parse(raw)
            visible = doc.visible_entries()
            if not visible:
                if doc.all_entries():
                    continue  # all stale — nothing visible
                toks = _est_tokens(raw)
                total += 1
                if toks > budget:
                    truncated = True
                    continue
                parts.append(raw)
                kept += 1
                budget -= toks
                continue
            prefix = [f"# {doc.title}"] if doc.title else []
            text, t, k, used = self._render_doc_budgeted(doc, budget, prefix)
            total += t
            kept += k
            budget -= used
            if text:
                parts.append(text)
            if k < t:
                truncated = True
        if not parts:
            if truncated:
                return f"（已截断，共 {total} 条记忆展示前 {kept} 条）\n"
            return _NO_MEMORY
        out = "\n\n---\n\n".join(parts) + "\n"
        if truncated:
            out += f"（已截断，共 {total} 条记忆展示前 {kept} 条）\n"
        return out

    def bucket_overview(self, bucket: str, *, fallback: bool = True) -> dict:
        """Structured, cheap overview of a memory bucket for progressive loading.

        Returns ``{"bucket", "source", "surfaces", "l3_slots"}`` where each
        surface entry is ``{"surface", "entries", "preview"}`` (visible
        (non-stale) entry count, preview = first visible bullet line
        ≤ 80 chars, ``""`` when nothing is visible).
        ``source`` is ``"bucket"`` when the bucket's L2 directory holds
        ``.md`` files, ``"fallback"`` when it is empty and ``fallback`` is
        true (reading the global L2 root, root-level only), and ``"empty"``
        when nothing is readable anywhere. ``l3_slots`` counts the global L3
        slots with non-empty content.
        """
        surfaces: list[dict] = []
        bdir = paths.buckets_dir() / bucket
        if bdir.is_dir():
            bucket_files = sorted(bdir.glob("*.md"))
            if bucket_files:
                surfaces = [self._surface_overview(md) for md in bucket_files]
        source = "bucket" if surfaces else "empty"
        if not surfaces and fallback:
            gdir = paths.l2_dir()
            if gdir.is_dir():
                global_files = sorted(gdir.glob("*.md"))
                if global_files:
                    surfaces = [self._surface_overview(md) for md in global_files]
                    source = "fallback"
        l3_slots = sum(1 for slot in paths.L3_SLOTS if self.read_raw("L3", slot).strip())
        return {
            "bucket": bucket,
            "source": source,
            "surfaces": surfaces,
            "l3_slots": l3_slots,
        }

    def _surface_overview(self, md: Path) -> dict:
        """Visible (non-stale) entry count + first visible bullet preview for
        one L2 surface file."""
        text = md.read_text(encoding="utf-8")
        doc = parse(text)
        entries = sorted(doc.visible_entries(), key=_confidence_key)
        preview = entries[0].text.strip()[:80] if entries else ""
        return {"surface": md.stem, "entries": len(entries), "preview": preview}

    def _render_doc_budgeted(
        self, doc: Document, budget_left: int, prefix_lines: list[str]
    ) -> tuple[str, int, int, int]:
        """Render ``doc``'s visible (non-stale) entries grouped by section.

        Within each section, entries are sorted by confidence descending
        (``None``/absent last, stable). Only entries whose estimated token
        count (``ceil(len(text)/2)``) still fits in ``budget_left`` are
        kept — this is a *per-surface* sort followed by a *global* budget
        applied across surfaces by the caller. Sections with no kept entry
        are omitted entirely.

        Returns ``(text, total_visible, kept, tokens_used)``.
        """
        lines = list(prefix_lines)
        total = 0
        kept = 0
        used = 0
        for section, entries in doc.sections:
            section_visible = [e for e in entries if not e.stale]
            if not section_visible:
                continue
            total += len(section_visible)
            section_visible = sorted(section_visible, key=_confidence_key)
            kept_lines: list[str] = []
            for e in section_visible:
                toks = _est_tokens(e.text)
                if used + toks > budget_left:
                    break
                kept_lines.append(f"- {e.text}")
                used += toks
                kept += 1
            if kept_lines:
                lines.append(f"## {section}")
                lines.extend(kept_lines)
        if kept == 0:
            return "", total, 0, 0
        return "\n".join(lines), total, kept, used

    def _render_surface(self, md: Path, budget_left: int) -> tuple[str, int, int, int]:
        """Render one L2 surface md: visible entries grouped by section.

        Document-format files render as ``## [{stem}]`` followed by
        ``## <section>`` headers and ``- <text>`` bullets for visible
        (non-stale) entries only — confidence-sorted per surface and
        budget-truncated. Files with no parseable entries (legacy raw
        text) fall back to their raw body so pre-document content still
        surfaces; the raw body counts as one opaque entry against the
        budget. Returns ``(text, total_visible, kept, tokens_used)``;
        ``text`` is ``""`` when the file contributes nothing.
        """
        text = md.read_text(encoding="utf-8")
        doc = parse(text)
        visible = doc.visible_entries()
        if not visible:
            if doc.all_entries():
                return "", 0, 0, 0  # all entries stale — nothing visible to render
            body = text.strip()
            if not body:
                return "", 0, 0, 0
            toks = _est_tokens(body)
            if toks > budget_left:
                return "", 1, 0, 0
            return f"## [{md.stem}]\n{body}", 1, 1, toks
        text, total, kept, used = self._render_doc_budgeted(doc, budget_left, [f"## [{md.stem}]"])
        return text, total, kept, used

    def read_bucket(self, bucket: str, *, fallback: bool = True) -> str:
        """Read a memory bucket: its L2 summaries across surfaces + global L3.

        L2 surfaces are rendered confidence-sorted (descending, ``None``
        last) *per surface*, then a *global* token budget
        (``MEMORY_TOKEN_BUDGET``) is applied across surfaces in file order;
        once the budget is exhausted remaining entries are dropped and a
        truncation note is appended. L3 slots (preferences etc.) are
        appended as-is — the global shared layer is not
        confidence-sorted/truncated.

        When the bucket's L2 directory holds no ``.md`` files (empty bucket)
        and ``fallback`` is true, additionally read the global L2 root
        (``L2/*.md``, root-level only — never other buckets) and prepend a
        source note. ``fallback=False`` keeps strict bucket isolation: an
        empty bucket returns the empty placeholder and never touches the
        global root.
        """
        parts: list[str] = []
        budget = MEMORY_TOKEN_BUDGET
        total = 0
        kept = 0
        bucket_files: list[Path] = []
        bdir = paths.buckets_dir() / bucket
        if bdir.is_dir():
            bucket_files = sorted(bdir.glob("*.md"))
            for md in bucket_files:
                body, t, k, used = self._render_surface(md, budget)
                total += t
                kept += k
                budget -= used
                if body:
                    parts.append(body)
        fallback_note = ""
        if not bucket_files and fallback:
            gdir = paths.l2_dir()
            if gdir.is_dir():
                for md in sorted(gdir.glob("*.md")):
                    body, t, k, used = self._render_surface(md, budget)
                    total += t
                    kept += k
                    budget -= used
                    if body:
                        parts.append(body)
            if parts:
                fallback_note = "（当前记忆区暂无内容，已回退到全局记忆）\n\n"
        for slot in paths.L3_SLOTS:
            body = self.read_raw("L3", slot).strip()
            if body:
                parts.append(body)
        if not parts:
            if kept < total:
                return f"（已截断，共 {total} 条记忆展示前 {kept} 条）\n"
            return "（该记忆区暂无内容）\n"
        if kept < total:
            parts.append(f"（已截断，共 {total} 条记忆展示前 {kept} 条）")
        return fallback_note + "\n\n---\n\n".join(parts) + "\n"

    # ── Bucket management ─────────────────────────────────────────────────

    def create_bucket(self, name: str) -> bool:
        """Create a bucket directory under L2.

        Returns ``True`` if newly created, ``False`` if it already existed.
        Raises :class:`ValueError` for invalid names (see
        :func:`validate_bucket_name`).
        """
        validate_bucket_name(name)
        path = paths.buckets_dir() / name
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        return not existed

    def delete_bucket(self, name: str) -> bool:
        """Remove a bucket directory (recursively).

        Returns ``True`` if the directory existed before deletion,
        ``False`` otherwise. Raises :class:`ValueError` for invalid names.
        """
        validate_bucket_name(name)
        path = paths.buckets_dir() / name
        existed = path.exists()
        shutil.rmtree(path, ignore_errors=True)
        return existed

    # ── L2 / L3 write (manual paths) ──────────────────────────────────────

    async def overwrite_doc(self, layer: Layer, key: str, md: str) -> None:
        """Direct user-driven save from the workbench editor."""
        path = self._path(layer, key)
        async with self._lock_for(path):
            await asyncio.to_thread(_atomic_write, path, md)

    async def delete_entry(self, layer: Layer, key: str, entry_id: str) -> bool:
        path = self._path(layer, key)
        return await self._mutate_entry(path, entry_id, Document.remove)

    async def mark_stale(
        self, surface: str, entry_id: str, *, bucket: str | None = None
    ) -> bool:
        """Mark an L2 entry stale so read paths hide it (no physical delete).

        Only L2 surfaces accept stale marks — L3 slots (preferences
        included) raise :class:`ValueError`. Returns ``True`` iff the entry
        exists (idempotent: marking an already-stale entry is a no-op write
        that still returns ``True``).
        """
        if surface in paths.L3_SLOTS:
            raise ValueError(f"L3 slot {surface!r} cannot be marked stale")
        if surface not in paths.SURFACES:
            raise ValueError(f"unknown surface {surface!r}")
        path = paths.l2_file(surface, bucket)  # type: ignore[arg-type]
        return await self._mutate_entry(path, entry_id, Document.mark_stale)

    async def unmark_stale(
        self, surface: str, entry_id: str, *, bucket: str | None = None
    ) -> bool:
        """Clear an L2 entry's stale flag (restores it to read paths).

        Same safeguard as :meth:`mark_stale`: L3 slots raise
        :class:`ValueError`. Returns ``True`` iff the entry exists
        (idempotent: unmarking an already-visible entry is a no-op write
        that still returns ``True``).
        """
        if surface in paths.L3_SLOTS:
            raise ValueError(f"L3 slot {surface!r} cannot be unmarked")
        if surface not in paths.SURFACES:
            raise ValueError(f"unknown surface {surface!r}")
        path = paths.l2_file(surface, bucket)  # type: ignore[arg-type]
        return await self._mutate_entry(path, entry_id, Document.unmark_stale)

    # ── L2 / L3 write (consolidator paths) ────────────────────────────────

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

    async def update_l3(
        self,
        slot: L3Slot,
        *,
        language: str = "en",
        user_label: str = "anonymous",
        on_event: OnEvent | None = None,
        apply_ops: bool = True,
    ) -> ConsolidateResult:
        if slot == "preferences":
            raise ValueError("preferences.md is not auto-consolidated")
        path = paths.l3_file(slot)
        async with self._lock_for(path):
            return await consolidator.consolidate_l3(
                slot,
                language=language,
                user_label=user_label,
                on_event=on_event,
                apply_ops=apply_ops,
            )

    async def apply_ops_payload(
        self, layer: Layer, key: str, ops_payload: list[dict]
    ) -> ApplyReport:
        """Apply a list of ops-as-JSON to a layer doc atomically.

        Used by the workbench's preview → apply two-step flow. The
        payload typically comes from a previous ``apply_ops=False``
        consolidate call surfaced to the user for review.
        """
        from deeptutor.services.memory.consolidator import _parse_ops_response

        path = self._path(layer, key)
        json_like = {"ops": ops_payload}
        import json as _json

        ops = _parse_ops_response(_json.dumps(json_like, ensure_ascii=False))
        async with self._lock_for(path):
            default_title = _default_title(layer, key)
            doc = (
                parse(path.read_text(encoding="utf-8"))
                if path.exists()
                else Document(title=default_title)
            )
            report = ops_apply(doc, ops)
            if report.accepted and ops:
                path.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(_atomic_write, path, serialize(doc))
            return report

    async def write_preference(
        self,
        *,
        op: Literal["add", "edit"],
        text: str,
        target_id: str | None = None,
        reason: str | None = None,
        trace_id: str,
    ) -> ApplyReport:
        """Write the chat-mode preference signal. The ``write_memory`` tool
        is the only caller; ``trace_id`` is the current chat turn's L1 id
        injected by runtime."""
        path = paths.l3_file("preferences")
        async with self._lock_for(path):
            doc = (
                parse(path.read_text(encoding="utf-8"))
                if path.exists()
                else Document(title=_default_title("L3", "preferences"))
            )
            section = "Preferences"
            if op == "add":
                # Idempotent add: preferences.md is never auto-consolidated
                # (see update_l3), so an identical bullet added again would
                # persist forever as a duplicate. Guided-learning turns are
                # highly tool-driven and long-running, so the model tends to
                # re-issue the same write_memory across turns (issue #647).
                # Short-circuit to a no-op that reports the existing entry as
                # already saved instead of appending a duplicate.
                duplicate = _find_duplicate_preference(doc, section, text)
                if duplicate is not None:
                    return ApplyReport(
                        accepted=True,
                        results=[
                            OpResult(
                                op=AddOp(section=section, text=text, refs=[trace_id]),
                                status="applied",
                                entry_id=duplicate.id,
                                detail="duplicate",
                            )
                        ],
                    )
                report = ops_apply(
                    doc,
                    [AddOp(section=section, text=text, refs=[trace_id])],
                )
            else:
                if not target_id:
                    return ApplyReport(accepted=False, reason="edit requires target_id")
                report = ops_apply(
                    doc,
                    [
                        EditOp(
                            target_id=target_id,
                            new_text=text,
                            new_refs=[trace_id],
                        )
                    ],
                )
            if report.accepted:
                await asyncio.to_thread(_atomic_write, path, serialize(doc))
            if reason:
                # Surface the reason in logs for workbench observability.
                logger.info("write_memory %s id=%s reason=%s", op, target_id or "new", reason)
            return report

    async def append_learning_summary(self, text: str, ref: str) -> ApplyReport:
        """Append one short learning-record summary to L3 ``recent.md``.

        Used by the annotation-coach's ``write_learning_record`` tool so the
        next conversation can resume from the last checkpoint via
        ``read_memory``. The canonical structured record lives in the JSONL
        learning store; this is a compact human-readable mirror. The bullet
        is capped at the standard 240-char entry limit.
        """
        path = paths.l3_file("recent")
        async with self._lock_for(path):
            doc = (
                parse(path.read_text(encoding="utf-8"))
                if path.exists()
                else Document(title=_default_title("L3", "recent"))
            )
            section = "Learning Records"
            text = _scrub_session_noise(text)
            report = ops_apply(doc, [AddOp(section=section, text=text, refs=[ref])])
            if report.accepted:
                path.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(_atomic_write, path, serialize(doc))
            return report

    # ── Workbench overview ────────────────────────────────────────────────

    def overview(self) -> list[DocOverview]:
        rows: list[DocOverview] = []
        for surface in paths.SURFACES:
            rows.append(self._overview_for("L2", surface))
        for slot in paths.L3_SLOTS:
            rows.append(self._overview_for("L3", slot))
        return rows

    def _overview_for(self, layer: Layer, key: str) -> DocOverview:
        path = self._path(layer, key)
        if not path.exists():
            backlog = trace.count_since(key) if layer == "L2" else 0  # type: ignore[arg-type]
            return DocOverview(
                layer=layer,
                key=key,
                exists=False,
                updated_at=None,
                entry_count=0,
                backlog=backlog,
            )

        stat = path.stat()
        updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        try:
            doc = parse(path.read_text(encoding="utf-8"))
            entry_count = len(doc.all_entries())
        except Exception:
            entry_count = 0

        backlog = 0
        if layer == "L2":
            try:
                cutoff = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                backlog = trace.count_since(key, since=cutoff)  # type: ignore[arg-type]
            except Exception:
                backlog = 0

        return DocOverview(
            layer=layer,
            key=key,
            exists=True,
            updated_at=updated_at,
            entry_count=entry_count,
            backlog=backlog,
        )

    # ── Internals ─────────────────────────────────────────────────────────

    def _path(self, layer: Layer, key: str) -> Path:
        if layer == "L2":
            if key not in paths.SURFACES:
                raise ValueError(f"unknown surface {key!r}")
            return paths.l2_file(key)  # type: ignore[arg-type]
        if key not in paths.L3_SLOTS:
            raise ValueError(f"unknown L3 slot {key!r}")
        return paths.l3_file(key)  # type: ignore[arg-type]

    def _lock_for(self, path: Path) -> asyncio.Lock:
        key = str(path)
        lock = self._write_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._write_locks[key] = lock
        return lock

    async def _mutate_entry(
        self,
        path: Path,
        entry_id: str,
        mutate: Callable[[Document, str], bool],
    ) -> bool:
        """Lock, parse, mutate one entry, and rewrite atomically iff it changed.

        ``mutate(doc, entry_id)`` is expected to return ``True`` when the
        entry was found (e.g. :meth:`Document.mark_stale`). The file is only
        rewritten when the mutation actually altered the document — a
        redundant mark/unmark on an entry already in the target state is a
        no-op write. Returns ``True`` iff the entry was found.
        """
        if not path.exists():
            return False
        async with self._lock_for(path):
            before = path.read_text(encoding="utf-8")
            doc = parse(before)
            if not mutate(doc, entry_id):
                return False
            after = serialize(doc)
            if after != before:
                await asyncio.to_thread(_atomic_write, path, after)
            return True


# ── v1 → v2 startup migration ─────────────────────────────────────────────


def migrate_v1_if_needed() -> Path | None:
    """If any v1 memory files are present under the memory root, move the
    whole memory directory's loose files into ``memory/backup/<ts>/``.

    Idempotent: if there's nothing v1-shaped at the root, this is a no-op.

    Returns the backup directory path on migration, or ``None`` otherwise.
    """
    root = paths.memory_root()
    if not root.exists():
        return None
    v1_present = [name for name in _V1_FILES if (root / name).exists()]
    if not v1_present:
        return None

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = paths.backup_root() / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    for item in list(root.iterdir()):
        if item.name in {"trace", "L2", "L3", "backup"}:
            continue
        try:
            shutil.move(str(item), str(backup_dir / item.name))
        except OSError:
            logger.warning("v1 memory migration: failed to move %s", item, exc_info=True)
    logger.info("v1 memory migrated to %s", backup_dir)
    return backup_dir


def migrate_partner_surface_if_needed() -> bool:
    """Rename the legacy ``tutorbot`` memory surface to ``partner``.

    The partner surface key used to be ``tutorbot`` — so footnote refs read
    ``tutorbot:<id>`` and the consolidator even wrote "tutorbot" into L2
    prose. It is now ``partner``. This moves any on-disk artifacts (L2 doc +
    meta, snapshot dir, trace dir) to the new name, rewrites the ``tutorbot``
    token to ``partner`` inside the L2 doc/meta (both the ``tutorbot:`` ref
    prefix and the bare prose word), and renames the per-surface key inside
    every L3 meta.

    Idempotent: skips any target that already exists; a no-op when nothing
    tutorbot-shaped lives under the memory root.
    """
    import json
    import re

    root = paths.memory_root()
    if not root.exists():
        return False

    moved = False

    l2 = paths.l2_dir()
    old_md, new_md = l2 / "tutorbot.md", l2 / "partner.md"
    if old_md.exists() and not new_md.exists():
        text = old_md.read_text(encoding="utf-8")
        text = text.replace("tutorbot:", "partner:")  # footnote/inline refs
        text = re.sub(r"\btutorbot\b", "partner", text)  # bare prose word
        text = re.sub(r"\bTutorbot\b", "Partner", text)
        new_md.write_text(text, encoding="utf-8")
        old_md.unlink()
        moved = True
    old_meta, new_meta = l2 / "tutorbot.meta.json", l2 / "partner.meta.json"
    if old_meta.exists() and not new_meta.exists():
        text = old_meta.read_text(encoding="utf-8").replace("tutorbot:", "partner:")
        new_meta.write_text(text, encoding="utf-8")
        old_meta.unlink()
        moved = True

    # snapshot/<surface>/ and trace/<surface>/ — plain directory moves
    # (entity ids carry no surface prefix, so no content rewrite needed).
    for sub in ("snapshot", "trace"):
        old_dir, new_dir = root / sub / "tutorbot", root / sub / "partner"
        if old_dir.is_dir() and not new_dir.exists():
            shutil.move(str(old_dir), str(new_dir))
            moved = True

    # L3 metas track seen L2 entry ids per surface — rename that key.
    l3 = paths.l3_dir()
    if l3.is_dir():
        for meta_path in l3.glob("*.meta.json"):
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            seen = data.get("seen_l2_entry_ids")
            if isinstance(seen, dict) and "tutorbot" in seen and "partner" not in seen:
                seen["partner"] = seen.pop("tutorbot")
                meta_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                moved = True

    if moved:
        logger.info("migrated legacy 'tutorbot' memory surface to 'partner'")
    return moved


# ── Singleton accessor ────────────────────────────────────────────────────


_singleton: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _singleton
    if _singleton is None:
        _singleton = MemoryStore()
    return _singleton


# ── Helpers ───────────────────────────────────────────────────────────────


def _default_title(layer: Layer, key: str) -> str:
    if layer == "L2":
        return f"{key} memory"
    return {
        "recent": "Recent summary",
        "profile": "User profile",
        "scope": "Knowledge scope",
        "preferences": "Preferences",
    }.get(key, key)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
