try:
    from langchain.tools import tool
except ImportError:
    tool = None  # type: ignore[assignment]

from schemas.trip_request import TripRequest
from services.memory_service import load_user_profile, save_user_preferences


def get_user_memory(user_id: str) -> dict:
    """Load user profile and preferences from local memory storage."""
    profile = load_user_profile(user_id)
    return profile.model_dump() if profile else {}


def save_user_memory(user_id: str, payload: dict) -> dict:
    """Persist user preferences from a trip request."""
    request = TripRequest.model_validate(payload)
    save_user_preferences(user_id=user_id, request=request)
    return {"saved": True}


get_user_memory_tool = tool(get_user_memory) if tool else get_user_memory
save_user_memory_tool = tool(save_user_memory) if tool else save_user_memory
