"""Monotonic time and tool budgets for one teaching run."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import time
from typing import Any

from .models import TeachingRunPolicy
from .policy import _RETRIEVAL_TOOLS


@dataclass(frozen=True, slots=True)
class BudgetRejection:
    tool_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    tool_calls: int
    retrieval_calls: int
    elapsed_ms: int
    remaining_hard_ms: int

    def to_dict(self) -> dict[str, int]:
        return {
            "tool_calls": self.tool_calls,
            "retrieval_calls": self.retrieval_calls,
            "elapsed_ms": self.elapsed_ms,
            "remaining_hard_ms": self.remaining_hard_ms,
        }


class ToolBudget:
    def __init__(
        self,
        policy: TeachingRunPolicy,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy = policy
        self._clock = clock
        self._started_at = clock()
        self._tool_calls = 0
        self._retrieval_calls = 0

    @property
    def elapsed_ms(self) -> int:
        return max(0, int((self._clock() - self._started_at) * 1000))

    @property
    def soft_expired(self) -> bool:
        return self.elapsed_ms >= self.policy.soft_timeout_ms

    @property
    def hard_expired(self) -> bool:
        return self.elapsed_ms >= self.policy.hard_timeout_ms

    @property
    def remaining_hard_seconds(self) -> float:
        remaining_ms = max(0, self.policy.hard_timeout_ms - self.elapsed_ms)
        return remaining_ms / 1000

    def reserve_retrieval(self) -> bool:
        if self.hard_expired or self._retrieval_calls >= self.policy.max_retrieval_calls:
            return False
        self._retrieval_calls += 1
        return True

    def admit_tool_calls(
        self,
        tool_calls: Iterable[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[BudgetRejection]]:
        accepted: list[dict[str, Any]] = []
        rejected: list[BudgetRejection] = []
        allowed = frozenset(self.policy.allowed_tools)
        for call in tool_calls:
            item = dict(call)
            name = str(item.get("name") or "")
            if name not in allowed:
                rejected.append(BudgetRejection(name, "tool_not_allowed"))
                continue
            if self.hard_expired:
                rejected.append(BudgetRejection(name, "hard_timeout"))
                continue
            if self._tool_calls >= self.policy.max_tool_calls:
                rejected.append(BudgetRejection(name, "tool_budget_exhausted"))
                continue
            if name in _RETRIEVAL_TOOLS:
                if self._retrieval_calls >= self.policy.max_retrieval_calls:
                    rejected.append(BudgetRejection(name, "retrieval_budget_exhausted"))
                    continue
                self._retrieval_calls += 1
            self._tool_calls += 1
            accepted.append(item)
        return accepted, rejected

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            tool_calls=self._tool_calls,
            retrieval_calls=self._retrieval_calls,
            elapsed_ms=self.elapsed_ms,
            remaining_hard_ms=max(0, self.policy.hard_timeout_ms - self.elapsed_ms),
        )


__all__ = ["BudgetRejection", "BudgetSnapshot", "ToolBudget"]
