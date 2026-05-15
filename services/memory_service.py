from __future__ import annotations

import json
from typing import Any

from app.config import ROOT_DIR
from schemas.user_profile import UserProfile


MEMORY_PATH = ROOT_DIR / "data" / "user_memory.json"
IN_MEMORY_PROFILES: dict[str, dict] = {}


def load_user_profile(user_id: str) -> UserProfile | None:
    payload = _load_profiles()
    raw_profile = payload.get(user_id)
    if raw_profile is None:
        return None
    return UserProfile.model_validate(raw_profile)


def save_user_preferences(user_id: str, preferences: dict[str, Any]) -> None:
    """Persist stable user preferences only.

    Temporary trip fields such as destination, days, people, and budget are not
    written here. Session-level state lives in ws_session_manager instead.
    """

    payload = _load_profiles()
    profile = payload.get(user_id, {"user_id": user_id})

    interests = preferences.get("interests")
    if isinstance(interests, list):
        profile["interests"] = [item for item in interests if isinstance(item, str)]

    food_preferences = preferences.get("food_preferences")
    if isinstance(food_preferences, list):
        profile["food_preferences"] = [
            item for item in food_preferences if isinstance(item, str)
        ]

    disliked_tags = preferences.get("disliked_tags")
    if isinstance(disliked_tags, list):
        profile["disliked_tags"] = [item for item in disliked_tags if isinstance(item, str)]

    pace_preference = preferences.get("pace_preference")
    if isinstance(pace_preference, str):
        profile["pace_preference"] = pace_preference

    home_city = preferences.get("home_city")
    if isinstance(home_city, str):
        profile["home_city"] = home_city

    payload[user_id] = profile
    _write_profiles(payload)


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
        MEMORY_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except PermissionError:
        pass
