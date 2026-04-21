from __future__ import annotations

import json
from typing import Any

from .llm_client import generate_with_model
from .models import PlannerConfig
from .prompt_loader import render_prompt


def refine_plan(
    request: dict[str, Any],
    current_plan: dict[str, Any],
    errors: list[str],
    config: PlannerConfig,
) -> dict[str, Any] | None:
    if not config.use_llm:
        return None

    system_prompt = render_prompt("system/refiner.txt")
    user_prompt = render_prompt(
        "user/refiner.txt",
        request_json=json.dumps(request, ensure_ascii=False, indent=2),
        errors_json=json.dumps(errors, ensure_ascii=False, indent=2),
        current_plan_json=json.dumps(current_plan, ensure_ascii=False, indent=2),
    )

    return generate_with_model(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
        temperature=0.1,
        max_tokens=config.max_tokens,
        expect_json=True,
    )
