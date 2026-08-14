from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

_SECRET_FIELDS = {
    "api_key",
    "api_token",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+\-/]+=*", re.IGNORECASE)
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|api[_-]?token|password|secret|token)(\s*[=:]\s*)([^\s,;&]+)"
)
_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


def redact_secrets(value: Any) -> Any:
    """Return a copy safe for logs, API diagnostics, and model context."""

    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SECRET_FIELDS or normalized.endswith("_secret"):
                result[key] = "[REDACTED]" if item else item
            else:
                result[key] = redact_secrets(item)
        return result
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        result = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        result = _ASSIGNMENT_PATTERN.sub(r"\1\2[REDACTED]", result)
        return _KEY_PATTERN.sub("[REDACTED]", result)
    return deepcopy(value)


__all__ = ["redact_secrets"]
