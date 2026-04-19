from __future__ import annotations

from typing import Any


def render_text(plan: dict[str, Any]) -> str:
    summary = plan["trip_summary"]
    lines: list[str] = []
    lines.append("=== OpenTravel Itinerary ===")
    lines.append(
        f"{summary['destination']} | {summary['start_date']} -> {summary['end_date']}"
    )
    lines.append(
        f"Travelers: {summary['travelers']} | Mode: {summary['transport_mode']} | Budget: {summary['budget_level']}"
    )
    lines.append("Must-do: " + ", ".join(summary.get("must_do", [])))
    lines.append("")

    total_cost = 0
    for day in plan["days"]:
        lines.append(
            f"Day {day['day']} ({day['date']}) | Overnight: {day['overnight_city']}"
        )
        for slot in day["slots"]:
            cost = int(slot.get("estimated_cost_cny", 0))
            total_cost += cost
            lines.append(
                f"  [{slot['slot_id']}] {slot['time_start']}-{slot['time_end']} "
                f"{slot['type']}: {slot['title']} @ {slot['location']} (CNY {cost})"
            )
            lines.append(f"      {slot['details']}")
        lines.append("")
    lines.append(f"Estimated total cost (all people): CNY {total_cost}")
    return "\n".join(lines)

