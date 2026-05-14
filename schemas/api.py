from pydantic import BaseModel, Field

from schemas.trip_plan import TripPlan
from schemas.trip_request import TripRequest

class TripPlanResponse(BaseModel):
    trip_id: str | None = None
    thread_id: str | None = None
    need_clarification: bool
    clarification_question: str | None = None
    trip_request: TripRequest | None = None
    trip_plan: TripPlan | None = None
    agent_steps: list[str] = Field(default_factory=list)


class TripDetailResponse(BaseModel):
    trip_id: str
    user_id: str | None = None
    status: str | None = None
    trip_request: TripRequest | None = None
    trip_plan: TripPlan
