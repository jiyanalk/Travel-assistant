from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schemas.light_trip import LightTripPlan, LightTripRequest


class AgentContext(BaseModel):
    """Internal state passed through the lightweight agent harness."""

    session_id: str = Field(description="Current WebSocket session id.")
    user_id: str | None = Field(default=None, description="Optional application user id.")
    user_message: str = Field(description="Latest user message.")
    message_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent session-level chat messages.",
    )
    latest_request: LightTripRequest | None = Field(
        default=None,
        description="Latest structured lightweight trip request in this session.",
    )
    latest_plan: LightTripPlan | None = Field(
        default=None,
        description="Latest lightweight trip draft in this session.",
    )
    preference_memory: dict[str, Any] = Field(
        default_factory=dict,
        description="Stable user preferences available to the agent.",
    )
    tool_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Deterministic local tool outputs used as model context.",
    )
    skill_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Higher-level skill outputs used as model context.",
    )
    selected_tools: list[str] = Field(
        default_factory=list,
        description="Tool names selected for this agent turn.",
    )
    selected_skills: list[str] = Field(
        default_factory=list,
        description="Skill names selected for this agent turn.",
    )
    trace_id: str | None = Field(
        default=None,
        description="Optional trace id for observability.",
    )
