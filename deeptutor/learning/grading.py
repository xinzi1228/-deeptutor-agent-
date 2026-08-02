"""Deterministic answer grading + coarse error classification for Mastery Path."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeptutor.learning.models import ErrorType


def grade_answer(user_answer: str, expected_answer: str, question_type: str = "short") -> bool:
    """Grade user answer against expected answer.

    Args:
        user_answer: The user's submitted answer.
        expected_answer: The stored expected answer.
        question_type: One of "choice", "short", "open", "tf", "standard",
            "error_case".

    Returns:
        True if answer is correct.
    """
    user = user_answer.strip().lower()
    expected = expected_answer.strip().lower()

    if not expected:
        return False

    if question_type == "choice":
        user_norm = user.replace(" ", "")
        expected_norm = expected.replace(" ", "")
        return user_norm == expected_norm

    if question_type == "short":
        if user == expected:
            return True
        if len(expected) <= 30:
            return SequenceMatcher(None, user, expected).ratio() >= 0.85
        return False

    if question_type == "open":
        keywords = [k.strip() for k in re.split(r"[,;，；。\n]+", expected) if k.strip()]
        if not keywords:
            return False
        matched = sum(1 for kw in keywords if kw in user)
        return matched / len(keywords) >= 0.6

    if question_type == "tf":
        truthy = {"对", "正确", "true", "t", "yes", "是", "1"}
        falsy = {"错", "错误", "false", "f", "no", "否", "0"}
        if user in truthy:
            return expected in truthy
        if user in falsy:
            return expected in falsy
        return False

    if question_type == "standard":
        import json

        try:
            spec = json.loads(expected_answer)
            answer_obj = json.loads(user_answer)
        except json.JSONDecodeError:
            return False
        required = spec.get("required_fields", [])
        labels = spec.get("labels", [])
        if isinstance(answer_obj, dict):
            if any(f not in answer_obj for f in required):
                return False
            if labels and answer_obj.get("label") not in labels:
                return False
            return True
        return False

    if question_type == "error_case":
        import json

        try:
            spec = json.loads(expected_answer)
            expected_errors = sorted(spec.get("errors", []))
            user_norm = user_answer.replace("[", "").replace("]", "")
            answer_errors = sorted(int(x) for x in user_norm.split(",") if x.strip())
        except (json.JSONDecodeError, ValueError):
            return False
        return answer_errors == expected_errors

    return False


def classify_error(user_answer: str) -> ErrorType:
    """Coarse error classification for a wrong answer.

    A blank answer signals the student did not know (metacognitive); anything
    else is treated as a wrong application. The richer four-type taxonomy is
    assigned later by the LLM in the error-diagnosis stage.
    """
    from deeptutor.learning.models import ErrorType

    return ErrorType.METACOGNITIVE if not user_answer.strip() else ErrorType.APPLICATION_ERROR


__all__ = ["grade_answer", "classify_error"]
