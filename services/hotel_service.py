from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import ROOT_DIR
from schemas.budget import HotelRecommendation
from services.llm_service import generate_structured_output


HOTEL_DATA_PATH = ROOT_DIR / "data" / "sample_hotels.json"


class GeneratedHotelRecommendation(BaseModel):
    name: str
    area: str
    nightly_price: float
    rating: float | None = None
    reason: str | None = None
    booking_hint: str | None = None
    is_estimated: bool = True
    source: str = "model_generated"


class GeneratedHotelRecommendationList(BaseModel):
    hotels: list[GeneratedHotelRecommendation] = Field(default_factory=list)


def recommend_hotels(
    *,
    destination: str,
    target_nightly_price: float | None,
    travelers_count: int,
    special_requirements: list[str] | None = None,
    debug_trace: list[dict[str, Any]] | None = None,
) -> list[HotelRecommendation]:
    local = _search_local_hotels(
        destination=destination,
        target_nightly_price=target_nightly_price,
        travelers_count=travelers_count,
    )
    if local:
        return [HotelRecommendation.model_validate(item) for item in local[:3]]

    result = generate_structured_output(
        model_class=GeneratedHotelRecommendationList,
        system_prompt=(
            "你是旅行住宿推荐助手。\n"
            "请根据目的地、预算和人数推荐适合的酒店或住宿。\n"
            "返回的 nightly_price 必须尽量贴近预算，适当上下浮动但不要离谱。"
        ),
        user_prompt=(
            f"目的地：{destination}\n"
            f"每晚酒店预算：{target_nightly_price if target_nightly_price is not None else '未指定'}\n"
            f"出行人数：{travelers_count}\n"
            f"特殊要求：{json.dumps(special_requirements or [], ensure_ascii=False)}\n"
            "请返回 3 个住宿推荐。\n"
            "要求：\n"
            "1. reason 说明为什么这个住宿与预算和行程风格匹配。\n"
            "2. booking_hint 给出预订建议，比如适合地铁沿线、适合早订等。\n"
            "3. source 固定写 model_generated。"
        ),
        temperature=0.25,
        debug_trace=debug_trace,
        trace_step="estimate_routes_and_budget",
        trace_label="hotel_recommendations",
    )
    return [HotelRecommendation.model_validate(item.model_dump()) for item in result.hotels[:3]]


def _search_local_hotels(
    *,
    destination: str,
    target_nightly_price: float | None,
    travelers_count: int,
) -> list[dict[str, Any]]:
    hotels = json.loads(HOTEL_DATA_PATH.read_text(encoding="utf-8"))
    matches = [hotel for hotel in hotels if hotel.get("city") == destination]
    if not matches:
        return []

    target = target_nightly_price or _derive_default_hotel_target(matches, travelers_count)
    for hotel in matches:
        hotel["price_gap"] = abs(hotel["nightly_price"] - target)
        hotel["is_estimated"] = True
    sorted_matches = sorted(matches, key=lambda item: (item["price_gap"], -item.get("rating", 0)))
    return [
        {
            "name": hotel["name"],
            "area": hotel["area"],
            "nightly_price": hotel["nightly_price"],
            "rating": hotel.get("rating"),
            "reason": hotel.get("reason"),
            "booking_hint": hotel.get("booking_hint"),
            "is_estimated": True,
            "source": hotel.get("source", "local_sample"),
        }
        for hotel in sorted_matches
    ]


def _derive_default_hotel_target(hotels: list[dict[str, Any]], travelers_count: int) -> float:
    average = sum(hotel["nightly_price"] for hotel in hotels) / max(len(hotels), 1)
    if travelers_count >= 3:
        average *= 1.2
    return round(average, 2)
