from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from pypinyin import lazy_pinyin
except ImportError:  # pragma: no cover
    lazy_pinyin = None


OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"


@dataclass
class WeatherLocation:
    name: str
    country: str
    admin1: str
    latitude: float
    longitude: float
    timezone: str


def build_weather_summary(
    request: dict[str, Any],
    *,
    language: str = "zh",
    timeout_sec: int = 15,
) -> dict[str, Any] | None:
    destination = str(request.get("destination", "")).strip()
    start_date = str(request.get("start_date", "")).strip()
    end_date = str(request.get("end_date", "")).strip()
    if not destination or not start_date or not end_date:
        return None

    try:
        start_day = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_day = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    today = date.today()
    if (start_day - today).days > 16:
        return {
            "provider": "open-meteo",
            "location": {
                "name": destination,
                "admin1": "",
                "country": "",
                "latitude": None,
                "longitude": None,
                "timezone": "auto",
            },
            "forecast_days": [],
            "overall_tip": (
                "出行日期超出当前天气预报范围，建议临近出发再查看实时天气。"
                if language == "zh"
                else "Trip dates are outside the forecast range. Check again closer to departure."
            ),
            "language": language,
            "coverage": "unavailable",
        }

    location = _geocode_destination(destination, timeout_sec=timeout_sec)
    if location is None:
        return None

    forecast_days = max(1, min(16, (end_day - today).days + 1))
    forecast = _fetch_daily_forecast(location, forecast_days=forecast_days, timeout_sec=timeout_sec)
    if forecast is None:
        return None

    daily = forecast.get("daily", {})
    if not isinstance(daily, dict):
        return None

    weather_days: list[dict[str, Any]] = []
    start_text = start_day.isoformat()
    end_text = end_day.isoformat()
    for idx, date_text in enumerate(daily.get("time", [])):
        if str(date_text) < start_text or str(date_text) > end_text:
            continue
        day_entry = _build_day_entry(daily, idx, str(date_text), language=language)
        if day_entry is not None:
            weather_days.append(day_entry)

    overall_tip = _overall_tip(weather_days, language=language)
    coverage = "full" if weather_days else "unavailable"
    if not weather_days:
        overall_tip = (
            "当前天气预报暂未覆盖出行日期，建议临近出发再查看。"
            if language == "zh"
            else "Forecast does not yet cover the trip dates. Check again closer to departure."
        )

    return {
        "provider": "open-meteo",
        "location": {
            "name": location.name,
            "admin1": location.admin1,
            "country": location.country,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": location.timezone,
        },
        "forecast_days": weather_days,
        "overall_tip": overall_tip,
        "language": language,
        "coverage": coverage,
    }


def _geocode_destination(destination: str, timeout_sec: int) -> WeatherLocation | None:
    candidates = _destination_search_terms(destination)
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for source_rank, (term, use_english) in enumerate(candidates):
        params = {
            "name": term,
            "count": 10,
            "format": "json",
            "language": "en" if use_english else "zh",
        }
        if _looks_like_china_destination(destination):
            params["country_code"] = "CN"

        payload = _get_json(f"{OPEN_METEO_GEOCODING}?{urlencode(params)}", timeout_sec)
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            continue

        for result in results:
            if not isinstance(result, dict):
                continue
            key = (
                str(result.get("name", "")),
                str(result.get("admin1", "")),
                str(result.get("country_code", "")),
                str(result.get("feature_code", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            enriched = dict(result)
            enriched["_source_rank"] = len(candidates) - source_rank
            merged.append(enriched)

    if not merged:
        return None

    best = _select_best_location(merged)
    if best is None:
        return None

    return WeatherLocation(
        name=str(best.get("name", destination)),
        admin1=str(best.get("admin1", "")).strip(),
        country=str(best.get("country", "")).strip(),
        latitude=float(best.get("latitude", 0.0)),
        longitude=float(best.get("longitude", 0.0)),
        timezone=str(best.get("timezone", "auto")).strip() or "auto",
    )


def _destination_search_terms(destination: str) -> list[tuple[str, bool]]:
    terms: list[tuple[str, bool]] = []
    if _looks_like_china_destination(destination):
        romanized = _romanize_destination(destination)
        if romanized:
            terms.append((romanized, True))
        if not destination.endswith("市"):
            terms.append((f"{destination}市", False))
    terms.append((destination, False))
    return terms


def _romanize_destination(destination: str) -> str | None:
    if lazy_pinyin is None:
        return None
    parts = lazy_pinyin(destination)
    if not parts:
        return None
    return "".join(parts).title()


def _select_best_location(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None

    def score(result: dict[str, Any]) -> tuple[int, int, int, str]:
        name = str(result.get("name", "")).strip().lower()
        admin1 = str(result.get("admin1", "")).strip().lower()
        country_code = str(result.get("country_code", "")).strip().upper()
        feature_code = str(result.get("feature_code", "")).strip().upper()
        source_rank = int(result.get("_source_rank", 0) or 0)
        population = result.get("population", 0)
        try:
            population_score = int(population)
        except (TypeError, ValueError):
            population_score = 0

        feature_rank = {
            "PPLC": 520,
            "PPLA": 500,
            "PPLA1": 480,
            "PPLA2": 460,
            "PPLA3": 440,
            "PPLA4": 420,
            "PPL": 300,
        }.get(feature_code, 100)

        china_bonus = 200 if country_code == "CN" else 0
        admin_bonus = 25 if admin1 else 0
        return (source_rank * 1000 + china_bonus + feature_rank + admin_bonus, population_score, -len(name), name)

    return max(results, key=score)


def _fetch_daily_forecast(
    location: WeatherLocation,
    *,
    forecast_days: int,
    timeout_sec: int,
) -> dict[str, Any] | None:
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "daily": ",".join(
            [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "rain_sum",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "sunshine_duration",
            ]
        ),
        "forecast_days": forecast_days,
        "timezone": location.timezone or "auto",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "timeformat": "iso8601",
    }
    return _get_json(f"{OPEN_METEO_FORECAST}?{urlencode(params)}", timeout_sec)


def _build_day_entry(
    daily: dict[str, Any],
    idx: int,
    date_text: str,
    *,
    language: str,
) -> dict[str, Any] | None:
    try:
        code = int(daily["weather_code"][idx])
        tmax = float(daily["temperature_2m_max"][idx])
        tmin = float(daily["temperature_2m_min"][idx])
        precipitation = float(daily["precipitation_sum"][idx])
        rain = float(daily["rain_sum"][idx])
        wind = float(daily["wind_speed_10m_max"][idx])
        gust = float(daily["wind_gusts_10m_max"][idx])
        sunshine = float(daily.get("sunshine_duration", [0])[idx])
    except (KeyError, IndexError, TypeError, ValueError):
        return None

    return {
        "date": date_text,
        "weather_code": code,
        "description": _weather_code_description(code, language=language),
        "temperature_2m_max": round(tmax, 1),
        "temperature_2m_min": round(tmin, 1),
        "precipitation_sum": round(precipitation, 1),
        "rain_sum": round(rain, 1),
        "wind_speed_10m_max": round(wind, 1),
        "wind_gusts_10m_max": round(gust, 1),
        "sunshine_duration_hours": round(sunshine / 3600.0, 1),
        "tips": _build_tips(
            code=code,
            tmax=tmax,
            tmin=tmin,
            precipitation=precipitation,
            rain=rain,
            wind=wind,
            gust=gust,
            language=language,
        ),
    }


def _overall_tip(weather_days: list[dict[str, Any]], *, language: str) -> str:
    if not weather_days:
        return ""

    rainy_days = sum(1 for day in weather_days if float(day.get("precipitation_sum", 0)) > 0.5)
    hot_days = sum(1 for day in weather_days if float(day.get("temperature_2m_max", 0)) >= 30)
    cold_days = sum(1 for day in weather_days if float(day.get("temperature_2m_min", 0)) <= 10)

    if language == "en":
        parts: list[str] = []
        if rainy_days:
            parts.append("carry an umbrella on rainy days")
        if hot_days:
            parts.append("keep sun protection and water handy")
        if cold_days:
            parts.append("bring a light jacket for cooler mornings")
        return "; ".join(parts) if parts else "weather looks fairly comfortable"

    parts: list[str] = []
    if rainy_days:
        parts.append("有降雨日，建议随身带伞")
    if hot_days:
        parts.append("有高温日，注意防晒和补水")
    if cold_days:
        parts.append("早晚偏凉，建议带一件薄外套")
    return "；".join(parts) if parts else "整体天气较适合出行"


def _build_tips(
    *,
    code: int,
    tmax: float,
    tmin: float,
    precipitation: float,
    rain: float,
    wind: float,
    gust: float,
    language: str,
) -> list[str]:
    tips: list[str] = []
    rainy = precipitation >= 1.0 or rain >= 1.0 or _is_rainy_code(code)
    windy = wind >= 25 or gust >= 35
    hot = tmax >= 30
    cold = tmin <= 10
    foggy = code in {45, 48}

    if language == "en":
        if rainy:
            tips.append("Bring an umbrella and keep some indoor backup time.")
        if windy:
            tips.append("Watch out for wind on open riverfront or hilltop areas.")
        if hot:
            tips.append("Use sun protection and drink enough water.")
        if cold:
            tips.append("A light jacket is recommended in the morning and evening.")
        if foggy:
            tips.append("Fog may reduce visibility in the morning.")
        return tips or ["Weather is comfortable for sightseeing."]

    if rainy:
        tips.append("建议带伞，并给室内活动留一点备选时间。")
    if windy:
        tips.append("江边或山顶开阔区域注意防风。")
    if hot:
        tips.append("注意防晒和补水，尽量避开中午暴晒。")
    if cold:
        tips.append("早晚可能偏凉，建议带一件薄外套。")
    if foggy:
        tips.append("清晨可能有雾，注意视线和拍照安排。")
    return tips or ["整体适合正常游览。"]


def _weather_code_description(code: int, *, language: str) -> str:
    if language == "en":
        return _weather_code_description_en(code)
    return _weather_code_description_zh(code)


def _weather_code_description_zh(code: int) -> str:
    if code == 0:
        return "晴"
    if code in {1, 2}:
        return "多云间晴"
    if code == 3:
        return "阴"
    if code in {45, 48}:
        return "有雾"
    if code in {51, 53, 55, 56, 57}:
        return "有毛毛雨"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "有降雨"
    if code in {71, 73, 75, 77, 85, 86}:
        return "有降雪"
    if code in {95, 96, 99}:
        return "有雷暴"
    return f"天气代码 {code}"


def _weather_code_description_en(code: int) -> str:
    if code == 0:
        return "clear sky"
    if code in {1, 2}:
        return "mostly clear / partly cloudy"
    if code == 3:
        return "overcast"
    if code in {45, 48}:
        return "fog"
    if code in {51, 53, 55, 56, 57}:
        return "drizzle"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {95, 96, 99}:
        return "thunderstorm"
    return f"weather code {code}"


def _is_rainy_code(code: int) -> bool:
    return code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


def _looks_like_china_destination(destination: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in destination)


def _get_json(url: str, timeout_sec: int) -> dict[str, Any] | None:
    request = Request(url, headers={"User-Agent": "OpenTravel/1.0"})
    try:
        with urlopen(request, timeout=timeout_sec) as response:
            raw = response.read().decode("utf-8")
    except (URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload
