try:
    from langchain.tools import tool
except ImportError:
    tool = None  # type: ignore[assignment]

from services.itinerary_service import validate_trip_plan


def validate_trip(payload: dict, budget: dict, request: dict) -> dict:
    """Validate a draft itinerary against MVP rules."""
    return validate_trip_plan(draft_plan=payload, budget=budget, request=request)


validate_trip_tool = tool(validate_trip) if tool else validate_trip
