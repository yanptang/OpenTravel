from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REQUIRED_REQUEST_FIELDS = [
    "origin_city",
    "destination",
    "start_date",
    "end_date",
    "arrival_mode",
    "travelers",
    "transport_mode",
    "must_do",
]

EDITABLE_SLOT_FIELDS = {
    "type",
    "time_start",
    "time_end",
    "title",
    "location",
    "details",
    "estimated_cost_cny",
    "rationale",
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class PlannerConfig:
    use_llm: bool = True
    model: str = "ollama/qwen3.5:4b"
    api_base: str = "http://localhost:11434"
    planner_mode: str = "daily"
    preferred_language: str = "auto"
    temperature: float = 0.2
    max_tokens: int = 4096
    request_timeout_sec: int = 900
    refine_retries: int = 2


def ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object.")
    return value
