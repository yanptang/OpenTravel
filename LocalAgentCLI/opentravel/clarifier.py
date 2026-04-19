from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .llm_client import generate_with_model
from .models import PlannerConfig


def clarify_request(
    request: dict[str, Any],
    config: PlannerConfig | None = None,
) -> dict[str, Any]:
    # 澄清层只在交互式终端中启用；非交互场景保持原始请求不变。
    if not _is_interactive():
        return request

    clarified = dict(request)
    if not isinstance(clarified.get("preferences"), dict):
        clarified["preferences"] = {}

    print("\n开始需求澄清")
    print("第1层：补齐基础信息")
    print("第2层：围绕目的地确认本地特色活动")
    print("第3层：细化预算、节奏和住宿偏好\n")

    _fill_required_fields(clarified)
    _collect_activity_preferences(clarified, config=config)
    _collect_general_preferences(clarified)
    _collect_extra_notes(clarified)

    return clarified


def _fill_required_fields(request: dict[str, Any]) -> None:
    print("先补齐这次行程的基础信息。")
    required_prompts = {
        "origin_city": "出发地",
        "destination": "目的地",
        "start_date": "出行开始日期 (YYYY-MM-DD)",
        "end_date": "出行结束日期 (YYYY-MM-DD)",
        "arrival_mode": "到达方式（flight/train/ferry/self_drive/mixed）",
        "travelers": "出行人数",
        "transport_mode": "旅行交通方式（self_drive/public_transport/mixed）",
        "must_do": "必须安排的活动或体验（逗号分隔）",
    }

    for field, label in required_prompts.items():
        if _field_is_valid(field, request.get(field)):
            continue
        value = _prompt_required(field, label)
        request[field] = value


def _collect_general_preferences(request: dict[str, Any]) -> None:
    preferences = _preferences_dict(request)
    print("\n继续细化通用偏好。")

    if not _has_value(preferences.get("budget_level")):
        preferences["budget_level"] = _prompt_choice(
            "预算层级",
            "希望采用哪种预算层级？",
            ["budget", "mid", "premium"],
            ["经济", "均衡", "舒适"],
            default="budget",
        )

    if not _has_value(preferences.get("pace_preference")):
        preferences["pace_preference"] = _prompt_choice(
            "节奏偏好",
            "这趟行程更偏向哪种节奏？",
            ["relaxed", "balanced", "intense"],
            ["轻松", "均衡", "紧凑"],
            default="balanced",
        )

    if not _has_value(preferences.get("accommodation_preference")):
        preferences["accommodation_preference"] = _prompt_choice(
            "住宿偏好",
            "更偏向哪种住宿类型？",
            ["guesthouse", "apartment", "hotel", "mixed"],
            ["民宿/Guesthouse", "公寓/Apartment", "酒店/Hotel", "混合"],
            default="mixed",
        )

    if (
        not _has_value(preferences.get("max_drive_hours_per_day"))
        and request.get("transport_mode") == "self_drive"
    ):
        preferences["max_drive_hours_per_day"] = _prompt_int(
            "每天驾驶上限",
            "如果这次主要采用自驾，每天可接受的驾驶时长上限是几小时？",
            default=4,
            minimum=1,
            maximum=10,
        )


def _collect_activity_preferences(
    request: dict[str, Any],
    config: PlannerConfig | None = None,
) -> None:
    preferences = _preferences_dict(request)
    print("\n先看目的地，再确认本地特色活动偏好。")
    if _has_value(preferences.get("activity_preferences")):
        return

    wants_local = _prompt_yes_no(
        "当地特色活动",
        "是否希望优先加入当地特色活动？",
        default=True,
    )
    if not wants_local:
        preferences["activity_preferences"] = []
        return

    candidates = _activity_candidates(request, config=config)
    selected = _prompt_multi_select(
        "活动偏好",
        "请选择想优先安排的活动（可多选，输入编号用逗号分隔）",
        candidates,
    )
    preferences["activity_preferences"] = selected

    must_do = request.get("must_do")
    if isinstance(must_do, list):
        merged = list(must_do)
        for item in selected:
            if item not in merged:
                merged.append(item)
        request["must_do"] = merged


def _collect_extra_notes(request: dict[str, Any]) -> None:
    preferences = _preferences_dict(request)
    print("\n最后补充特殊需求。")
    if _has_value(preferences.get("special_requirements")):
        return

    note = _prompt_optional(
        "补充说明",
        "还有没有必须注意的特殊需求？例如不想赶路、想保留自由活动时间、要控制住宿预算等。留空表示没有。",
    )
    if note:
        preferences["special_requirements"] = note


def _prompt_required(field: str, label: str) -> Any:
    while True:
        if field in {"arrival_mode", "transport_mode"}:
            if field == "arrival_mode":
                return _prompt_choice(
                    label,
                    "请选择一种到达方式：",
                    ["flight", "train", "ferry", "self_drive", "mixed"],
                    ["飞机", "火车", "轮渡", "自驾到达", "混合"],
                    default="flight",
                )
            return _prompt_choice(
                label,
                "请选择一种旅行交通方式：",
                ["self_drive", "public_transport", "mixed"],
                ["自驾", "公共交通", "混合"],
                default="self_drive",
            )

        if field == "travelers":
            return _prompt_int(
                label,
                "请输入出行人数：",
                default=4,
                minimum=1,
                maximum=12,
            )

        if field == "must_do":
            raw = _prompt_optional(
                label,
                "请输入必须安排的活动或体验，多个内容用逗号分隔。",
            )
            items = _split_items(raw)
            if items:
                return items
            print("must_do 不能为空，请至少输入一个活动或体验。")
            continue

        raw = _prompt_optional(label, f"请输入{label}：")
        if raw:
            if field in {"start_date", "end_date"}:
                if _valid_date(raw):
                    return raw
                print("日期格式必须是 YYYY-MM-DD。")
                continue
            return raw
        print(f"{label} 不能为空。")


def _prompt_choice(
    field_label: str,
    question: str,
    values: list[str],
    display_labels: list[str],
    default: str,
) -> str:
    print(f"\n{field_label}")
    print(question)
    for idx, (value, display_label) in enumerate(zip(values, display_labels), start=1):
        suffix = " (默认)" if value == default else ""
        print(f"  {idx}. {display_label}{suffix}")

    while True:
        raw = input(f"请输入编号，直接回车默认 [{default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(values):
                return values[idx - 1]
        print("输入无效，请重新选择。")


def _prompt_yes_no(field_label: str, question: str, default: bool) -> bool:
    default_text = "Y/n" if default else "y/N"
    print(f"\n{field_label}")
    print(question)
    while True:
        raw = input(f"请输入 {default_text}: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "1", "是"}:
            return True
        if raw in {"n", "no", "0", "否"}:
            return False
        print("请输入 y 或 n。")


def _prompt_int(
    field_label: str,
    question: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    print(f"\n{field_label}")
    print(question)
    while True:
        raw = input(f"请输入数字，直接回车默认 [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except Exception:
            print("请输入整数。")
            continue
        if minimum <= value <= maximum:
            return value
        print(f"请输入 {minimum} 到 {maximum} 之间的整数。")


def _prompt_optional(field_label: str, question: str) -> str:
    print(f"\n{field_label}")
    return input(f"{question}\n> ").strip()


def _prompt_multi_select(field_label: str, question: str, candidates: list[str]) -> list[str]:
    print(f"\n{field_label}")
    print(question)
    for idx, candidate in enumerate(candidates, start=1):
        print(f"  {idx}. {candidate}")

    while True:
        raw = input("请输入编号，例如 1,3,4；直接回车表示不选择：").strip()
        if not raw:
            return []
        selected: list[str] = []
        ok = True
        for part in raw.split(","):
            part = part.strip()
            if not part.isdigit():
                ok = False
                break
            idx = int(part)
            if idx < 1 or idx > len(candidates):
                ok = False
                break
            item = candidates[idx - 1]
            if item not in selected:
                selected.append(item)
        if ok:
            return selected
        print("输入无效，请重新选择。")


def _activity_candidates(
    request: dict[str, Any],
    config: PlannerConfig | None = None,
) -> list[str]:
    destination = str(request.get("destination", "")).lower()
    if config and config.use_llm and destination:
        generated = _generate_destination_activity_candidates(request, config)
        if generated:
            return generated

    if "iceland" in destination or "冰岛" in destination:
        return [
            "whale watching",
            "glacier hiking",
            "horse riding",
            "hot springs",
            "puffin watching",
            "photography",
            "black sand beach",
        ]
    return [
        "local food tour",
        "city walk",
        "museum visit",
        "day trip",
        "scenic viewpoint",
        "hiking",
        "hot springs",
    ]


def _generate_destination_activity_candidates(
    request: dict[str, Any],
    config: PlannerConfig,
) -> list[str]:
    destination = str(request.get("destination", "")).strip()
    if not destination:
        return []

    prompt = _build_activity_prompt(request)
    result = generate_with_model(
        system_prompt=_ACTIVITY_CANDIDATE_SYSTEM_PROMPT,
        user_prompt=prompt,
        config=config,
        temperature=0.3,
        max_tokens=600,
        expect_json=True,
    )
    if not result:
        return []

    items = result.get("activities")
    if not isinstance(items, list):
        return []

    cleaned: list[str] = []
    for item in items:
        if isinstance(item, str):
            value = item.strip()
            if value and value not in cleaned:
                cleaned.append(value)
    return cleaned[:8]


def _build_activity_prompt(request: dict[str, Any]) -> str:
    payload = {
        "destination": request.get("destination", ""),
        "start_date": request.get("start_date", ""),
        "end_date": request.get("end_date", ""),
        "travelers": request.get("travelers", ""),
        "transport_mode": request.get("transport_mode", ""),
        "must_do": request.get("must_do", []),
        "notes": request.get("notes", ""),
    }
    return (
        "请根据目的地和行程信息，列出适合这个目的地的本地特色活动候选，"
        "用于后续向用户追问偏好。只输出 JSON。\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


_ACTIVITY_CANDIDATE_SYSTEM_PROMPT = """
You are a destination-aware travel concierge.
Return ONLY valid JSON. No markdown. No explanation.

Task:
Generate 6 to 8 local activity candidates that are actually relevant to the destination and the travel context.
These candidates will be shown to the user as follow-up preference options.

Output schema:
{
  "activities": [
    "string"
  ]
}

Rules:
- Prefer specific, local, and practical activities.
- Keep labels short and user-friendly.
- Avoid duplicates and overly generic items.
- The list should fit the destination and season.
"""


def _split_items(raw: str | None) -> list[str]:
    if not raw:
        return []
    items = [part.strip() for part in raw.split(",")]
    return [item for item in items if item]


def _valid_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return False
    return True


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return True


def _preferences_dict(request: dict[str, Any]) -> dict[str, Any]:
    preferences = request.get("preferences")
    if not isinstance(preferences, dict):
        preferences = {}
        request["preferences"] = preferences
    return preferences


def _field_is_valid(field: str, value: Any) -> bool:
    if field in {"origin_city", "destination"}:
        return isinstance(value, str) and bool(value.strip())
    if field in {"start_date", "end_date"}:
        return isinstance(value, str) and _valid_date(value)
    if field == "arrival_mode":
        return value in {"flight", "train", "ferry", "self_drive", "mixed"}
    if field == "travelers":
        return isinstance(value, int) and 1 <= value <= 12
    if field == "transport_mode":
        return value in {"self_drive", "public_transport", "mixed"}
    if field == "must_do":
        return isinstance(value, list) and len(value) > 0
    return _has_value(value)


def _is_interactive() -> bool:
    try:
        import sys

        return sys.stdin.isatty()
    except Exception:
        return False
