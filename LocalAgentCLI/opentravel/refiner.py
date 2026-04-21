from __future__ import annotations

import json
import re
from copy import deepcopy
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
        return current_plan

    plan = deepcopy(current_plan)
    affected_days = _extract_affected_days(errors)
    if not affected_days:
        return current_plan

    for day_no in affected_days:
        if _find_day(plan, day_no) is None:
            continue
        day_errors = [err for err in errors if f"Day {day_no}" in err]
        if not day_errors:
            continue
        for error in day_errors:
            day = _find_day(plan, day_no)
            if day is None:
                break
            repaired_day = _refine_single_issue(
                request=request,
                plan=plan,
                target_day=day,
                error=error,
                config=config,
            )
            if repaired_day is not None:
                _replace_day(plan, day_no, repaired_day)

    return plan


def _refine_single_issue(
    *,
    request: dict[str, Any],
    plan: dict[str, Any],
    target_day: dict[str, Any],
    error: str,
    config: PlannerConfig,
) -> dict[str, Any] | None:
    payload = _build_issue_repair_payload(request=request, plan=plan, target_day=target_day, error=error)
    system_prompt = render_prompt("system/day_refiner.txt")
    user_prompt = render_prompt(
        "user/day_refiner.txt",
        repair_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    result = generate_with_model(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
        temperature=0.1,
        max_tokens=min(config.max_tokens, 2200),
        expect_json=True,
    )
    if not result:
        return None

    day = _normalize_day_result(target_day, result)
    if _day_changed(target_day, day):
        return day
    return None


def _build_issue_repair_payload(
    *,
    request: dict[str, Any],
    plan: dict[str, Any],
    target_day: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    day_no = _safe_int(target_day.get("day"), 0)
    issue_type = _classify_error(error)
    issue_hint = _issue_hint(target_day, error, issue_type)
    return {
        "request_summary": {
            "origin_city": request.get("origin_city", ""),
            "destination": request.get("destination", ""),
            "start_date": request.get("start_date", ""),
            "end_date": request.get("end_date", ""),
            "arrival_mode": request.get("arrival_mode", ""),
            "transport_mode": request.get("transport_mode", ""),
            "budget_level": request.get("budget_level", ""),
            "must_do": request.get("must_do", []),
        },
        "target_day": _day_brief(target_day),
        "primary_issue": {
            "error": error,
            "issue_type": issue_type,
            "focus_slot": _focus_slot_for_issue(target_day, error),
            "issue_hint": issue_hint,
        },
        "day_errors": [error],
        "prev_day": _day_brief(_find_day(plan, day_no - 1)) if day_no > 1 else {},
        "next_day": _day_brief(_find_day(plan, day_no + 1)),
        "neighbor_slots": {
            "previous": _neighbor_slot(target_day, -1),
            "current": [_slot_brief(slot) for slot in _slots(target_day)],
            "next": _neighbor_slot(target_day, 1),
        },
    }


def _normalize_day_result(scaffold_day: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "day": scaffold_day.get("day"),
        "date": scaffold_day.get("date"),
        "overnight_city": result.get("overnight_city", scaffold_day.get("overnight_city", "")),
        "slots": result.get("slots", scaffold_day.get("slots", [])),
    }
    if not isinstance(normalized["slots"], list) or not normalized["slots"]:
        normalized["slots"] = scaffold_day.get("slots", [])

    for idx, slot in enumerate(normalized["slots"], start=1):
        if isinstance(slot, dict):
            slot["slot_id"] = idx
    return normalized


def _extract_affected_days(errors: list[str]) -> list[int]:
    days: list[int] = []
    for error in errors:
        match = re.search(r"Day\s+(\d+)", error, re.IGNORECASE)
        if not match:
            continue
        day_no = _safe_int(match.group(1), None)
        if day_no is not None and day_no not in days:
            days.append(day_no)
    return sorted(days)


def _find_day(plan: dict[str, Any], day_no: int) -> dict[str, Any] | None:
    days = plan.get("days", [])
    if not isinstance(days, list):
        return None
    for day in days:
        if _safe_int(day.get("day"), -1) == day_no:
            return day
    return None


def _replace_day(plan: dict[str, Any], day_no: int, new_day: dict[str, Any]) -> None:
    days = plan.get("days", [])
    if not isinstance(days, list):
        return
    for idx, day in enumerate(days):
        if _safe_int(day.get("day"), -1) == day_no:
            days[idx] = new_day
            return


def _day_brief(day: dict[str, Any] | None) -> dict[str, Any]:
    if not day:
        return {}
    slots = _slots(day)
    return {
        "day": day.get("day", ""),
        "date": day.get("date", ""),
        "overnight_city": day.get("overnight_city", ""),
        "slot_count": len(slots),
        "slot_titles": [str(slot.get("title", "")).strip() for slot in slots if str(slot.get("title", "")).strip()][:5],
    }


def _classify_error(error: str) -> str:
    lowered = error.lower()
    if "hotel slot" in lowered:
        return "hotel"
    if "transport" in lowered or "connect" in lowered:
        return "transport"
    if "must-do" in lowered:
        return "must_do"
    if "time" in lowered or "overlap" in lowered:
        return "time"
    return "general"


def _extract_slot_id(error: str) -> int | None:
    match = re.search(r"slot\s+(\d+)", error, re.IGNORECASE)
    if not match:
        return None
    return _safe_int(match.group(1), None)


def _focus_slot_for_issue(day: dict[str, Any], error: str) -> dict[str, Any] | str:
    slot_id = _extract_slot_id(error)
    slot = _find_slot(day, slot_id)
    if slot is not None:
        return _slot_brief(slot)
    slots = _slots(day)
    if not slots:
        return ""
    issue_type = _classify_error(error)
    if issue_type == "hotel":
        for candidate in slots:
            if candidate.get("type") == "hotel":
                return _slot_brief(candidate)
    if issue_type == "must_do":
        for candidate in slots:
            if candidate.get("type") in {"activity", "meal", "transport"}:
                return _slot_brief(candidate)
    if issue_type == "transport":
        for candidate in slots:
            if candidate.get("type") == "transport":
                return _slot_brief(candidate)
    return _slot_brief(slots[0])


def _issue_hint(
    day: dict[str, Any],
    error: str,
    issue_type: str,
) -> dict[str, Any]:
    slots = _slots(day)
    if issue_type == "hotel":
        hotel_slots = [
            _slot_brief(slot)
            for slot in slots
            if slot.get("type") == "hotel"
        ]
        return {
            "hotel_slots": hotel_slots,
            "goal": "Leave only the hotel arrangement that best fits this day, and make the day pass validation.",
        }
    if issue_type == "must_do":
        item = error.split(":", 1)[-1].strip() if ":" in error else error
        return {
            "must_do_item": item,
            "candidate_slots": [
                _slot_brief(slot)
                for slot in slots
                if slot.get("type") in {"activity", "meal", "transport"}
            ],
            "goal": "Make the must-do item explicit in one relevant slot's title or details.",
        }
    if issue_type == "transport":
        slot_id = _extract_slot_id(error)
        current = _find_slot(day, slot_id)
        return {
            "current_transport": _slot_brief(current) if current else "",
            "previous_slot": _slot_brief(_find_slot(day, slot_id - 1)) if slot_id and _find_slot(day, slot_id - 1) else "",
            "next_slot": _slot_brief(_find_slot(day, slot_id + 1)) if slot_id and _find_slot(day, slot_id + 1) else "",
            "goal": "Make the transport route explicit with clear origin and destination, and ensure it connects to nearby slots.",
        }
    return {
        "candidate_slots": [_slot_brief(slot) for slot in slots[:4]],
        "goal": "Fix the issue in a minimal but visible way.",
    }


def _slots(day: dict[str, Any]) -> list[dict[str, Any]]:
    slots = day.get("slots", [])
    if isinstance(slots, list):
        return [slot for slot in slots if isinstance(slot, dict)]
    return []


def _find_slot(day: dict[str, Any], slot_id: int | None) -> dict[str, Any] | None:
    if slot_id is None:
        return None
    for slot in _slots(day):
        if _safe_int(slot.get("slot_id"), -1) == slot_id:
            return slot
    return None


def _slot_brief(slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot_id": slot.get("slot_id", ""),
        "type": slot.get("type", ""),
        "time_start": slot.get("time_start", ""),
        "time_end": slot.get("time_end", ""),
        "title": slot.get("title", ""),
        "location": slot.get("location", ""),
        "details": slot.get("details", ""),
        "estimated_cost_cny": slot.get("estimated_cost_cny", ""),
        "rationale": slot.get("rationale", ""),
    }


def _neighbor_slot(day: dict[str, Any], offset: int) -> dict[str, Any] | str:
    slots = _slots(day)
    if not slots:
        return ""
    if offset < 0:
        target_index = max(0, len(slots) - 2)
    else:
        target_index = min(len(slots) - 1, 1)
    return _slot_brief(slots[target_index])


def _day_changed(before: dict[str, Any], after: dict[str, Any]) -> bool:
    before_slots = before.get("slots", [])
    after_slots = after.get("slots", [])
    return json.dumps(before_slots, ensure_ascii=False, sort_keys=True) != json.dumps(after_slots, ensure_ascii=False, sort_keys=True)


def _safe_int(value: Any, default: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
