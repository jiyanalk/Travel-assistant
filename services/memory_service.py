import json

from app.config import ROOT_DIR
from schemas.trip_request import TripRequest
from schemas.user_profile import UserProfile


MEMORY_PATH = ROOT_DIR / "data" / "user_memory.json"
IN_MEMORY_PROFILES: dict[str, dict] = {}


def load_user_profile(user_id: str) -> UserProfile | None:
    payload = _load_profiles()
    raw_profile = payload.get(user_id)
    if raw_profile is None:
        return None
    return UserProfile.model_validate(raw_profile)


def save_user_preferences(user_id: str, request: TripRequest) -> None:
    payload = _load_profiles()

    profile = payload.get(user_id, {"user_id": user_id})
    if request.origin:
        profile["home_city"] = request.origin
    if request.destination:
        history = set(profile.get("history_destinations", []))
        history.add(request.destination)
        profile["history_destinations"] = sorted(history)
    if request.interests:
        profile["interests"] = request.interests
    profile["pace_preference"] = request.pace
    if request.budget:
        profile["budget_preference"] = f"{int(request.budget.amount)} {request.budget.currency}"

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
