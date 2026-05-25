from __future__ import annotations

from schemas.light_trip import LightTripRequest


CITY_ALIASES: dict[str, str] = {
    "蓉城": "成都",
    "魔都": "上海",
    "帝都": "北京",
    "山城": "重庆",
    "羊城": "广州",
    "花城": "广州",
    "鹏城": "深圳",
    "金陵": "南京",
    "姑苏": "苏州",
}


def normalize_city_name(value: str | None) -> tuple[str | None, bool]:
    if not value:
        return value, False
    normalized = CITY_ALIASES.get(value.strip())
    if normalized:
        return normalized, True
    return value, False


def normalize_request_destination(
    request: LightTripRequest | None,
) -> tuple[LightTripRequest | None, dict]:
    if request is None:
        return None, {"replaced": False, "aliases_found": []}

    destination, replaced = normalize_city_name(request.destination)
    if not replaced:
        return request, {"replaced": False, "aliases_found": []}

    return (
        request.model_copy(update={"destination": destination}),
        {
            "replaced": True,
            "aliases_found": [request.destination],
            "destination": destination,
        },
    )


def detect_aliases_in_text(text: str) -> dict:
    aliases_found = [alias for alias in CITY_ALIASES if alias in text]
    return {
        "replaced": bool(aliases_found),
        "aliases_found": aliases_found,
        "normalized": {alias: CITY_ALIASES[alias] for alias in aliases_found},
    }
