from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MetricName = Literal[
    "cold_start_interactive",
    "route_visible",
    "progress_core_visible",
    "chat_status_visible",
    "chat_first_token",
    "annotation_task_visible",
    "annotation_mode_switch",
]
MetricOutcome = Literal["success", "error", "cancelled", "timeout"]
MetricErrorType = Literal[
    "",
    "network",
    "timeout",
    "cancelled",
    "server",
    "validation",
    "permission",
    "unknown",
]


class PerformanceMetricInput(BaseModel):
    """Strict client contract that cannot carry learning content or identifiers."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: MetricName
    route: str = Field(min_length=1, max_length=120)
    duration_ms: float = Field(ge=0, le=600_000)
    outcome: MetricOutcome = "success"
    stage: str = Field(default="", max_length=60, pattern=r"^[\w.-]*$")
    tool_calls: int = Field(default=0, ge=0, le=100)
    error_type: MetricErrorType = ""
    build_version: str = Field(default="", max_length=80, pattern=r"^[\w.-]*$")

    @field_validator("route")
    @classmethod
    def normalize_route(cls, value: str) -> str:
        route = value.split("?", 1)[0].split("#", 1)[0]
        if not route.startswith("/") or route.startswith("//"):
            raise ValueError("route must be an application path")
        return route
