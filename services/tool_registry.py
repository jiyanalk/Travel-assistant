from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.agent_context import AgentContext
from schemas.light_trip import LightTripPlan, LightTripRequest
from services.city_alias_service import (
    CITY_ALIASES,
    detect_aliases_in_text,
    normalize_request_destination,
)
from services.light_rag_service import get_rag_context
from services.preference_extractor_service import extract_preference_updates
from services.request_merge_service import merge_light_trip_request
from services.retrieval_service import CITY_FILE_MAP
from services.simple_budget_service import estimate_simple_budget


ToolCallable = Callable[[AgentContext], Awaitable[dict[str, Any]] | dict[str, Any]]


class ToolSpec(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    intents: list[str] = Field(default_factory=list)
    func: ToolCallable


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool_spec: ToolSpec) -> None:
        self._tools[tool_spec.name] = tool_spec

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def select_tools(self, context: AgentContext) -> list[str]:
        selected: list[str] = []
        if _should_select_rag(context):
            selected.append("rag_context_tool")
        alias_output = detect_aliases_in_text(context.user_message)
        if alias_output["replaced"]:
            selected.append("city_alias_tool")
        if _request_has_budget_inputs(context.latest_request):
            selected.append("simple_budget_tool")
        if context.latest_plan is not None:
            selected.append("trip_quality_check_tool")
        if extract_preference_updates(context.user_message).get("should_update"):
            selected.append("preference_extractor_tool")
        return [name for name in selected if name in self._tools]

    async def run_tool(self, name: str, context: AgentContext) -> dict[str, Any]:
        tool = self.get(name)
        result = tool.func(context)
        if inspect.isawaitable(result):
            result = await result
        return dict(result or {})

    async def run_tools(
        self,
        tool_names: list[str],
        context: AgentContext,
    ) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for name in tool_names:
            outputs[name] = await self.run_tool(name, context)
        return outputs


def create_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="rag_context_tool",
            description="Retrieve lightweight local Markdown city knowledge for prompt grounding.",
            intents=["collect_info", "draft_plan", "revise_plan"],
            func=rag_context_tool,
        )
    )
    registry.register(
        ToolSpec(
            name="city_alias_tool",
            description="Normalize common Chinese city aliases in messages and destinations.",
            intents=["collect_info", "draft_plan", "revise_plan"],
            func=city_alias_tool,
        )
    )
    registry.register(
        ToolSpec(
            name="trip_request_merge_tool",
            description="Merge newly extracted request fields into session request.",
            intents=["collect_info", "draft_plan", "revise_plan", "budget_estimate"],
            func=trip_request_merge_tool,
        )
    )
    registry.register(
        ToolSpec(
            name="preference_extractor_tool",
            description="Extract stable long-term preferences from explicit memory requests.",
            intents=["chat", "collect_info", "draft_plan", "revise_plan"],
            func=preference_extractor_tool,
        )
    )
    registry.register(
        ToolSpec(
            name="simple_budget_tool",
            description="Estimate broad budget level from days, people and total budget.",
            intents=["draft_plan", "budget_estimate", "revise_plan"],
            func=simple_budget_tool,
        )
    )
    registry.register(
        ToolSpec(
            name="trip_quality_check_tool",
            description="Check whether a lightweight plan roughly matches days and pacing.",
            intents=["draft_plan", "revise_plan"],
            func=trip_quality_check_tool,
        )
    )
    return registry


def _request_from_context(context: AgentContext) -> LightTripRequest | None:
    candidate = context.tool_context.get("updated_request") or context.latest_request
    if candidate is None:
        return None
    if isinstance(candidate, LightTripRequest):
        return candidate
    return LightTripRequest.model_validate(candidate)


def _plan_from_context(context: AgentContext) -> LightTripPlan | None:
    candidate = context.tool_context.get("updated_plan") or context.latest_plan
    if candidate is None:
        return None
    if isinstance(candidate, LightTripPlan):
        return candidate
    return LightTripPlan.model_validate(candidate)


def _request_has_budget_inputs(request: LightTripRequest | None) -> bool:
    return (
        request is not None
        and request.days is not None
        and request.people is not None
        and request.budget is not None
    )


def _should_select_rag(context: AgentContext) -> bool:
    request = _request_from_context(context)
    if request and request.destination:
        return True
    message = context.user_message or ""
    if detect_aliases_in_text(message).get("replaced"):
        return True
    if any(city in message for city in CITY_FILE_MAP):
        return True
    travel_terms = ["旅行", "旅游", "行程", "玩", "路线", "攻略", "周末", "city walk"]
    return any(term in message for term in travel_terms)


def rag_context_tool(context: AgentContext) -> dict[str, Any]:
    request = _request_from_context(context)
    destination = request.destination if request else None
    interests = request.interests if request else []
    return get_rag_context(
        destination=destination,
        interests=interests,
        user_message=context.user_message,
    )


def city_alias_tool(context: AgentContext) -> dict[str, Any]:
    request = _request_from_context(context)
    normalized_request, request_alias_output = normalize_request_destination(request)
    message_alias_output = detect_aliases_in_text(context.user_message)
    output = {
        "available": True,
        "message_aliases": message_alias_output,
        "request_aliases": request_alias_output,
        "replaced": bool(
            message_alias_output.get("replaced") or request_alias_output.get("replaced")
        ),
    }
    if normalized_request is not None:
        output["normalized_request"] = normalized_request.model_dump(mode="json")
        output["destination"] = normalized_request.destination
    return output


def trip_request_merge_tool(context: AgentContext) -> dict[str, Any]:
    new_request = context.tool_context.get("updated_request")
    new_request_model = (
        LightTripRequest.model_validate(new_request)
        if new_request is not None
        else None
    )
    merged = merge_light_trip_request(context.latest_request, new_request_model)
    return {
        "available": merged is not None,
        "merged_request": merged.model_dump(mode="json") if merged else None,
    }


def preference_extractor_tool(context: AgentContext) -> dict[str, Any]:
    return extract_preference_updates(context.user_message)


def simple_budget_tool(context: AgentContext) -> dict[str, Any]:
    request = _request_from_context(context)
    if request is None:
        return estimate_simple_budget(days=None, people=None, budget=None)
    return estimate_simple_budget(
        days=request.days,
        people=request.people,
        budget=request.budget,
    )


def trip_quality_check_tool(context: AgentContext) -> dict[str, Any]:
    request = _request_from_context(context)
    plan = _plan_from_context(context)

    checks: list[str] = []
    warnings: list[str] = []
    if request is None or not request.destination:
        warnings.append("missing_destination")
    if request is None or request.budget is None:
        warnings.append("missing_budget")

    if plan is None:
        warnings.append("missing_plan")
        return {
            "available": False,
            "warnings": warnings,
            "checks": checks,
            "summary": "No lightweight plan is available for quality checking.",
        }

    expected_days = plan.days or (request.days if request else None)
    daily_count = len(plan.daily_plan)
    if expected_days is not None:
        if daily_count == expected_days:
            checks.append("daily_plan_matches_days")
        else:
            warnings.append("daily_plan_days_mismatch")

    busy_days = [
        index + 1
        for index, item in enumerate(plan.daily_plan)
        if _looks_too_busy(item)
    ]
    if busy_days:
        warnings.append("possibly_too_busy")

    return {
        "available": True,
        "warnings": warnings,
        "checks": checks,
        "busy_days": busy_days,
        "summary": "Lightweight plan quality check completed.",
    }


def _looks_too_busy(day_plan: str) -> bool:
    separators = ["，", ",", "、", "->", "-", "；", ";"]
    activity_count = sum(day_plan.count(separator) for separator in separators) + 1
    return activity_count >= 6 or len(day_plan) > 160


default_tool_registry = create_default_tool_registry()
