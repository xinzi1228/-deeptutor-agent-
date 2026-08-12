from __future__ import annotations

import re

from deeptutor.services.auth import hash_password, verify_password

PIN_PATTERN = re.compile(r"^\d{4,12}$")
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 10


def validate_pin(pin: str) -> str:
    value = str(pin).strip()
    if not PIN_PATTERN.fullmatch(value):
        raise ValueError("PIN 必须是 4 到 12 位数字")
    return value


def hash_pin(pin: str) -> str:
    return hash_password(validate_pin(pin))


def verify_pin(pin: str, hashed: str) -> bool:
    try:
        value = validate_pin(pin)
    except ValueError:
        return False
    return bool(hashed) and verify_password(value, hashed)
