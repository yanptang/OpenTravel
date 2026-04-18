from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from .llm_client import generate_with_model
from .models import PlannerConfig


SYSTEM_PROMPT = """
You are a travel planning agent.
Return ONLY valid JSON. No markdown. No explanation.
Generate a complete day-by-day slot itinerary that follows this schema:
{
  "trip_summary": {
    "origin_city": "string",
    "destination": "string",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "arrival_mode": "flight|train|ferry|self_drive|mixed",
    "travelers": 1,
    "transport_mode": "self_drive|public_transport|mixed",
    "budget_level": "budget|mid|premium",
    "must_do": ["string"]
  },
  "days": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "overnight_city": "string",
      "slots": [
        {
          "slot_id": 1,
          "type": "transport|activity|meal|hotel|buffer",
          "time_start": "HH:MM",
          "time_end": "HH:MM",
          "title": "string",
          "location": "string",
          "details": "string",
          "estimated_cost_cny": 0,
          "rationale": "string"
        }
      ]
    }
  ]
}

Hard constraints:
- Do not leave empty strings.
- Each day should end with one hotel slot.
- Include all user must_do preferences across the whole trip.
- Keep schedule realistic and coherent.
"""


def build_user_prompt(request: dict[str, Any]) -> str:
    return (
        "Generate an itinerary JSON based on this request.\n"
        "Request JSON:\n"
        f"{json.dumps(request, ensure_ascii=False, indent=2)}"
    )


def generate_plan(request: dict[str, Any], config: PlannerConfig) -> dict[str, Any]:
    if config.use_llm:
        plan = _generate_by_llm(request, config)
        if plan is not None:
            return plan
        boosted_tokens = min(config.max_tokens * 2, 8192)
        if boosted_tokens > config.max_tokens:
            print(
                f"[warn] LLM first pass failed. Retrying with higher max_tokens={boosted_tokens}."
            )
            boosted = replace(config, max_tokens=boosted_tokens)
            plan = _generate_by_llm(request, boosted)
            if plan is not None:
                return plan
        print("[warn] LLM generation failed or timed out; fallback to mock planner.")
    return _generate_mock_plan(request)


def _generate_by_llm(request: dict[str, Any], config: PlannerConfig) -> dict[str, Any] | None:
    return generate_with_model(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(request),
        config=config,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        expect_json=True,
    )


def _generate_mock_plan(request: dict[str, Any]) -> dict[str, Any]:
    start = datetime.strptime(request["start_date"], "%Y-%m-%d")
    end = datetime.strptime(request["end_date"], "%Y-%m-%d")
    total_days = (end - start).days + 1

    destination = request["destination"]
    must_do = request.get("must_do", [])

    days: list[dict[str, Any]] = []
    major_stops = _build_major_stops(destination, total_days)
    for idx in range(total_days):
        date = (start + timedelta(days=idx)).strftime("%Y-%m-%d")
        stop = major_stops[idx]
        slots = _build_day_slots(idx + 1, date, stop, must_do, request)
        days.append(
            {
                "day": idx + 1,
                "date": date,
                "overnight_city": stop["overnight_city"],
                "slots": slots,
            }
        )

    return {
        "trip_summary": {
            "origin_city": request["origin_city"],
            "destination": destination,
            "start_date": request["start_date"],
            "end_date": request["end_date"],
            "arrival_mode": request["arrival_mode"],
            "travelers": request["travelers"],
            "transport_mode": request["transport_mode"],
            "budget_level": request.get("budget_level", "budget"),
            "must_do": must_do,
        },
        "days": days,
    }


def _build_major_stops(destination: str, total_days: int) -> list[dict[str, str]]:
    if "iceland" in destination.lower() or "冰岛" in destination:
        ring = [
            ("Reykjanes", "Reykjavik"),
            ("Golden Circle", "Hella"),
            ("South Coast", "Vik"),
            ("Skaftafell", "Hofn"),
            ("Eastfjords", "Egilsstadir"),
            ("Lake Myvatn", "Myvatn"),
            ("Husavik", "Akureyri"),
            ("Northwest", "Blonduos"),
            ("Snaefellsnes", "Borgarnes"),
            ("Capital Area", "Reykjavik"),
        ]
        if total_days <= len(ring):
            return [
                {"zone": zone, "overnight_city": city}
                for zone, city in ring[:total_days]
            ]
        result = [{"zone": zone, "overnight_city": city} for zone, city in ring]
        while len(result) < total_days:
            result.append({"zone": "Flexible Day", "overnight_city": "Reykjavik"})
        return result
    return [
        {"zone": f"{destination} Day {i + 1}", "overnight_city": destination}
        for i in range(total_days)
    ]


def _build_day_slots(
    day_no: int,
    date: str,
    stop: dict[str, str],
    must_do: list[str],
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    if day_no == 1:
        slots = _build_arrival_day_slots(request, stop)
        _inject_must_do(day_no, date, slots, must_do, stop)
        return slots

    slots: list[dict[str, Any]] = [
        {
            "slot_id": 1,
            "type": "meal",
            "time_start": "08:00",
            "time_end": "09:00",
            "title": "Breakfast",
            "location": stop["overnight_city"],
            "details": "Simple breakfast near accommodation.",
            "estimated_cost_cny": 60,
            "rationale": "Stable start for self-drive day.",
        },
        {
            "slot_id": 2,
            "type": "transport",
            "time_start": "09:00",
            "time_end": "11:00",
            "title": f"Drive to {stop['zone']} highlights",
            "location": stop["zone"],
            "details": "Self-drive scenic transfer. Time is estimated.",
            "estimated_cost_cny": 120,
            "rationale": "Keep a moderate driving window.",
        },
        {
            "slot_id": 3,
            "type": "activity",
            "time_start": "11:30",
            "time_end": "14:00",
            "title": f"{stop['zone']} core sightseeing",
            "location": stop["zone"],
            "details": "Main scenic stop with photo time.",
            "estimated_cost_cny": 180,
            "rationale": "Best daylight window for outdoor activities.",
        },
        {
            "slot_id": 4,
            "type": "meal",
            "time_start": "14:00",
            "time_end": "15:00",
            "title": "Lunch",
            "location": stop["zone"],
            "details": "Local restaurant with flexible menu options.",
            "estimated_cost_cny": 120,
            "rationale": "Avoid driving fatigue and keep pacing realistic.",
        },
        {
            "slot_id": 5,
            "type": "activity",
            "time_start": "15:30",
            "time_end": "18:00",
            "title": "Secondary stop",
            "location": stop["zone"],
            "details": "Optional short hike / viewpoint.",
            "estimated_cost_cny": 80,
            "rationale": "Adds flexibility based on weather and energy.",
        },
        {
            "slot_id": 6,
            "type": "hotel",
            "time_start": "20:00",
            "time_end": "23:00",
            "title": "Check in accommodation",
            "location": stop["overnight_city"],
            "details": "2-bedroom budget guesthouse or apartment.",
            "estimated_cost_cny": 1200,
            "rationale": "Close to next-day route to reduce morning transfer time.",
        },
    ]

    _inject_must_do(day_no, date, slots, must_do, stop)
    return slots


def _build_arrival_day_slots(
    request: dict[str, Any], stop: dict[str, str]
) -> list[dict[str, Any]]:
    origin = request["origin_city"]
    destination = request["destination"]
    arrival_mode = request["arrival_mode"]
    transport_mode = request["transport_mode"]

    intercity_title = _arrival_title(arrival_mode, origin, destination)
    arrival_hub = _arrival_hub(destination, arrival_mode)

    if transport_mode == "self_drive":
        local_transfer_title = "Pick up rental car and drive to city"
        local_transfer_details = (
            "Collect rental car at arrival hub and transfer to city center."
        )
    elif transport_mode == "public_transport":
        local_transfer_title = "Use public transfer to city"
        local_transfer_details = "Use airport/terminal bus or rail to reach city center."
    else:
        local_transfer_title = "Mixed transfer to city"
        local_transfer_details = "Choose rental car or shuttle based on convenience."

    return [
        {
            "slot_id": 1,
            "type": "transport",
            "time_start": "07:00",
            "time_end": "10:30",
            "title": intercity_title,
            "location": f"{origin} -> {arrival_hub}",
            "details": "Arrival-day intercity transfer. Timing is estimated in offline mode.",
            "estimated_cost_cny": 3600,
            "rationale": "Explicitly model day-one departure and arrival connection.",
        },
        {
            "slot_id": 2,
            "type": "transport",
            "time_start": "10:30",
            "time_end": "12:00",
            "title": local_transfer_title,
            "location": f"{arrival_hub} -> {stop['overnight_city']}",
            "details": local_transfer_details,
            "estimated_cost_cny": 500,
            "rationale": "Make airport/terminal to city movement explicit.",
        },
        {
            "slot_id": 3,
            "type": "meal",
            "time_start": "12:00",
            "time_end": "13:00",
            "title": "Arrival lunch",
            "location": stop["overnight_city"],
            "details": "Light meal near city center before afternoon activity.",
            "estimated_cost_cny": 150,
            "rationale": "Keep day-one pacing realistic after transit.",
        },
        {
            "slot_id": 4,
            "type": "activity",
            "time_start": "14:00",
            "time_end": "17:00",
            "title": f"{stop['zone']} easy intro sightseeing",
            "location": stop["zone"],
            "details": "Low-intensity scenic intro with flexible duration.",
            "estimated_cost_cny": 120,
            "rationale": "Avoid overloading arrival day.",
        },
        {
            "slot_id": 5,
            "type": "hotel",
            "time_start": "18:30",
            "time_end": "23:00",
            "title": "Check in accommodation",
            "location": stop["overnight_city"],
            "details": "2-bedroom budget guesthouse or apartment.",
            "estimated_cost_cny": 1200,
            "rationale": "Early rest for full itinerary execution from day two.",
        },
    ]


def _arrival_title(arrival_mode: str, origin: str, destination: str) -> str:
    if arrival_mode == "flight":
        return f"Fly from {origin} to {destination}"
    if arrival_mode == "train":
        return f"Train from {origin} to {destination}"
    if arrival_mode == "ferry":
        return f"Ferry from {origin} to {destination}"
    if arrival_mode == "self_drive":
        return f"Drive from {origin} to {destination}"
    return f"Travel from {origin} to {destination}"


def _arrival_hub(destination: str, arrival_mode: str) -> str:
    destination_lower = destination.lower()
    if arrival_mode == "flight":
        if "iceland" in destination_lower or "冰岛" in destination:
            return "Keflavik International Airport"
        return f"{destination} Airport"
    if arrival_mode == "train":
        return f"{destination} Main Station"
    if arrival_mode == "ferry":
        return f"{destination} Ferry Terminal"
    return destination


def _inject_must_do(
    day_no: int,
    date: str,
    slots: list[dict[str, Any]],
    must_do: list[str],
    stop: dict[str, str],
) -> None:
    combined = " ".join(must_do).lower()

    if ("whale" in combined or "观鲸" in combined) and day_no == 7:
        slots[4] = {
            "slot_id": 5,
            "type": "activity",
            "time_start": "15:00",
            "time_end": "18:00",
            "title": "Whale watching tour",
            "location": "Husavik Harbor",
            "details": "Book small-group afternoon tour; sea condition dependent.",
            "estimated_cost_cny": 700,
            "rationale": "North Iceland is the strongest whale-watching area.",
        }
    if ("glacier" in combined or "冰川" in combined) and day_no == 4:
        slots[2] = {
            "slot_id": 3,
            "type": "activity",
            "time_start": "11:00",
            "time_end": "14:00",
            "title": "Guided glacier hike",
            "location": "Skaftafell / Vatnajokull area",
            "details": "Entry-level guided glacier hike with safety gear.",
            "estimated_cost_cny": 900,
            "rationale": "South-east Iceland offers safer and popular guided options.",
        }
