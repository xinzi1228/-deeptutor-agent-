from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deeptutor.services.annotation_attempts import AnnotationAttemptStore
from deeptutor.services.current_learning_task.store import CurrentLearningTaskStore


def _read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def _memory_summary(profile_root: Path) -> str:
    memory_root = profile_root / "memory"
    candidates = (memory_root / "recent.md", memory_root / "profile.md", memory_root / "L3.md")
    chunks: list[str] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if content:
            chunks.append(content[-1200:])
    return "\n".join(chunks)[:2400]


def build_annotation_coach_context(profile_root: Path) -> dict[str, Any]:
    """Return a small, explainable context window rather than raw history."""
    profile_root = Path(profile_root)
    attempts = AnnotationAttemptStore(profile_root)
    current_task = CurrentLearningTaskStore(profile_root).get()
    learning = _read_jsonl_tail(profile_root / "learning" / "records.jsonl", 20)
    confirmed_weaknesses: list[dict[str, Any]] = []
    for row in learning:
        pattern = row.get("error_pattern")
        if pattern and row.get("pattern_status") == "confirmed":
            confirmed_weaknesses.append({"pattern": pattern, "task_id": row.get("task_id", "")})
    compact_attempts = []
    for row in attempts.list_attempts(limit=5):
        compact_attempts.append({
            "task_id": row.get("task_id", ""),
            "task_type": row.get("task_type", ""),
            "mode": row.get("mode", ""),
            "metrics": row.get("metrics", {}),
            "created_at": row.get("created_at", ""),
        })
    return {
        "current": current_task.model_dump(mode="json") if current_task else attempts.current(),
        "annotation_projection": attempts.current(),
        "recent_attempts": compact_attempts,
        "confirmed_weaknesses": confirmed_weaknesses[-5:],
        "memory_summary": _memory_summary(profile_root),
        "context_policy": "默认仅提供当前任务、最近5次练习、确认的薄弱点与短记忆摘要；完整历史需用户明确要求。",
    }
