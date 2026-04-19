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

DAY_SYSTEM_PROMPT = """
这是按天生成模式的单日提示词，目标是让小模型一次只处理一天，降低长上下文失败概率。
You are a travel planning agent generating exactly one day of a trip.
Return ONLY valid JSON. No markdown. No explanation.
Output schema:
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

Hard constraints:
- Generate only this single day.
- Keep slot times realistic and non-overlapping.
- End the day with exactly one hotel slot.
- Respect arrival/departure context, overnight city, and must-do targets for this day.
"""


def _language_hint(language: str) -> str:
    if language == "en":
        return (
            "Use English for all free-text fields such as title, location notes, "
            "details, rationale, and any narrative content."
        )
    return (
        "请使用中文输出所有自由文本字段，包括 title、location、details、rationale 等。"
    )


def build_user_prompt(request: dict[str, Any]) -> str:
    language = str(request.get("language", "zh"))
    return (
        f"{_language_hint(language)}\n"
        "Generate an itinerary JSON based on this request.\n"
        "Request JSON:\n"
        f"{json.dumps(request, ensure_ascii=False, indent=2)}"
    )


def generate_plan(request: dict[str, Any], config: PlannerConfig) -> dict[str, Any]:
    # 这里是总调度器：daily 模式逐天生成，whole 模式整段生成，失败则回退到本地骨架。
    language = config.preferred_language if config.preferred_language != "auto" else str(
        request.get("language", "zh")
    )
    if config.use_llm:
        if config.planner_mode == "daily":
            plan = _generate_by_day_llm(request, config, language)
        else:
            plan = _generate_by_llm(request, config, language)
        if plan is not None:
            return plan
        boosted_tokens = min(config.max_tokens * 2, 8192)
        if boosted_tokens > config.max_tokens:
            print(
                f"[warn] LLM first pass failed. Retrying with higher max_tokens={boosted_tokens}.",
                flush=True,
            )
            boosted = replace(config, max_tokens=boosted_tokens)
            if config.planner_mode == "daily":
                plan = _generate_by_day_llm(request, boosted, language)
            else:
                plan = _generate_by_llm(request, boosted, language)
            if plan is not None:
                return plan
        print("[warn] LLM generation failed or timed out; fallback to mock planner.", flush=True)
    return _generate_mock_plan(request, language)


def _generate_by_llm(
    request: dict[str, Any], config: PlannerConfig, language: str
) -> dict[str, Any] | None:
    return generate_with_model(
        system_prompt=f"{SYSTEM_PROMPT}\n\n{_language_hint(language)}",
        user_prompt=build_user_prompt(request),
        config=config,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        expect_json=True,
    )


def _generate_by_day_llm(
    request: dict[str, Any], config: PlannerConfig, language: str
) -> dict[str, Any] | None:
    # 先用本地骨架给出总体路线，逐天只让模型负责“填细节”。
    scaffold = _generate_mock_plan(request, language)
    days = scaffold["days"]
    built_days: list[dict[str, Any]] = []
    covered_texts: list[str] = []

    for idx, day in enumerate(days):
        remaining_must_do = _remaining_must_do(
            request.get("must_do", []),
            covered_texts,
        )
        target_items = _target_must_do_for_day(day, remaining_must_do, idx == len(days) - 1)
        day_prompt = _build_day_prompt(
            request=request,
            trip_summary=scaffold["trip_summary"],
            day=day,
            previous_day=built_days[-1] if built_days else None,
            target_items=target_items,
        )
        print(f"[info] Generating day {day['day']} in daily mode...", flush=True)
        generated_day = generate_with_model(
            system_prompt=f"{DAY_SYSTEM_PROMPT}\n\n{_language_hint(language)}",
            user_prompt=day_prompt,
            config=config,
            temperature=config.temperature,
            max_tokens=min(config.max_tokens, 2200),
            expect_json=True,
        )
        if generated_day is None:
            print(f"[warn] Day {day['day']} generation failed; using scaffold day.", flush=True)
            generated_day = day
        normalized_day = _normalize_day_output(day, generated_day)
        built_days.append(normalized_day)
        covered_texts.extend(_collect_day_texts(normalized_day))

    plan = {
        "trip_summary": scaffold["trip_summary"],
        "days": built_days,
    }
    return plan


def _generate_mock_plan(request: dict[str, Any], language: str) -> dict[str, Any]:
    # 本地骨架用于两种场景：
    # 1. 没有模型时直接出结果
    # 2. daily 模式下先保底，再逐天细化
    start = datetime.strptime(request["start_date"], "%Y-%m-%d")
    end = datetime.strptime(request["end_date"], "%Y-%m-%d")
    total_days = (end - start).days + 1

    destination = request["destination"]
    must_do = request.get("must_do", [])

    days: list[dict[str, Any]] = []
    major_stops = _build_major_stops(destination, total_days, language)
    for idx in range(total_days):
        date = (start + timedelta(days=idx)).strftime("%Y-%m-%d")
        stop = major_stops[idx]
        slots = _build_day_slots(idx + 1, date, stop, must_do, request, language)
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


def _build_major_stops(
    destination: str, total_days: int, language: str
) -> list[dict[str, str]]:
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
                {"zone": _localize_zone(zone, language), "overnight_city": _localize_city(city, language)}
                for zone, city in ring[:total_days]
            ]
        result = [
            {"zone": _localize_zone(zone, language), "overnight_city": _localize_city(city, language)}
            for zone, city in ring
        ]
        while len(result) < total_days:
            result.append(
                {
                    "zone": _localize_zone("Flexible Day", language),
                    "overnight_city": _localize_city("Reykjavik", language),
                }
            )
        return result
    return [
        {
            "zone": _localize_text(
                f"{destination} Day {i + 1}",
                f"{destination}第{i + 1}天",
                language,
            ),
            "overnight_city": _localize_city(destination, language),
        }
        for i in range(total_days)
    ]


def _build_day_slots(
    day_no: int,
    date: str,
    stop: dict[str, str],
    must_do: list[str],
    request: dict[str, Any],
    language: str,
) -> list[dict[str, Any]]:
    transport_mode = request.get("transport_mode", "mixed")
    if day_no == 1:
        # 第一天是到达日，必须显式包含“出发 -> 到达 -> 进城/取车”链路。
        slots = _build_arrival_day_slots(request, stop, language)
        _inject_must_do(day_no, date, slots, must_do, stop, language)
        return slots

    slots: list[dict[str, Any]] = [
        {
            "slot_id": 1,
            "type": "meal",
            "time_start": "08:00",
            "time_end": "09:00",
            "title": _localize_text("Breakfast", "早餐", language),
            "location": stop["overnight_city"],
            "details": _localize_text(
                "Simple breakfast near accommodation.",
                "在住宿附近吃一份简单早餐。",
                language,
            ),
            "estimated_cost_cny": 60,
            "rationale": _localize_text(
                "Stable start for the day.",
                "为当天行程提供稳定开局。",
                language,
            ),
        },
        {
            "slot_id": 2,
            "type": "transport",
            "time_start": "09:00",
            "time_end": "11:00",
            "title": _localize_text(
                (
                    f"Take public transport to {stop['zone']}"
                    if transport_mode == "public_transport"
                    else f"Drive to {stop['zone']} highlights"
                ),
                f"前往{stop['zone']}游览",
                language,
            ),
            "location": stop["zone"],
            "details": _localize_text(
                "Public transport transfer. Time is estimated.",
                "乘坐公共交通前往下一站，时长为估算值。",
                language,
            ),
            "estimated_cost_cny": 120,
            "rationale": _localize_text(
                "Keep pacing realistic for the day.",
                "保持当天节奏合理。",
                language,
            ),
        },
        {
            "slot_id": 3,
            "type": "activity",
            "time_start": "11:30",
            "time_end": "14:00",
            "title": _localize_text(
                f"{stop['zone']} core sightseeing",
                f"{stop['zone']} 核心游览",
                language,
            ),
            "location": stop["zone"],
            "details": _localize_text("Main scenic stop with photo time.", "核心景点停留，留出拍照时间。", language),
            "estimated_cost_cny": 180,
            "rationale": _localize_text("Best daylight window for outdoor activities.", "利用白天最适合户外活动的时段。", language),
        },
        {
            "slot_id": 4,
            "type": "meal",
            "time_start": "14:00",
            "time_end": "15:00",
            "title": _localize_text("Lunch", "午餐", language),
            "location": stop["zone"],
            "details": _localize_text("Local restaurant with flexible menu options.", "在当地餐馆用餐，菜单选择灵活。", language),
            "estimated_cost_cny": 120,
            "rationale": _localize_text("Avoid driving fatigue and keep pacing realistic.", "避免驾驶疲劳，让节奏保持合理。", language),
        },
        {
            "slot_id": 5,
            "type": "activity",
            "time_start": "15:30",
            "time_end": "18:00",
            "title": _localize_text("Secondary stop", "补充游览", language),
            "location": stop["zone"],
            "details": _localize_text("Optional short hike / viewpoint.", "可选短徒步或观景点。", language),
            "estimated_cost_cny": 80,
            "rationale": _localize_text("Adds flexibility based on weather and energy.", "根据天气和体力保留机动性。", language),
        },
        {
            "slot_id": 6,
            "type": "hotel",
            "time_start": "20:00",
            "time_end": "23:00",
            "title": _localize_text("Check in accommodation", "入住酒店", language),
            "location": stop["overnight_city"],
            "details": _localize_text("2-bedroom budget guesthouse or apartment.", "两居室经济型民宿或公寓。", language),
            "estimated_cost_cny": 1200,
            "rationale": _localize_text("Close to next-day route to reduce morning transfer time.", "靠近次日路线，减少早晨转场时间。", language),
        },
    ]

    _inject_must_do(day_no, date, slots, must_do, stop, language)
    return slots


def _build_arrival_day_slots(
    request: dict[str, Any], stop: dict[str, str], language: str
) -> list[dict[str, Any]]:
    # 到达日的核心逻辑：先跨城交通，再当地衔接，再轻量游览，最后入住。
    origin = request["origin_city"]
    destination = request["destination"]
    arrival_mode = request["arrival_mode"]
    transport_mode = request["transport_mode"]

    intercity_title = _arrival_title(arrival_mode, origin, destination, language)
    arrival_hub = _arrival_hub(destination, arrival_mode)

    if transport_mode == "self_drive":
        local_transfer_title = _localize_text(
            "Pick up rental car and drive to city",
            "取车后前往市区",
            language,
        )
        local_transfer_details = _localize_text(
            "Collect rental car at arrival hub and transfer to city center.",
            "在到达点取车后前往市中心。",
            language,
        )
    elif transport_mode == "public_transport":
        local_transfer_title = _localize_text("Use public transfer to city", "使用公共交通前往市区", language)
        local_transfer_details = _localize_text(
            "Use airport/terminal bus or rail to reach city center.",
            "使用机场大巴或铁路前往市中心。",
            language,
        )
    else:
        local_transfer_title = _localize_text("Mixed transfer to city", "混合方式前往市区", language)
        local_transfer_details = _localize_text(
            "Choose rental car or shuttle based on convenience.",
            "根据便利性选择租车或接驳车。",
            language,
        )

    return [
        {
            "slot_id": 1,
            "type": "transport",
            "time_start": "07:00",
            "time_end": "10:30",
            "title": intercity_title,
            "location": f"{origin} -> {arrival_hub}",
            "details": _localize_text(
                "Arrival-day intercity transfer. Timing is estimated in offline mode.",
                "到达日跨城移动。离线模式下时间为估算值。",
                language,
            ),
            "estimated_cost_cny": 3600,
            "rationale": _localize_text(
                "Explicitly model day-one departure and arrival connection.",
                "明确建模第一天的出发与到达衔接。",
                language,
            ),
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
            "rationale": _localize_text(
                "Make airport/terminal to city movement explicit.",
                "把机场/车站到市区的移动明确写入行程。",
                language,
            ),
        },
        {
            "slot_id": 3,
            "type": "meal",
            "time_start": "12:00",
            "time_end": "13:00",
            "title": _localize_text("Arrival lunch", "到达午餐", language),
            "location": stop["overnight_city"],
            "details": _localize_text(
                "Light meal near city center before afternoon activity.",
                "在市中心附近简单用餐，再开始下午活动。",
                language,
            ),
            "estimated_cost_cny": 150,
            "rationale": _localize_text("Keep day-one pacing realistic after transit.", "到达日先放缓节奏。", language),
        },
        {
            "slot_id": 4,
            "type": "activity",
            "time_start": "14:00",
            "time_end": "17:00",
            "title": _localize_text(
                f"{stop['zone']} easy intro sightseeing",
                f"{stop['zone']} 轻松初体验",
                language,
            ),
            "location": stop["zone"],
            "details": _localize_text(
                "Low-intensity scenic intro with flexible duration.",
                "低强度的景点初体验，时长可灵活调整。",
                language,
            ),
            "estimated_cost_cny": 120,
            "rationale": _localize_text("Avoid overloading arrival day.", "避免到达日安排过满。", language),
        },
        {
            "slot_id": 5,
            "type": "hotel",
            "time_start": "18:30",
            "time_end": "23:00",
            "title": _localize_text("Check in accommodation", "入住酒店", language),
            "location": stop["overnight_city"],
            "details": _localize_text("2-bedroom budget guesthouse or apartment.", "两居室经济型民宿或公寓。", language),
            "estimated_cost_cny": 1200,
            "rationale": _localize_text("Early rest for full itinerary execution from day two.", "早点休息，为第二天完整行程做准备。", language),
        },
    ]


def _arrival_title(
    arrival_mode: str, origin: str, destination: str, language: str
) -> str:
    if arrival_mode == "flight":
        return _localize_text(
            f"Fly from {origin} to {destination}",
            f"从{origin}飞往{destination}",
            language,
        )
    if arrival_mode == "train":
        return _localize_text(
            f"Train from {origin} to {destination}",
            f"从{origin}乘火车前往{destination}",
            language,
        )
    if arrival_mode == "ferry":
        return _localize_text(
            f"Ferry from {origin} to {destination}",
            f"从{origin}乘轮渡前往{destination}",
            language,
        )
    if arrival_mode == "self_drive":
        return _localize_text(
            f"Drive from {origin} to {destination}",
            f"从{origin}自驾前往{destination}",
            language,
        )
    return _localize_text(
        f"Travel from {origin} to {destination}",
        f"从{origin}前往{destination}",
        language,
    )


def _arrival_hub(destination: str, arrival_mode: str) -> str:
    destination_lower = destination.lower()
    if arrival_mode == "flight":
        if "iceland" in destination_lower or "冰岛" in destination:
            return "凯夫拉维克国际机场"
        return f"{destination}机场"
    if arrival_mode == "train":
        return f"{destination}火车站"
    if arrival_mode == "ferry":
        return f"{destination}码头"
    return destination


def _localize_text(en_text: str, zh_text: str, language: str) -> str:
    return zh_text if language == "zh" else en_text


def _localize_zone(zone: str, language: str) -> str:
    mapping = {
        "Reykjanes": "雷克雅内斯",
        "Golden Circle": "黄金圈",
        "South Coast": "南岸",
        "Skaftafell": "斯卡夫塔费尔",
        "Eastfjords": "东峡湾",
        "Lake Myvatn": "米湖",
        "Husavik": "胡萨维克",
        "Northwest": "西北部",
        "Snaefellsnes": "斯奈山半岛",
        "Capital Area": "首都圈",
        "Flexible Day": "机动日",
    }
    if language == "zh":
        return mapping.get(zone, zone)
    reverse = {v: k for k, v in mapping.items()}
    return reverse.get(zone, zone)


def _localize_city(city: str, language: str) -> str:
    mapping = {
        "Reykjavik": "雷克雅未克",
        "Hella": "赫拉",
        "Vik": "维克",
        "Hofn": "赫本",
        "Egilsstadir": "埃伊尔斯塔济",
        "Myvatn": "米湖",
        "Akureyri": "阿克雷里",
        "Blonduos": "布伦迪欧斯",
        "Borgarnes": "博尔加内斯",
    }
    if language == "zh":
        return mapping.get(city, city)
    reverse = {v: k for k, v in mapping.items()}
    return reverse.get(city, city)


def _inject_must_do(
    day_no: int,
    date: str,
    slots: list[dict[str, Any]],
    must_do: list[str],
    stop: dict[str, str],
    language: str,
) -> None:
    combined = " ".join(must_do).lower()

    if ("whale" in combined or "观鲸" in combined) and day_no == 7:
        slots[4] = {
            "slot_id": 5,
            "type": "activity",
            "time_start": "15:00",
            "time_end": "18:00",
            "title": _localize_text("Whale watching tour", "观鲸行程", language),
            "location": _localize_text("Husavik Harbor", "胡萨维克港口", language),
            "details": _localize_text(
                "Book small-group afternoon tour; sea condition dependent.",
                "预订下午小团观鲸，具体时间受海况影响。",
                language,
            ),
            "estimated_cost_cny": 700,
            "rationale": _localize_text(
                "North Iceland is the strongest whale-watching area.",
                "冰岛北部是更适合观鲸的区域。",
                language,
            ),
        }
    if ("glacier" in combined or "冰川" in combined) and day_no == 4:
        slots[2] = {
            "slot_id": 3,
            "type": "activity",
            "time_start": "11:00",
            "time_end": "14:00",
            "title": _localize_text("Guided glacier hike", "冰川徒步", language),
            "location": _localize_text("Skaftafell / Vatnajokull area", "斯卡夫塔费尔 / 瓦特纳冰川区域", language),
            "details": _localize_text(
                "Entry-level guided glacier hike with safety gear.",
                "配备安全装备的入门级冰川徒步。",
                language,
            ),
            "estimated_cost_cny": 900,
            "rationale": _localize_text(
                "South-east Iceland offers safer and popular guided options.",
                "冰岛东南部有更安全、也更常见的冰川徒步线路。",
                language,
            ),
        }

    if must_do and day_no == 2:
        joined = _localize_text(
            ", ".join(must_do),
            "、".join(must_do),
            language,
        )
        focus_title = _localize_text(
            f"{joined} themed sightseeing",
            f"{joined} 主题游览",
            language,
        )
        focus_details = _localize_text(
            f"This day is adjusted to cover: {joined}.",
            f"这一天会优先覆盖：{joined}。",
            language,
        )
        slots[2]["title"] = focus_title
        slots[2]["details"] = f"{slots[2]['details']} {focus_details}"


def _build_day_prompt(
    *,
    request: dict[str, Any],
    trip_summary: dict[str, Any],
    day: dict[str, Any],
    previous_day: dict[str, Any] | None,
    target_items: list[str],
) -> str:
    # 日生成 prompt 尽量短，只保留当天必要上下文，减少小模型负担。
    previous_context = "none"
    if previous_day is not None:
        last_slot = previous_day["slots"][-1]
        previous_context = (
            f"previous day ends in {previous_day['overnight_city']} with "
            f"{last_slot.get('title', 'hotel')}"
        )

    prompt_payload = {
        "trip": {
            "origin_city": trip_summary["origin_city"],
            "destination": trip_summary["destination"],
            "dates": f"{trip_summary['start_date']} to {trip_summary['end_date']}",
            "travelers": trip_summary["travelers"],
            "arrival_mode": trip_summary["arrival_mode"],
            "transport_mode": trip_summary["transport_mode"],
            "budget_level": trip_summary["budget_level"],
        },
        "day_request": {
            "day": day["day"],
            "date": day["date"],
            "overnight_city": day["overnight_city"],
            "theme_hint": _day_theme_hint(day),
            "target_must_do": target_items,
            "previous_context": previous_context,
            "notes": request.get("notes", ""),
        },
        "requirements": [
            "Generate 5 to 7 slots only.",
            "Use concrete titles and locations.",
            "End with one hotel slot in the overnight city.",
            "If this is an arrival day, include arrival transfer.",
            "If this is a departure day, include departure transfer.",
        ],
    }
    return (
        "Generate exactly one day JSON for this trip.\n"
        "Input payload:\n"
        f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
    )


def _remaining_must_do(must_do: list[str], covered_texts: list[str]) -> list[str]:
    # 已覆盖的 must-do 不再重复分配给后续天。
    merged = " ".join(covered_texts).lower()
    remaining: list[str] = []
    for item in must_do:
        item_text = item.lower().strip()
        if item_text and item_text in merged:
            continue
        remaining.append(item)
    return remaining


def _target_must_do_for_day(
    day: dict[str, Any], remaining_items: list[str], is_last_day: bool
) -> list[str]:
    # 根据天数和地理位置，把必须体验优先分配到更合适的一天。
    if not remaining_items:
        return []

    zone_text = (
        f"{day.get('overnight_city', '')} "
        f"{' '.join(slot.get('title', '') for slot in day.get('slots', []))}"
    ).lower()
    matched: list[str] = []
    for item in remaining_items:
        lowered = item.lower()
        if "whale" in lowered and ("husavik" in zone_text or "akureyri" in zone_text):
            matched.append(item)
        elif "glacier" in lowered and (
            "skaftafell" in zone_text or "hofn" in zone_text or "vatnaj" in zone_text
        ):
            matched.append(item)

    if matched:
        return matched
    if is_last_day:
        return remaining_items
    return remaining_items[:1]


def _normalize_day_output(
    scaffold_day: dict[str, Any], generated_day: dict[str, Any]
) -> dict[str, Any]:
    # 模型输出后做一次归一化，保证日期、夜宿城市和 slot_id 连续。
    normalized = {
        "day": scaffold_day["day"],
        "date": scaffold_day["date"],
        "overnight_city": generated_day.get(
            "overnight_city", scaffold_day["overnight_city"]
        ),
        "slots": generated_day.get("slots", scaffold_day["slots"]),
    }
    if not isinstance(normalized["slots"], list) or not normalized["slots"]:
        normalized["slots"] = scaffold_day["slots"]

    for idx, slot in enumerate(normalized["slots"], start=1):
        slot["slot_id"] = idx
    return normalized


def _collect_day_texts(day: dict[str, Any]) -> list[str]:
    # 把当天标题和详情压成文本，供 must-do 覆盖检查使用。
    return [
        f"{slot.get('title', '')} {slot.get('details', '')}".lower()
        for slot in day.get("slots", [])
    ]


def _day_theme_hint(day: dict[str, Any]) -> str:
    # 给单日生成一个简短主题提示，帮助模型聚焦当天重点。
    activity_titles = [
        slot.get("title", "")
        for slot in day.get("slots", [])
        if slot.get("type") == "activity"
    ]
    if activity_titles:
        return activity_titles[0]
    transport_titles = [
        slot.get("title", "")
        for slot in day.get("slots", [])
        if slot.get("type") == "transport"
    ]
    if transport_titles:
        return transport_titles[0]
    return day.get("overnight_city", "")
