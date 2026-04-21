from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .llm_client import generate_with_model
from .models import PlannerConfig
from .progress import ProgressReporter
from .prompt_loader import render_prompt


def clarify_request(
    request: dict[str, Any],
    config: PlannerConfig | None = None,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    # 澄清层只在交互式终端中启用；非交互场景保持原始请求不变。
    if not _is_interactive():
        return request

    clarified = dict(request)
    language = _resolve_language(clarified, config)
    if not isinstance(clarified.get("preferences"), dict):
        clarified["preferences"] = {}

    labels = _clarify_labels(language)
    if progress:
        progress.stage(labels["heading"].strip(), percent=12)
    print(f"\n{labels['heading']}")
    print(labels["step_1"])
    print(labels["step_2"])
    print(f"{labels['step_3']}\n")

    _fill_required_fields(clarified, language)
    _collect_activity_preferences(clarified, config=config, language=language)
    _collect_general_preferences(clarified, language)
    _collect_extra_notes(clarified, language)
    if progress:
        progress.stage("澄清完成", percent=18)

    return clarified


def _fill_required_fields(request: dict[str, Any], language: str) -> None:
    print(_clarify_labels(language)["fill_required"])
    required_prompts = {
        "origin_city": _field_label("origin_city", language),
        "destination": _field_label("destination", language),
        "start_date": _field_label("start_date", language),
        "end_date": _field_label("end_date", language),
        "arrival_mode": _field_label("arrival_mode", language),
        "travelers": _field_label("travelers", language),
        "transport_mode": _field_label("transport_mode", language),
        "must_do": _field_label("must_do", language),
    }

    for field, label in required_prompts.items():
        if _field_is_valid(field, request.get(field)):
            continue
        value = _prompt_required(field, label)
        request[field] = value


def _collect_general_preferences(request: dict[str, Any], language: str) -> None:
    preferences = _preferences_dict(request)
    print(f"\n{_clarify_labels(language)['general_prefs']}")

    if not _has_value(preferences.get("budget_level")):
        preferences["budget_level"] = _prompt_choice(
            _field_label("budget_level", language),
            _question("budget_level", language),
            ["budget", "mid", "premium"],
            _display_labels("budget_level", language),
            default="budget",
            language=language,
        )

    if not _has_value(preferences.get("pace_preference")):
        preferences["pace_preference"] = _prompt_choice(
            _field_label("pace_preference", language),
            _question("pace_preference", language),
            ["relaxed", "balanced", "intense"],
            _display_labels("pace_preference", language),
            default="balanced",
            language=language,
        )

    if not _has_value(preferences.get("accommodation_preference")):
        preferences["accommodation_preference"] = _prompt_choice(
            _field_label("accommodation_preference", language),
            _question("accommodation_preference", language),
            ["guesthouse", "apartment", "hotel", "mixed"],
            _display_labels("accommodation_preference", language),
            default="mixed",
            language=language,
        )

    if (
        not _has_value(preferences.get("max_drive_hours_per_day"))
        and request.get("transport_mode") == "self_drive"
    ):
        preferences["max_drive_hours_per_day"] = _prompt_int(
            _field_label("max_drive_hours_per_day", language),
            _question("max_drive_hours_per_day", language),
            default=4,
            minimum=1,
            maximum=10,
            language=language,
        )


def _collect_activity_preferences(
    request: dict[str, Any],
    config: PlannerConfig | None = None,
    language: str = "zh",
) -> None:
    preferences = _preferences_dict(request)
    print(f"\n{_clarify_labels(language)['activity_stage']}")
    if _has_value(preferences.get("activity_preferences")):
        return

    wants_local = _prompt_yes_no(
        _field_label("activity_preferences", language),
        _question("activity_preferences", language),
        default=True,
        language=language,
    )
    if not wants_local:
        preferences["activity_preferences"] = []
        return

    candidates = _activity_candidates(request, config=config)
    selected = _prompt_multi_select(
        _field_label("activity_preferences", language),
        _question("activity_selection", language),
        candidates,
        language=language,
    )
    preferences["activity_preferences"] = selected

    must_do = request.get("must_do")
    if isinstance(must_do, list):
        merged = list(must_do)
        for item in selected:
            if item not in merged:
                merged.append(item)
        request["must_do"] = merged


def _collect_extra_notes(request: dict[str, Any], language: str) -> None:
    preferences = _preferences_dict(request)
    print(f"\n{_clarify_labels(language)['special_notes']}")
    if _has_value(preferences.get("special_requirements")):
        return

    note = _prompt_optional(
        _field_label("special_requirements", language),
        _question("special_requirements", language),
        language=language,
    )
    if note:
        preferences["special_requirements"] = note


def _prompt_required(field: str, label: str, language: str) -> Any:
    while True:
        if field in {"arrival_mode", "transport_mode"}:
            if field == "arrival_mode":
                return _prompt_choice(
                    label,
                    _question(field, language),
                    ["flight", "train", "ferry", "self_drive", "mixed"],
                    _display_labels(field, language),
                    default="flight",
                    language=language,
                )
            return _prompt_choice(
                label,
                _question(field, language),
                ["self_drive", "public_transport", "mixed"],
                _display_labels(field, language),
                default="self_drive",
                language=language,
            )

        if field == "travelers":
            return _prompt_int(
                label,
                _question(field, language),
                default=4,
                minimum=1,
                maximum=12,
                language=language,
            )

        if field == "must_do":
            raw = _prompt_optional(
                label,
                _question(field, language),
                language=language,
            )
            items = _split_items(raw)
            if items:
                return items
            print("must_do 不能为空，请至少输入一个活动或体验。")
            continue

        raw = _prompt_optional(label, _question(field, language), language=language)
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
    language: str,
) -> str:
    print(f"\n{field_label}")
    print(question)
    for idx, (value, display_label) in enumerate(zip(values, display_labels), start=1):
        suffix = " (默认)" if language == "zh" and value == default else ""
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


def _prompt_yes_no(field_label: str, question: str, default: bool, language: str) -> bool:
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
    language: str,
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


def _prompt_optional(field_label: str, question: str, language: str) -> str:
    print(f"\n{field_label}")
    return input(f"{question}\n> ").strip()


def _prompt_multi_select(
    field_label: str, question: str, candidates: list[str], language: str
) -> list[str]:
    print(f"\n{field_label}")
    print(question)
    for idx, candidate in enumerate(candidates, start=1):
        print(f"  {idx}. {candidate}")

    while True:
        raw = input(_question("activity_selection_input", language)).strip()
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
        print(_message("invalid_choice", language))


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
        system_prompt=render_prompt("system/clarifier_activity.txt"),
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
    return render_prompt(
        "user/clarifier_activity.txt",
        payload_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )


def _resolve_language(request: dict[str, Any], config: PlannerConfig | None) -> str:
    if config and config.preferred_language in {"zh", "en"}:
        return config.preferred_language
    return str(request.get("language", "zh"))


def _clarify_labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "heading": "\nStart trip clarification",
            "step_1": "Step 1: complete the required basics",
            "step_2": "Step 2: confirm destination-specific activity preferences",
            "step_3": "Step 3: refine budget, pace, and lodging preferences",
            "fill_required": "First, fill in the core trip information.",
            "general_prefs": "Now refine general preferences.",
            "activity_stage": "Now confirm local activity preferences based on the destination.",
            "special_notes": "Finally, add any special requirements.",
        }
    return {
        "heading": "\n开始需求澄清",
        "step_1": "第1层：补齐基础信息",
        "step_2": "第2层：围绕目的地确认本地特色活动",
        "step_3": "第3层：细化预算、节奏和住宿偏好",
        "fill_required": "先补齐这次行程的基础信息。",
        "general_prefs": "继续细化通用偏好。",
        "activity_stage": "先看目的地，再确认本地特色活动偏好。",
        "special_notes": "最后补充特殊需求。",
    }


def _field_label(field: str, language: str) -> str:
    mapping = {
        "origin_city": ("Origin city", "出发地"),
        "destination": ("Destination", "目的地"),
        "start_date": ("Start date (YYYY-MM-DD)", "出行开始日期 (YYYY-MM-DD)"),
        "end_date": ("End date (YYYY-MM-DD)", "出行结束日期 (YYYY-MM-DD)"),
        "arrival_mode": ("Arrival mode", "到达方式"),
        "travelers": ("Travelers", "出行人数"),
        "transport_mode": ("Travel mode", "旅行交通方式"),
        "must_do": ("Must-do items", "必须安排的活动或体验"),
        "budget_level": ("Budget level", "预算层级"),
        "pace_preference": ("Pace preference", "节奏偏好"),
        "accommodation_preference": ("Accommodation preference", "住宿偏好"),
        "max_drive_hours_per_day": ("Max driving hours per day", "每天驾驶上限"),
        "activity_preferences": ("Local activity preferences", "当地特色活动"),
        "special_requirements": ("Special requirements", "补充说明"),
    }
    en, zh = mapping.get(field, (field, field))
    return en if language == "en" else zh


def _question(field: str, language: str) -> str:
    mapping = {
        "origin_city": ("Please enter the origin city:", "请输入出发地："),
        "destination": ("Please enter the destination:", "请输入目的地："),
        "start_date": ("Please enter the start date:", "请输入出行开始日期："),
        "end_date": ("Please enter the end date:", "请输入出行结束日期："),
        "arrival_mode": ("Choose an arrival mode:", "请选择一种到达方式："),
        "travelers": ("Please enter the number of travelers:", "请输入出行人数："),
        "transport_mode": ("Choose the travel mode for the trip:", "请选择一种旅行交通方式："),
        "must_do": ("Enter must-do items, separated by commas.", "请输入必须安排的活动或体验，多个内容用逗号分隔。"),
        "budget_level": ("Which budget level do you prefer?", "希望采用哪种预算层级？"),
        "pace_preference": ("What pace do you prefer?", "这趟行程更偏向哪种节奏？"),
        "accommodation_preference": ("Which lodging type do you prefer?", "更偏向哪种住宿类型？"),
        "max_drive_hours_per_day": ("What is the maximum driving time per day?", "如果这次主要采用自驾，每天可接受的驾驶时长上限是几小时？"),
        "activity_preferences": ("Do you want to prioritize local activities?", "是否希望优先加入当地特色活动？"),
        "activity_selection": ("Select the activities you want to prioritize.", "请选择想优先安排的活动（可多选，输入编号用逗号分隔）"),
        "activity_selection_input": ("Enter numbers like 1,3,4; press Enter for none: ", "请输入编号，例如 1,3,4；直接回车表示不选择："),
        "special_requirements": ("Any special requirements to note?", "还有没有必须注意的特殊需求？例如不想赶路、想保留自由活动时间、要控制住宿预算等。留空表示没有。"),
    }
    en, zh = mapping.get(field, (field, field))
    return en if language == "en" else zh


def _display_labels(field: str, language: str) -> list[str]:
    mapping = {
        "arrival_mode": [["flight", "train", "ferry", "self_drive", "mixed"], ["Flight", "Train", "Ferry", "Self-drive arrival", "Mixed"]],
        "transport_mode": [["self_drive", "public_transport", "mixed"], ["Self-drive", "Public transport", "Mixed"]],
        "budget_level": [["budget", "mid", "premium"], ["Budget", "Balanced", "Comfort"]],
        "pace_preference": [["relaxed", "balanced", "intense"], ["Relaxed", "Balanced", "Intense"]],
        "accommodation_preference": [["guesthouse", "apartment", "hotel", "mixed"], ["Guesthouse", "Apartment", "Hotel", "Mixed"]],
    }
    default = [field]
    values = mapping.get(field, [default, default])[1 if language == "en" else 0]
    return list(values)


def _message(key: str, language: str) -> str:
    mapping = {
        "invalid_choice": ("Invalid input, please choose again.", "输入无效，请重新选择。"),
    }
    en, zh = mapping.get(key, (key, key))
    return en if language == "en" else zh
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
