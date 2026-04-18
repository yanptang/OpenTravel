from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import REQUIRED_REQUEST_FIELDS, ValidationResult


def validate_request(request: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []

    for field in REQUIRED_REQUEST_FIELDS:
        if field not in request:
            errors.append(f"Missing required field: {field}")

    if errors:
        return ValidationResult(valid=False, errors=errors)

    errors.extend(_validate_dates(request))
    errors.extend(_validate_required_strings(request))
    errors.extend(_validate_modes(request))
    errors.extend(_validate_travelers(request))
    errors.extend(_validate_lists(request))

    return ValidationResult(valid=(len(errors) == 0), errors=errors)


def _validate_dates(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    start = request.get("start_date")
    end = request.get("end_date")

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except Exception:
        return ["start_date/end_date must use format YYYY-MM-DD."]

    if end_dt < start_dt:
        errors.append("end_date must be on or after start_date.")
    if (end_dt - start_dt).days > 20:
        errors.append("For v1, please keep trip duration <= 21 days.")

    return errors


def _validate_travelers(request: dict[str, Any]) -> list[str]:
    travelers = request.get("travelers")
    if not isinstance(travelers, int):
        return ["travelers must be an integer."]
    if travelers <= 0 or travelers > 12:
        return ["travelers must be between 1 and 12."]
    return []


def _validate_required_strings(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["origin_city", "destination"]:
        value = request.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string.")
    return errors


def _validate_modes(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    arrival_mode = request.get("arrival_mode")
    transport_mode = request.get("transport_mode")

    valid_arrival = {"flight", "train", "ferry", "self_drive", "mixed"}
    valid_transport = {"self_drive", "public_transport", "mixed"}

    if arrival_mode not in valid_arrival:
        errors.append(
            "arrival_mode must be one of: flight, train, ferry, self_drive, mixed."
        )
    if transport_mode not in valid_transport:
        errors.append(
            "transport_mode must be one of: self_drive, public_transport, mixed."
        )
    return errors


def _validate_lists(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    must_do = request.get("must_do")
    if not isinstance(must_do, list) or not must_do:
        errors.append("must_do must be a non-empty list.")
    return errors
