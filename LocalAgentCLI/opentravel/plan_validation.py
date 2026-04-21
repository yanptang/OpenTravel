#初步攻略的校验
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .models import ValidationResult


def validate_plan(plan: dict[str, Any]) -> ValidationResult:
    # 行程后校验：结构、时间、收尾、衔接、must-do 覆盖都在这里兜底。
    errors: list[str] = []
    errors.extend(_validate_top_level(plan))
    if errors:
        return ValidationResult(valid=False, errors=errors)

    days = plan["days"]
    must_do = plan["trip_summary"].get("must_do", [])

    seen_must_do_text: list[str] = []
    previous_overnight_city: str | None = None
    for idx, day in enumerate(days):
        day_errors = _validate_day(
            day,
            is_last_day=(idx == len(days) - 1),
            previous_overnight_city=previous_overnight_city,
        )
        errors.extend(day_errors)

        for slot in day.get("slots", []):
            text = f"{slot.get('title', '')} {slot.get('details', '')}".lower()
            seen_must_do_text.append(text)

        overnight_city = str(day.get("overnight_city", "")).strip()
        if overnight_city:
            previous_overnight_city = overnight_city

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


def _validate_day(
    day: dict[str, Any],
    is_last_day: bool,
    previous_overnight_city: str | None = None,
) -> list[str]:
    errors: list[str] = []
    for key in ["day", "date", "overnight_city", "slots"]:
        if key not in day:
            errors.append(f"Day object missing key: {key}")
            return errors

    if not isinstance(day["slots"], list) or not day["slots"]:
        errors.append(f"Day {day.get('day')} has no slots.")
        return errors

    if not is_last_day:
        hotel_slots = [slot for slot in day["slots"] if slot.get("type") == "hotel"]
        if len(hotel_slots) == 0:
            errors.append(f"Day {day.get('day')} should include at least one hotel slot.")

    errors.extend(
        _validate_transport_continuity(
            day,
            previous_overnight_city=previous_overnight_city,
        )
    )
    errors.extend(_validate_slot_order(day))
    return errors


def _validate_transport_continuity(
    day: dict[str, Any],
    previous_overnight_city: str | None,
) -> list[str]:
    errors: list[str] = []
    slots = day.get("slots", [])
    if not slots:
        return errors

    previous_slot: dict[str, Any] | None = None
    for idx, slot in enumerate(slots):
        if slot.get("type") != "transport":
            previous_slot = slot
            continue

        if not _transport_has_route_language(slot):
            errors.append(
                f"Day {day.get('day')} slot {slot.get('slot_id', -1)} transport needs a clear origin and destination."
            )

        if idx == 0:
            if previous_overnight_city and not _transport_mentions_previous_context(
                slot, previous_overnight_city
            ):
                errors.append(
                    f"Day {day.get('day')} slot {slot.get('slot_id', -1)} should connect from previous overnight location: {previous_overnight_city}."
                )
        elif previous_slot is not None:
            if not _transport_mentions_previous_slot(slot, previous_slot):
                errors.append(
                    f"Day {day.get('day')} slot {slot.get('slot_id', -1)} should clearly connect from the previous stop."
                )

        previous_slot = slot

    return errors


def _validate_slot_order(day: dict[str, Any]) -> list[str]:
    # 检查 slot 时间合法性和相互重叠问题。
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

    for suffix in ["美食", "午餐", "晚餐", "酒店", "住宿", "打卡", "游玩", "游览", "用餐"]:
        if item.endswith(suffix) and len(item) > len(suffix):
            prefix = item[: -len(suffix)].strip()
            if prefix and prefix in merged_text:
                return True

    if len(item) >= 4:
        prefix = item[:3]
        if prefix and prefix in merged_text:
            return True
    return False


def _transport_has_route_language(slot: dict[str, Any]) -> bool:
    text = " ".join(
        str(slot.get(field, ""))
        for field in ["title", "location", "details"]
    ).replace(" ", "")
    route_markers = ["->", "从", "前往", "返回", "抵达", "离开", "到", "至", "赴"]
    return any(marker.replace(" ", "") in text for marker in route_markers)


def _transport_mentions_previous_context(
    slot: dict[str, Any],
    previous_overnight_city: str,
) -> bool:
    text = " ".join(
        str(slot.get(field, ""))
        for field in ["title", "location", "details"]
    ).replace(" ", "")
    if not previous_overnight_city:
        return False
    context_markers = [
        previous_overnight_city,
        "酒店",
        "住宿",
        "住处",
        "前一晚",
        "前一天",
    ]
    return any(marker.replace(" ", "") in text for marker in context_markers)


def _transport_mentions_previous_slot(
    slot: dict[str, Any],
    previous_slot: dict[str, Any],
) -> bool:
    text = " ".join(
        str(slot.get(field, ""))
        for field in ["title", "location", "details"]
    ).replace(" ", "")
    previous_text = " ".join(
        str(previous_slot.get(field, ""))
        for field in ["title", "location", "details"]
    ).replace(" ", "")
    if not previous_text:
        return False
    markers = _text_keywords(previous_text)
    markers.extend(_text_keywords(str(previous_slot.get("location", ""))))
    markers.extend(_text_keywords(str(previous_slot.get("title", ""))))
    return any(marker and marker in text for marker in markers)


def _text_keywords(text: str) -> list[str]:
    keywords: list[str] = []
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", text):
        keywords.append(chunk)
    if not keywords and len(text) >= 3:
        keywords.append(text[:3])
    return keywords
