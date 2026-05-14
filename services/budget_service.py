from __future__ import annotations

from typing import Any

from schemas.trip_request import TripRequest
from services.hotel_service import recommend_hotels


def build_budget(
    *,
    request: TripRequest,
    draft_plan: dict[str, Any],
    user_budget: float | None = None,
    debug_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    travelers_count = max(
        request.travelers.adults + request.travelers.children + request.travelers.seniors,
        1,
    )
    duration_days = request.duration_days or max(len(draft_plan.get("days", [])), 1)
    hotel_nights = max(duration_days - 1, 1)

    planned_day_costs = [
        round(float(day.get("estimated_cost", 0)), 2)
        for day in draft_plan.get("days", [])
    ]
    itinerary_total = round(sum(planned_day_costs), 2)

    target_hotel_price = _resolve_target_hotel_price(
        request=request,
        travelers_count=travelers_count,
        hotel_nights=hotel_nights,
    )
    hotel_recommendations = recommend_hotels(
        destination=request.destination or "",
        target_nightly_price=target_hotel_price,
        travelers_count=travelers_count,
        special_requirements=request.special_requirements,
        debug_trace=debug_trace,
    )
    hotel_total = round((target_hotel_price or 0) * hotel_nights, 2)
    estimated_total = round(itinerary_total + hotel_total, 2)

    if user_budget is None:
        status = "unknown"
    elif estimated_total <= user_budget:
        status = "within_budget"
    elif estimated_total <= user_budget * 1.1:
        status = "slightly_over"
    else:
        status = "over_budget"

    return {
        "currency": request.budget.currency if request.budget else "CNY",
        "user_budget": user_budget,
        "hotel_budget_per_night": target_hotel_price,
        "estimated_total": estimated_total,
        "hotel_total": hotel_total,
        "status": status,
        "hotel_recommendations": [
            recommendation.model_dump()
            for recommendation in hotel_recommendations
        ],
        "is_estimated": True,
    }


def _resolve_target_hotel_price(
    *,
    request: TripRequest,
    travelers_count: int,
    hotel_nights: int,
) -> float:
    if request.hotel_budget_per_night:
        return round(request.hotel_budget_per_night, 2)

    if request.budget:
        hotel_budget_ratio = 0.32 if request.pace == "relaxed" else 0.28
        derived = request.budget.amount * hotel_budget_ratio / max(hotel_nights, 1)
        if travelers_count >= 3:
            derived *= 1.2
        return round(max(derived, 120), 2)

    fallback = 220 if request.destination in {"曼谷"} else 320
    if travelers_count >= 3:
        fallback *= 1.2
    return round(fallback, 2)
