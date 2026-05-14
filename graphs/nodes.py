from __future__ import annotations

from typing import Any

from schemas.trip_plan import TripPlan
from services.budget_service import build_budget
from services.destination_context_service import build_destination_context
from services.itinerary_service import (
    build_trip_plan,
    validate_trip_plan,
)
from services.memory_service import load_user_profile, save_user_preferences
from services.poi_service import rank_pois
from services.request_parser import (
    build_clarification_question,
    detect_missing_fields,
    parse_trip_request,
)


def _append_step(state: dict[str, Any], step: str) -> None:
    state.setdefault("agent_steps", []).append(step)
    _emit_event(
        state,
        {
            "type": "step_start",
            "step": step,
        },
    )


def _trace(state: dict[str, Any], step: str, stage: str, payload: Any = None, label: str | None = None) -> None:
    return None


def _emit_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    emitter = state.get("event_emitter")
    if callable(emitter):
        emitter(event)


def parse_user_request(state: dict[str, Any]) -> dict[str, Any]:
    step = "parse_user_request"
    _append_step(state, step)
    state["trip_request"] = parse_trip_request(
        state["user_message"],
    )
    _trace(state, step, "state_update", state["trip_request"], "trip_request")
    return state


def check_missing_fields(state: dict[str, Any]) -> dict[str, Any]:
    step = "check_missing_fields"
    _append_step(state, step)
    missing_fields = detect_missing_fields(state["trip_request"])
    state["missing_fields"] = missing_fields
    state["need_clarification"] = bool(missing_fields)
    state["clarification_question"] = (
        build_clarification_question(
            user_message=state["user_message"],
            parsed_request=state["trip_request"],
            missing_fields=missing_fields,
        )
        if missing_fields
        else None
    )
    _trace(
        state,
        step,
        "state_update",
        {
            "missing_fields": missing_fields,
            "need_clarification": state["need_clarification"],
            "clarification_question": state["clarification_question"],
        },
        "missing_fields_check",
    )
    return state


def ask_clarification(state: dict[str, Any]) -> dict[str, Any]:
    step = "ask_clarification"
    _append_step(state, step)
    _trace(
        state,
        step,
        "state_update",
        {"clarification_question": state.get("clarification_question")},
        "clarification_output",
    )
    return state


def load_user_memory(state: dict[str, Any]) -> dict[str, Any]:
    step = "load_user_memory"
    _append_step(state, step)
    state["user_profile"] = load_user_profile(state.get("user_id", "guest"))
    _trace(state, step, "state_update", state["user_profile"], "user_profile")
    return state


def prepare_destination_context(state: dict[str, Any]) -> dict[str, Any]:
    step = "prepare_destination_context"
    _append_step(state, step)
    request = state["trip_request"]
    candidate_pois, guide_context = build_destination_context(
        destination=request.destination or "",
        interests=request.interests,
        pace=request.pace,
        poi_limit=24,
    )
    state["candidate_pois"] = candidate_pois
    state["guide_context"] = guide_context
    _trace(
        state,
        step,
        "state_update",
        {
            "candidate_pois": _slim_pois(candidate_pois),
            "guide_context": guide_context[:3],
        },
        "destination_context",
    )
    return state


def rank_and_cluster_pois(state: dict[str, Any]) -> dict[str, Any]:
    step = "rank_and_cluster_pois"
    _append_step(state, step)
    request = state["trip_request"]
    state["ranked_pois"] = rank_pois(
        pois=state.get("candidate_pois", []),
        interests=request.interests,
        pace=request.pace,
    )
    _trace(state, step, "state_update", _slim_pois(state["ranked_pois"]), "ranked_pois")
    return state


def build_daily_itinerary(state: dict[str, Any]) -> dict[str, Any]:
    step = "build_daily_itinerary"
    _append_step(state, step)
    state["draft_itinerary"] = build_trip_plan(
        request=state["trip_request"],
        ranked_pois=state.get("ranked_pois", []),
        guide_context=state.get("guide_context", []),
        user_profile=state.get("user_profile"),
    )
    _trace(state, step, "state_update", state["draft_itinerary"], "draft_itinerary")
    return state


def estimate_routes_and_budget(state: dict[str, Any]) -> dict[str, Any]:
    step = "estimate_routes_and_budget"
    _append_step(state, step)
    request = state["trip_request"]
    state["budget_result"] = build_budget(
        request=request,
        draft_plan=state["draft_itinerary"],
        user_budget=request.budget.amount if request.budget else None,
    )
    _trace(state, step, "state_update", state["budget_result"], "budget_result")
    return state


def validate_itinerary(state: dict[str, Any]) -> dict[str, Any]:
    step = "validate_itinerary"
    _append_step(state, step)
    state["validation_result"] = validate_trip_plan(
        draft_plan=state["draft_itinerary"],
        budget=state.get("budget_result", {}),
        request=state["trip_request"],
    )
    _trace(state, step, "state_update", state["validation_result"], "validation_result")
    return state


def format_trip_plan(state: dict[str, Any]) -> dict[str, Any]:
    step = "format_trip_plan"
    _append_step(state, step)
    state["formatted_trip_plan"] = TripPlan.model_validate(
        {
            **state["draft_itinerary"],
            "budget": state["budget_result"],
        }
    )
    _trace(state, step, "state_update", state["formatted_trip_plan"], "formatted_trip_plan")
    return state


def save_memory(state: dict[str, Any]) -> dict[str, Any]:
    step = "save_memory"
    _append_step(state, step)
    save_user_preferences(
        user_id=state.get("user_id", "guest"),
        request=state["trip_request"],
    )
    _trace(
        state,
        step,
        "state_update",
        {
            "user_id": state.get("user_id", "guest"),
            "saved_request": state["trip_request"],
        },
        "memory_saved",
    )
    return state


def _slim_pois(pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": poi.get("name"),
            "category": poi.get("category"),
            "area": poi.get("area"),
            "tags": poi.get("tags", []),
            "rating": poi.get("rating"),
        }
        for poi in pois[:10]
    ]
