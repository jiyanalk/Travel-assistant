from __future__ import annotations

import json
from typing import Any

from app.config import ROOT_DIR
from schemas.user_profile import UserProfile


MEMORY_PATH = ROOT_DIR / "data" / "user_memory.json"
IN_MEMORY_PROFILES: dict[str, dict] = {}
BLOCKED_MEMORY_FIELDS = {
    "destination",
    "origin",
    "days",
    "people",
    "budget",
    "date",
    "start_date",
    "end_date",
}


def load_user_profile(user_id: str) -> UserProfile | None:
    payload = _load_profiles()
    raw_profile = payload.get(user_id)
    if raw_profile is None:
        return None
    return UserProfile.model_validate(raw_profile)


def get_user_preferences(user_id: str) -> dict[str, Any]:
    if not user_id:
        return {}
    return dict(_load_profiles().get(user_id, {"user_id": user_id}))


def update_user_preferences(user_id: str, preferences: dict[str, Any]) -> dict[str, Any]:
    """Merge stable user preferences and never store one-off trip fields."""

    if not user_id:
        return {}

    sanitized = _sanitize_preferences(preferences)
    if not sanitized:
        return get_user_preferences(user_id)

    payload = _load_profiles()
    profile = payload.get(user_id, {"user_id": user_id})

    for key, value in sanitized.items():
        if isinstance(value, list):
            profile[key] = _merge_unique(profile.get(key, []), value)
        elif value is not None:
            profile[key] = value

    payload[user_id] = profile
    _write_profiles(payload)
    return dict(profile)


def save_user_preferences(user_id: str, preferences: dict[str, Any]) -> None:
    update_user_preferences(user_id, preferences)


def _sanitize_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    allowed_fields = {
        "interests",
        "food_preferences",
        "disliked_tags",
        "pace_preference",
        "budget_preference",
        "home_city",
        "travel_style",
        "avoid",
    }
    for key, value in preferences.items():
        if key in BLOCKED_MEMORY_FIELDS or key not in allowed_fields:
            continue
        if isinstance(value, list):
            sanitized[key] = [item for item in value if isinstance(item, str) and item]
        elif isinstance(value, str) and value:
            sanitized[key] = value
    if "avoid" in sanitized:
        sanitized["disliked_tags"] = _merge_unique(
            sanitized.get("disliked_tags", []),
            sanitized.pop("avoid"),
        )
    return sanitized


def _merge_unique(left: Any, right: list[str]) -> list[str]:
    result: list[str] = []
    source = left if isinstance(left, list) else []
    for value in [*source, *right]:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return result


def _load_profiles() -> dict[str, dict]:
    if IN_MEMORY_PROFILES:
        return dict(IN_MEMORY_PROFILES)
    if not MEMORY_PATH.exists():
        return {}
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (PermissionError, OSError, json.JSONDecodeError):
        return dict(IN_MEMORY_PROFILES)


def _write_profiles(payload: dict[str, dict]) -> None:
    IN_MEMORY_PROFILES.clear()
    IN_MEMORY_PROFILES.update(payload)
    try:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except PermissionError:
        pass
