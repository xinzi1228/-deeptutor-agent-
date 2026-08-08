"""LLM batch dedup for learning records (TencentDB-Agent-Memory borrow).

Mirrors ``l1-dedup.ts`` conflict detection: a single LLM call decides how a
batch of new records relate to existing ones (store/skip/update/merge), then
the decisions are applied to the JSONL truth. Every failure path degrades to
``store`` so no record is ever lost (truth-preserving, reversible).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from deeptutor.services.learning_records import RECORD_TYPES

logger = logging.getLogger(__name__)

_VALID_ACTIONS = {"store", "skip", "update", "merge"}


def build_candidates(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Cluster active records by (type, task_id, knowledge_point) anchor.

    Tencent's unified candidate pool relies on vector recall; we have no
    vector store for records, so the deterministic (type, anchor) clustering
    is the candidate pool. Returns groups of records that may conflict.
    """
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    standalone: list[dict[str, Any]] = []
    for r in records:
        if r.get("archived"):
            continue
        kind = r.get("type")
        if kind in ("annotation_exercise", "theory_mastered"):
            key = (kind, str(r.get("task_id", "")), str(r.get("knowledge_point", "")))
            if key[1] or key[2]:
                groups.setdefault(key, []).append(r)
                continue
        standalone.append(r)
    out: list[list[dict[str, Any]]] = []
    for g in groups.values():
        out.append(g)
    for s in standalone:
        out.append([s])
    return out


def parse_decisions(raw: str, new_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Parse the LLM's batch decision JSON into a per-record_id decision map.

    Mirrors Tencent's ``parseBatchResult``: strip markdown fences, extract the
    JSON array, skip empty record_ids, default invalid actions to ``store``,
    and ensure every new record has a decision (missing -> store).
    """
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        array_match = re.search(r"\[[\s\S]*\]", cleaned)
        parsed = json.loads(array_match.group(0)) if array_match else []
        items = parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        items = []
    decisions: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            rid = str(item.get("record_id") or "").strip()
            if not rid:
                continue
            action = str(item.get("action") or "store")
            raw_tids = item.get("target_ids") or []
            tids = [str(t) for t in raw_tids] if isinstance(raw_tids, list) else []
            merged_type = item.get("merged_type")
            decisions[rid] = {
                "action": action if action in _VALID_ACTIONS else "store",
                "target_ids": tids,
                "merged_content": item.get("merged_content") if isinstance(item.get("merged_content"), str) else None,
                "merged_type": merged_type if isinstance(merged_type, str) and merged_type in RECORD_TYPES else None,
                "merged_confidence": item.get("merged_confidence") if isinstance(item.get("merged_confidence"), (int, float)) else None,
            }
        except (TypeError, ValueError):
            logger.warning("Malformed dedup decision item dropped: %r", item)
    for rid in new_ids:
        decisions.setdefault(rid, {"action": "store", "target_ids": []})
    return decisions


def apply_decision(
    records: list[dict[str, Any]],
    new_record: dict[str, Any],
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply a single dedup decision, returning the new records list.

    ``store``  -> append new. ``skip``   -> drop new (no delta).
    ``update`` -> replace target(s) with new (targets archived).
    ``merge``  -> archive targets, append new with lifted confidence/content.
    Truth-preserving: targets are archived, never deleted.
    """
    action = decision.get("action", "store")
    if action not in _VALID_ACTIONS:
        action = "store"
    target_ids = [str(t) for t in decision.get("target_ids") or []]

    if action == "store":
        return records + [new_record]

    if action == "skip":
        return list(records)

    target_set = set(target_ids)
    remaining = []
    for r in records:
        rid = str(r.get("id") or r.get("timestamp") or "")
        if rid in target_set:
            r["archived"] = True
            remaining.append(r)
            continue
        remaining.append(r)

    merged = dict(new_record)
    if action == "merge":
        mc = decision.get("merged_content")
        if mc:
            merged["session_summary"] = mc
        mconf = decision.get("merged_confidence")
        if isinstance(mconf, (int, float)):
            merged["confidence"] = mconf
        merged["merged_from"] = sorted(target_set)
    elif action == "update":
        mconf = decision.get("merged_confidence")
        if isinstance(mconf, (int, float)):
            merged["confidence"] = mconf
        merged["updated_from"] = sorted(target_set)
    return remaining + [merged]
