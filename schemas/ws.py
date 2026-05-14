from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from schemas.api import TripPlanResponse
from schemas.trip_plan import TripPlan


class WSClientMessage(BaseModel):
    type: Literal["user_message", "revise_plan", "request_snapshot", "ping"]
    message: str | None = None
    user_id: str | None = None


class WSSessionSnapshot(BaseModel):
    session_id: str
    thread_id: str | None = None
    trip_id: str | None = None
    user_id: str | None = None
    awaiting_clarification: bool = False
    latest_trip_plan: TripPlan | None = None
    last_plan_response: TripPlanResponse | None = None
    message_history: list[dict[str, str]] = Field(default_factory=list)


class WSServerMessage(BaseModel):
    type: str
    payload: Any = None
