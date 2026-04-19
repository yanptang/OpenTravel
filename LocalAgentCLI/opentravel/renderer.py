from __future__ import annotations

from typing import Any


def render_text(plan: dict[str, Any], language: str = "zh") -> str:
    return _render_plain_text(plan, language=language)


def render_markdown(plan: dict[str, Any], language: str = "zh") -> str:
    summary = plan["trip_summary"]
    lines: list[str] = []
    labels = _labels(language)
    transport_mode = _summary_value_label("transport_mode", summary["transport_mode"], language)
    budget_level = _summary_value_label("budget_level", summary["budget_level"], language)

    lines.append(f"# {labels['title']}")
    lines.append("")
    lines.append(
        f"**{summary['destination']}** | {summary['start_date']} {labels['range_sep']} {summary['end_date']}"
    )
    lines.append(
        f"{labels['travelers']}: {summary['travelers']} | "
        f"{labels['mode']}: {transport_mode} | "
        f"{labels['budget']}: {budget_level}"
    )
    lines.append(f"**{labels['must_do']}**: " + ", ".join(summary.get("must_do", [])))
    lines.append("")

    total_cost = 0
    for day in plan["days"]:
        day_label = f"{labels['day']} {day['day']} {labels['day_suffix']}"
        lines.append(f"## {day_label} ({day['date']})")
        lines.append(f"**{labels['overnight']}**: {day['overnight_city']}")
        lines.append("")
        for slot in day["slots"]:
            cost = int(slot.get("estimated_cost_cny", 0))
            total_cost += cost
            slot_type = _slot_type_label(slot["type"], language)
            lines.append(
                f"- **[{slot['slot_id']}] {slot['time_start']}-{slot['time_end']} "
                f"{slot_type}**: {slot['title']} {labels['at']} {slot['location']} "
                f"({labels['currency']} {cost})"
            )
            lines.append(f"  - {slot['details']}")
        lines.append("")
    lines.append(f"**{labels['total_cost']}**: {labels['currency']} {total_cost}")
    return "\n".join(lines)


def _render_plain_text(plan: dict[str, Any], language: str = "zh") -> str:
    summary = plan["trip_summary"]
    labels = _labels(language)
    transport_mode = _summary_value_label("transport_mode", summary["transport_mode"], language)
    budget_level = _summary_value_label("budget_level", summary["budget_level"], language)
    lines: list[str] = []
    lines.append(f"=== {labels['title']} ===")
    lines.append(
        f"{summary['destination']} | {summary['start_date']} {labels['range_sep']} {summary['end_date']}"
    )
    lines.append(
        f"{labels['travelers']}: {summary['travelers']} | "
        f"{labels['mode']}: {transport_mode} | "
        f"{labels['budget']}: {budget_level}"
    )
    lines.append(f"{labels['must_do']}: " + ", ".join(summary.get("must_do", [])))
    lines.append("")

    total_cost = 0
    for day in plan["days"]:
        day_label = f"{labels['day']} {day['day']} {labels['day_suffix']}"
        lines.append(f"{day_label} ({day['date']}) | {labels['overnight']}: {day['overnight_city']}")
        for slot in day["slots"]:
            cost = int(slot.get("estimated_cost_cny", 0))
            total_cost += cost
            slot_type = _slot_type_label(slot["type"], language)
            lines.append(
                f"  [{slot['slot_id']}] {slot['time_start']}-{slot['time_end']} "
                f"{slot_type}: {slot['title']} {labels['at']} {slot['location']} ({labels['currency']} {cost})"
            )
            lines.append(f"      {slot['details']}")
        lines.append("")
    lines.append(f"{labels['total_cost']}: {labels['currency']} {total_cost}")
    return "\n".join(lines)


def _labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "title": "OpenTravel Itinerary",
            "travelers": "Travelers",
            "mode": "Mode",
            "budget": "Budget",
            "must_do": "Must-do",
            "day": "Day",
            "day_suffix": "",
            "overnight": "Overnight",
            "total_cost": "Estimated total cost (all people)",
            "currency": "CNY",
            "at": "at",
            "range_sep": "to",
        }
    return {
        "title": "OpenTravel 行程",
        "travelers": "人数",
        "mode": "交通方式",
        "budget": "预算",
        "must_do": "必须安排",
        "day": "第",
        "day_suffix": "天",
        "overnight": "住宿",
        "total_cost": "预计总费用（所有人）",
        "currency": "人民币",
        "at": "在",
        "range_sep": "至",
    }


def _slot_type_label(slot_type: str, language: str) -> str:
    labels = {
        "transport": ("交通", "Transport"),
        "activity": ("活动", "Activity"),
        "meal": ("餐饮", "Meal"),
        "hotel": ("住宿", "Hotel"),
        "buffer": ("缓冲", "Buffer"),
    }
    zh, en = labels.get(slot_type, (slot_type, slot_type))
    return zh if language == "zh" else en


def _summary_value_label(field: str, value: str, language: str) -> str:
    mapping = {
        "transport_mode": {
            "self_drive": ("自驾", "Self-drive"),
            "public_transport": ("公共交通", "Public transport"),
            "mixed": ("混合", "Mixed"),
        },
        "budget_level": {
            "budget": ("经济", "Budget"),
            "mid": ("均衡", "Balanced"),
            "premium": ("舒适", "Comfort"),
        },
    }
    field_map = mapping.get(field, {})
    zh, en = field_map.get(value, (value, value))
    return zh if language == "zh" else en
