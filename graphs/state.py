from typing import Any, TypedDict

from schemas.trip_plan import TripPlan
from schemas.trip_request import TripRequest
from schemas.user_profile import UserProfile


class TravelState(TypedDict, total=False):
    user_id: str
    thread_id: str | None
    user_message: str
    agent_steps: list[str]
    event_emitter: Any
    trip_request: TripRequest
    missing_fields: list[str]
    need_clarification: bool
    clarification_question: str | None
    user_profile: UserProfile | None
    candidate_pois: list[dict[str, Any]]
    guide_context: list[str]
    ranked_pois: list[dict[str, Any]]
    draft_itinerary: dict[str, Any]
    budget_result: dict[str, Any]
    validation_result: dict[str, Any]
    formatted_trip_plan: TripPlan | None
