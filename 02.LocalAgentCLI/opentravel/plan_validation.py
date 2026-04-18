from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import ValidationResult


def validate_plan(plan: dict[str, Any]) -> ValidationResult:
    # 行程后校验：结构、时间、收尾、must-do 覆盖都在这里兜底。
    errors: list[str] = []
    errors.extend(_validate_top_level(plan))
    if errors:
        return ValidationResult(valid=False, errors=errors)

    days = plan["days"]
    must_do = plan["trip_summary"].get("must_do", [])

    seen_must_do_text: list[str] = []
    for day in days:
        day_errors = _validate_day(day)
        errors.extend(day_errors)

        for slot in day.get("slots", []):
            text = f"{slot.get('title', '')} {slot.get('details', '')}".lower()
            seen_must_do_text.append(text)

    errors.extend(_validate_must_do_coverage(must_do, seen_must_do_text))
    return ValidationResult(valid=(len(errors) == 0), errors=errors)


def _validate_top_level(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "trip_summary" not in plan:
        errors.append("Missing top-level key: trip_summary")
    if "days" not in plan:
        errors.append("Missing top-level key: days")
        return errors
    if not isinstance(plan["days"], list) or not plan["days"]:
        errors.append("days must be a non-empty list.")
    return errors


def _validate_day(day: dict[str, Any]) -> list[str]:
    # 每天至少要有 slot，且最后一个 slot 必须是 hotel。
    errors: list[str] = []
    for key in ["day", "date", "overnight_city", "slots"]:
        if key not in day:
            errors.append(f"Day object missing key: {key}")
            return errors

    if not isinstance(day["slots"], list) or not day["slots"]:
        errors.append(f"Day {day.get('day')} has no slots.")
        return errors

    last_slot = day["slots"][-1]
    if last_slot.get("type") != "hotel":
        errors.append(f"Day {day.get('day')} should end with a hotel slot.")

    errors.extend(_validate_slot_order(day))
    return errors


def _validate_slot_order(day: dict[str, Any]) -> list[str]:
    # 校验 slot 时间合法性和相互重叠问题。
    errors: list[str] = []
    intervals: list[tuple[datetime, datetime, int]] = []

    for slot in day["slots"]:
        slot_id = slot.get("slot_id", -1)
        for field in [
            "slot_id",
            "type",
            "time_start",
            "time_end",
            "title",
            "location",
            "details",
            "estimated_cost_cny",
            "rationale",
        ]:
            if field not in slot:
                errors.append(
                    f"Day {day.get('day')} slot {slot_id} missing field: {field}"
                )
                continue

        try:
            start = datetime.strptime(slot["time_start"], "%H:%M")
            end = datetime.strptime(slot["time_end"], "%H:%M")
        except Exception:
            errors.append(
                f"Day {day.get('day')} slot {slot_id} time format must be HH:MM."
            )
            continue
        if end <= start:
            errors.append(
                f"Day {day.get('day')} slot {slot_id} has invalid time range."
            )
            continue
        intervals.append((start, end, slot_id))

    intervals.sort(key=lambda x: x[0])
    for i in range(1, len(intervals)):
        prev_start, prev_end, prev_id = intervals[i - 1]
        curr_start, curr_end, curr_id = intervals[i]
        if curr_start < prev_end:
            errors.append(
                f"Day {day.get('day')} slot overlap between {prev_id} and {curr_id}."
            )
        if prev_start == curr_start and prev_end == curr_end:
            errors.append(
                f"Day {day.get('day')} slots {prev_id}/{curr_id} duplicate interval."
            )
    return errors


def _validate_must_do_coverage(
    must_do: list[str],
    seen_texts: list[str],
) -> list[str]:
    # must-do 是用户核心诉求，必须在最终行程里被覆盖到。
    errors: list[str] = []
    merged = " ".join(seen_texts)
    for item in must_do:
        keyword = item.lower().strip()
        if not keyword:
            continue
        if _item_covered(keyword, merged):
            continue
        errors.append(f"Must-do item not covered in plan: {item}")
    return errors


def _item_covered(item: str, merged_text: str) -> bool:
    # 做一个轻量级的文本匹配，避免同义表达导致误判。
    if item in merged_text:
        return True

    tokens = [tok.strip() for tok in item.replace("-", " ").split() if tok.strip()]
    meaningful = [tok for tok in tokens if len(tok) >= 4]
    if not meaningful:
        meaningful = tokens

    for tok in meaningful:
        candidates = {tok}
        if tok.endswith("ing") and len(tok) > 5:
            candidates.add(tok[:-3])
        if tok.endswith("ed") and len(tok) > 4:
            candidates.add(tok[:-2])
        for c in candidates:
            if c and c in merged_text:
                return True
    return False
