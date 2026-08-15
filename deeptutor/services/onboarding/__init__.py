"""Resumable onboarding state machine for the admin first-run wizard.

Fixed-order steps (账号安全 → 对话模型 → Embedding → 知识库 → Label Studio →
完整体检) plus optional steps (生图 / MCP / Skill). Every step keeps a
persistent status and can be skipped, resumed, or retested; when a dependency
config changes the affected result degrades to ``stale`` instead of pretending
the earlier verification still holds.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Literal

from deeptutor.services.file_io import atomic_write_json

OnboardingStepStatus = Literal[
    "not_started", "running", "passed", "failed", "skipped", "stale"
]
OnboardingAction = Literal["done", "skip", "resume", "retest", "dismiss"]

# Fixed order of the core wizard (design spec §4). Index order is meaningful:
# the wizard resumes at the first step that is not passed/skipped.
CORE_STEPS: tuple[tuple[str, str], ...] = (
    ("account_security", "账号安全"),
    ("llm", "对话模型"),
    ("embedding", "Embedding"),
    ("knowledge_base", "知识库"),
    ("label_studio", "Label Studio"),
    ("health_check", "完整体检"),
)
OPTIONAL_STEPS: tuple[tuple[str, str], ...] = (
    ("imagegen", "生图"),
    ("mcp", "MCP"),
    ("skill", "Skill"),
)
STEP_LABELS: dict[str, str] = dict(CORE_STEPS + OPTIONAL_STEPS)
ALL_STEP_KEYS: tuple[str, ...] = tuple(STEP_LABELS.keys())
TERMINAL_STATUSES: frozenset[str] = frozenset({"passed", "skipped"})

# Legacy 7-step wizard used before the state machine (kept only for mapping old
# saved "completed"/"skipped" integer lists onto the new core steps).
_LEGACY_STEP_KEYS: tuple[str, ...] = (
    "account_security", "llm", "embedding", "knowledge_base",
    "label_studio", "health_check", "health_check",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(value)).lower()
    return cleaned or "empty"


def default_state() -> dict[str, Any]:
    return {
        "version": 2,
        "dismissed": False,
        "updated_at": "",
        "steps": {key: _default_step() for key in ALL_STEP_KEYS},
    }


def _default_step() -> dict[str, Any]:
    return {"status": "not_started", "updated_at": "", "detail": "", "fingerprint": ""}


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def current_step(state: dict[str, Any]) -> str:
    """First core step (in fixed order) that is not passed/skipped."""
    steps = state.get("steps", {})
    for key, _label in CORE_STEPS:
        status = steps.get(key, {}).get("status", "not_started")
        if not is_terminal(status):
            return key
    return CORE_STEPS[-1][0]


def completed_steps(state: dict[str, Any]) -> list[str]:
    steps = state.get("steps", {})
    return [key for key in ALL_STEP_KEYS if steps.get(key, {}).get("status") == "passed"]


def skipped_steps(state: dict[str, Any]) -> list[str]:
    steps = state.get("steps", {})
    return [key for key in ALL_STEP_KEYS if steps.get(key, {}).get("status") == "skipped"]


def apply_action(
    state: dict[str, Any],
    step_key: str,
    action: OnboardingAction,
    *,
    detail: str = "",
    fingerprint: str = "",
) -> dict[str, Any]:
    """Apply one wizard action to a step. Pure state transition, no I/O.

    ``done`` records the live config fingerprint so later reads can detect
    staleness; ``retest`` clears the fingerprint and moves the step back to
    ``running``; ``dismiss`` hides the wizard banner globally.
    """
    steps = dict(state.get("steps", {}))
    if step_key not in steps:
        raise ValueError(f"未知的初始化步骤：{step_key}")
    step = dict(steps[step_key])
    ts = now_iso()
    if action == "done":
        step.update({"status": "passed", "updated_at": ts, "detail": detail, "fingerprint": fingerprint})
    elif action == "skip":
        step.update({"status": "skipped", "updated_at": ts, "detail": detail})
    elif action == "resume":
        step.update({"status": "running", "updated_at": ts, "detail": detail})
    elif action == "retest":
        step.update({"status": "running", "updated_at": ts, "detail": detail, "fingerprint": ""})
    elif action == "dismiss":
        next_state = {**state, "dismissed": True, "updated_at": ts}
        return next_state
    else:
        raise ValueError(f"未知的初始化动作：{action}")
    steps[step_key] = step
    return {**state, "steps": steps, "updated_at": ts}


def mark_stale(
    state: dict[str, Any],
    live_fingerprints: dict[str, str],
) -> dict[str, Any]:
    """Degrade passed steps whose dependency config changed to ``stale``.

    A step whose stored fingerprint is empty cannot be checked and is left
    alone; only steps that recorded a fingerprint during ``done`` are verified.
    """
    steps = dict(state.get("steps", {}))
    changed = False
    for key, stored in steps.items():
        if stored.get("status") != "passed":
            continue
        recorded = stored.get("fingerprint") or ""
        if not recorded:
            continue
        live = live_fingerprints.get(key)
        if live and live != recorded:
            updated = dict(stored)
            updated["status"] = "stale"
            updated["detail"] = "依赖配置已变化，请重新验证"
            steps[key] = updated
            changed = True
    if not changed:
        return state
    return {**state, "steps": steps, "updated_at": now_iso()}


def legacy_int_to_key(index: int) -> str:
    """Map a legacy 1-based wizard step number to a new core step key."""
    idx = max(1, min(len(_LEGACY_STEP_KEYS), int(index)))
    return _LEGACY_STEP_KEYS[idx - 1]


def fingerprint(*parts: str) -> str:
    joined = "|".join(_slugify(part) for part in parts if part is not None)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def load_state(path) -> dict[str, Any]:
    default = default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(raw, dict):
        return default
    version = raw.get("version")
    if version != 2:
        return migrate_legacy(raw)
    steps = {
        key: {**_default_step(), **(raw.get("steps", {}).get(key) or {})}
        for key in ALL_STEP_KEYS
    }
    return {
        "version": 2,
        "dismissed": bool(raw.get("dismissed", False)),
        "updated_at": str(raw.get("updated_at", "")),
        "steps": steps,
    }


def migrate_legacy(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade the v1 ``{step, completed, skipped, dismissed}`` shape."""
    state = default_state()
    state["dismissed"] = bool(raw.get("dismissed", False))
    for number in raw.get("completed", []) or []:
        state = apply_action(state, legacy_int_to_key(number), "done")
    for number in raw.get("skipped", []) or []:
        state = apply_action(state, legacy_int_to_key(number), "skip")
    state["updated_at"] = now_iso()
    return state


def save_state(path, state: dict[str, Any]) -> None:
    atomic_write_json(path, state)
