from __future__ import annotations

from typing import Any


def render_text(plan: dict[str, Any], language: str = "zh") -> str:
    return _render(plan, language=language, markdown=False)


def render_markdown(plan: dict[str, Any], language: str = "zh") -> str:
    return _render(plan, language=language, markdown=True)


def _render(plan: dict[str, Any], language: str, markdown: bool) -> str:
    summary = plan["trip_summary"]
    labels = _labels(language)
    transport_mode = _summary_value_label("transport_mode", summary["transport_mode"], language)
    budget_level = _summary_value_label("budget_level", summary["budget_level"], language)
    lines: list[str] = []

    if markdown:
        lines.append(f"# {labels['title']}")
        lines.append("")
        lines.append(
            f"**{summary['destination']}** | {summary['start_date']} {labels['range_sep']} {summary['end_date']}"
        )
    else:
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
        if markdown:
            lines.append(f"## {labels['day']} {day['day']} {labels['day_suffix']} ({day['date']})")
            lines.append(f"**{labels['overnight']}**: {day['overnight_city']}")
            lines.append("")
        else:
            lines.append(f"{labels['day']} {day['day']} {labels['day_suffix']} ({day['date']})")
            lines.append(f"{labels['overnight']}: {day['overnight_city']}")

        for slot in day["slots"]:
            cost = int(slot.get("estimated_cost_cny", 0))
            total_cost += cost
            slot_type = _slot_type_label(slot["type"], language)
            lines.extend(_render_slot_block(slot, slot_type, cost, markdown=markdown))
            lines.append("")

        lines.append("")

    lines.append(f"{labels['total_cost']}: {labels['currency']} {total_cost}")
    return "\n".join(lines).rstrip()


def _render_slot_block(
    slot: dict[str, Any],
    slot_type: str,
    cost: int,
    markdown: bool,
) -> list[str]:
    title = str(slot.get("title", "")).strip()
    location = str(slot.get("location", "")).strip()
    details = str(slot.get("details", "")).strip()
    cost_text = f"费用约{cost}元" if cost > 0 else "费用约0元"
    detail_line = f"{details} {cost_text}".strip()
    first_line = f"[{slot['slot_id']}] {slot['time_start']}-{slot['time_end']} {_slot_icon(slot['type'])} {slot_type}: {title}"

    if markdown:
        return [
            f"- {first_line}",
            f"  - {location}",
            f"  - {detail_line}",
        ]

    return [
        f"  - {first_line}",
        f"    - {location}",
        f"    - {detail_line}",
    ]


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


def _slot_icon(slot_type: str) -> str:
    icons = {
        "transport": "🚇",
        "activity": "🎡",
        "meal": "🍜",
        "hotel": "🏨",
        "buffer": "⏳",
    }
    return icons.get(slot_type, "•")


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
