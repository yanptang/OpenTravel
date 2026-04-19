from __future__ import annotations

from typing import Any


def render_text(plan: dict[str, Any], language: str = "zh") -> str:
    return _render_plain_text(plan, language=language)


def render_markdown(plan: dict[str, Any], language: str = "zh") -> str:
    summary = plan["trip_summary"]
    lines: list[str] = []
    labels = _labels(language)

    lines.append(f"# {labels['title']}")
    lines.append("")
    lines.append(
        f"**{summary['destination']}** | {summary['start_date']} -> {summary['end_date']}"
    )
    lines.append(
        f"{labels['travelers']}: {summary['travelers']} | "
        f"{labels['mode']}: {summary['transport_mode']} | "
        f"{labels['budget']}: {summary['budget_level']}"
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
            lines.append(
                f"- **[{slot['slot_id']}] {slot['time_start']}-{slot['time_end']} "
                f"{slot['type']}**: {slot['title']} @ {slot['location']} "
                f"(CNY {cost})"
            )
            lines.append(f"  - {slot['details']}")
        lines.append("")
    lines.append(f"**{labels['total_cost']}**: CNY {total_cost}")
    return "\n".join(lines)


def _render_plain_text(plan: dict[str, Any], language: str = "zh") -> str:
    summary = plan["trip_summary"]
    labels = _labels(language)
    lines: list[str] = []
    lines.append(f"=== {labels['title']} ===")
    lines.append(
        f"{summary['destination']} | {summary['start_date']} -> {summary['end_date']}"
    )
    lines.append(
        f"{labels['travelers']}: {summary['travelers']} | "
        f"{labels['mode']}: {summary['transport_mode']} | "
        f"{labels['budget']}: {summary['budget_level']}"
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
            lines.append(
                f"  [{slot['slot_id']}] {slot['time_start']}-{slot['time_end']} "
                f"{slot['type']}: {slot['title']} @ {slot['location']} (CNY {cost})"
            )
            lines.append(f"      {slot['details']}")
        lines.append("")
    lines.append(f"{labels['total_cost']}: CNY {total_cost}")
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
    }
