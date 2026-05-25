from __future__ import annotations

from schemas.light_trip import LightTripRequest
from services.city_alias_service import normalize_request_destination


def merge_light_trip_request(
    current_request: LightTripRequest | None,
    new_request: LightTripRequest | None,
) -> LightTripRequest | None:
    """Merge a new model-extracted request into the current session request."""

    if current_request is None and new_request is None:
        return None
    if current_request is None:
        normalized, _ = normalize_request_destination(new_request)
        return normalized
    if new_request is None:
        return current_request

    normalized_new, _ = normalize_request_destination(new_request)
    if normalized_new is None:
        return current_request

    merged = current_request.model_dump(mode="json")
    new_payload = normalized_new.model_dump(mode="json")

    for field in ["origin", "destination", "days", "travel_style"]:
        if new_payload.get(field) is not None:
            merged[field] = new_payload[field]

    if new_payload.get("budget") is not None:
        merged["budget"] = new_payload["budget"]

    new_people = new_payload.get("people")
    current_people = merged.get("people")
    if new_people is not None:
        if not (new_people == 1 and current_people not in (None, 1)):
            merged["people"] = new_people

    merged["interests"] = _merge_unique(
        current_request.interests,
        normalized_new.interests,
    )
    merged["constraints"] = _merge_unique(
        current_request.constraints,
        normalized_new.constraints,
    )
    return LightTripRequest.model_validate(merged)


def _merge_unique(left: list[str], right: list[str]) -> list[str]:
    result: list[str] = []
    for value in [*left, *right]:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return result
