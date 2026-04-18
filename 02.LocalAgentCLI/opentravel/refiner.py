from __future__ import annotations

import json
from typing import Any

from .llm_client import generate_with_model
from .models import PlannerConfig


def refine_plan(
    request: dict[str, Any],
    current_plan: dict[str, Any],
    errors: list[str],
    config: PlannerConfig,
) -> dict[str, Any] | None:
    if not config.use_llm:
        return None

    system_prompt = (
        "You are a strict JSON travel itinerary fixer. "
        "Return only valid JSON and preserve user intent."
    )
    user_prompt = (
        "Fix this itinerary JSON according to these validation errors.\n"
        "Only modify what is necessary. Keep day-by-day structure.\n"
        f"Request:\n{json.dumps(request, ensure_ascii=False, indent=2)}\n\n"
        f"Validation errors:\n{json.dumps(errors, ensure_ascii=False, indent=2)}\n\n"
        f"Current plan:\n{json.dumps(current_plan, ensure_ascii=False, indent=2)}\n"
    )

    return generate_with_model(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
        temperature=0.1,
        max_tokens=config.max_tokens,
        expect_json=True,
    )
