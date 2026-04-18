from __future__ import annotations

from typing import Any

from .models import EDITABLE_SLOT_FIELDS
from .plan_validation import validate_plan
from .renderer import render_text


HELP = """
Commands:
  help
  show
  show day <n>
  delete <day> <slot_id>
  set <day> <slot_id> <field> <value>
  done
"""


def edit_plan_interactively(plan: dict[str, Any]) -> dict[str, Any]:
    print("\nEnter interactive edit mode. Type 'help' for commands.\n")
    while True:
        cmd = input("edit> ").strip()
        if not cmd:
            continue
        if cmd == "help":
            print(HELP)
            continue
        if cmd == "show":
            print(render_text(plan))
            continue
        if cmd.startswith("show day "):
            _show_day(plan, cmd)
            continue
        if cmd.startswith("delete "):
            _delete_slot(plan, cmd)
            _print_validation(plan)
            continue
        if cmd.startswith("set "):
            _set_slot(plan, cmd)
            _print_validation(plan)
            continue
        if cmd == "done":
            return plan
        print("Unknown command. Type 'help'.")


def _show_day(plan: dict[str, Any], cmd: str) -> None:
    parts = cmd.split()
    if len(parts) != 3:
        print("Usage: show day <n>")
        return
    day_idx = _parse_int(parts[2], "day")
    if day_idx is None:
        return
    day = _get_day(plan, day_idx)
    if day is None:
        return
    print(f"Day {day['day']} ({day['date']}) | Overnight: {day['overnight_city']}")
    for slot in day["slots"]:
        print(
            f"  [{slot['slot_id']}] {slot['time_start']}-{slot['time_end']} "
            f"{slot['type']}: {slot['title']} @ {slot['location']}"
        )


def _delete_slot(plan: dict[str, Any], cmd: str) -> None:
    parts = cmd.split()
    if len(parts) != 3:
        print("Usage: delete <day> <slot_id>")
        return

    day_idx = _parse_int(parts[1], "day")
    slot_id = _parse_int(parts[2], "slot_id")
    if day_idx is None or slot_id is None:
        return

    day = _get_day(plan, day_idx)
    if day is None:
        return

    before = len(day["slots"])
    day["slots"] = [s for s in day["slots"] if int(s.get("slot_id", -1)) != slot_id]
    if len(day["slots"]) == before:
        print("No matching slot.")
        return
    _renumber_slots(day)
    print(f"Deleted slot {slot_id} from day {day_idx}.")


def _set_slot(plan: dict[str, Any], cmd: str) -> None:
    parts = cmd.split(maxsplit=4)
    if len(parts) != 5:
        print("Usage: set <day> <slot_id> <field> <value>")
        return

    day_idx = _parse_int(parts[1], "day")
    slot_id = _parse_int(parts[2], "slot_id")
    field = parts[3]
    value = parts[4]
    if day_idx is None or slot_id is None:
        return
    if field not in EDITABLE_SLOT_FIELDS:
        print(f"Unsupported field: {field}")
        return

    day = _get_day(plan, day_idx)
    if day is None:
        return

    for slot in day["slots"]:
        if int(slot.get("slot_id", -1)) == slot_id:
            if field == "estimated_cost_cny":
                slot[field] = _parse_int(value, "estimated_cost_cny")
            else:
                slot[field] = value
            print(f"Updated day {day_idx} slot {slot_id} field {field}.")
            return
    print("No matching slot.")


def _print_validation(plan: dict[str, Any]) -> None:
    result = validate_plan(plan)
    if result.valid:
        print("Validation: PASS")
    else:
        print("Validation: FAIL")
        for err in result.errors:
            print(f"- {err}")


def _get_day(plan: dict[str, Any], day_idx: int) -> dict[str, Any] | None:
    for day in plan["days"]:
        if int(day.get("day", -1)) == day_idx:
            return day
    print(f"Day {day_idx} not found.")
    return None


def _renumber_slots(day: dict[str, Any]) -> None:
    for idx, slot in enumerate(day["slots"], start=1):
        slot["slot_id"] = idx


def _parse_int(value: str, label: str) -> int | None:
    try:
        return int(value)
    except Exception:
        print(f"{label} must be integer.")
        return None

