from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from schemas.light_trip import LightTripPlan, LightTripRequest


class WSClientMessage(BaseModel):
    type: Literal["user_message", "revise_plan", "request_snapshot", "ping"]
    message: str | None = None
    user_id: str | None = None


class WSSessionSnapshot(BaseModel):
    session_id: str
    user_id: str | None = None
    latest_request: LightTripRequest | None = None
    latest_plan: LightTripPlan | None = None
    message_history: list[dict[str, Any]] = Field(default_factory=list)
    preference_memory: dict[str, Any] = Field(default_factory=dict)


class WSServerMessage(BaseModel):
    type: str
    payload: Any = None
