from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import ROOT_DIR
from services.debug_trace import append_debug_trace
from services.llm_service import generate_structured_output
from services.poi_service import load_pois


GUIDES_DIR = ROOT_DIR / "data" / "guides"
SLUG_MAP = {"大阪": "osaka", "东京": "tokyo", "曼谷": "bangkok"}


class GeneratedPoi(BaseModel):
    name: str
    city: str
    country: str | None = None
    category: str = Field(description="attraction / food / shopping / rest")
    area: str
    tags: list[str] = Field(default_factory=list)
    rating: float = 4.3
    price_level: int = 2
    estimated_cost_per_person: float | None = None
    recommended_duration_minutes: int = 90
    address: str | None = None
    source: str = "model_generated"


class DestinationContextResult(BaseModel):
    pois: list[GeneratedPoi]
    guide_paragraphs: list[str] = Field(default_factory=list)


def build_destination_context(
    *,
    destination: str,
    interests: list[str],
    pace: str,
    poi_limit: int = 24,
    debug_trace: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    local_pois = _search_local_candidate_pois(destination=destination, interests=interests, limit=poi_limit)
    local_guide = _read_local_guide(destination=destination, interests=interests, pace=pace)

    if local_pois and local_guide:
        append_debug_trace(
            debug_trace,
            step="prepare_destination_context",
            stage="context_source",
            label="local_context",
            payload={
                "destination": destination,
                "poi_count": len(local_pois),
                "guide_count": len(local_guide),
            },
        )
        return local_pois, local_guide

    generated = _generate_destination_context(
        destination=destination,
        interests=interests,
        pace=pace,
        poi_limit=poi_limit,
        debug_trace=debug_trace,
    )
    pois = [poi.model_dump() for poi in generated.pois[:poi_limit]]
    guide_paragraphs = generated.guide_paragraphs[:3]
    append_debug_trace(
        debug_trace,
        step="prepare_destination_context",
        stage="context_source",
        label="model_generated_context",
        payload={
            "destination": destination,
            "poi_count": len(pois),
            "guide_count": len(guide_paragraphs),
        },
    )
    return pois, guide_paragraphs


def _search_local_candidate_pois(
    *,
    destination: str,
    interests: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    pois = load_pois()
    matched = []
    normalized_destination = _normalize_location_text(destination)

    for poi in pois:
        poi_city = str(poi.get("city", ""))
        if _normalize_location_text(poi_city) != normalized_destination:
            continue
        score = 0.0
        for interest in interests:
            if interest in poi.get("tags", []):
                score += 2
        score += poi.get("rating", 4.0)
        matched.append(
            {
                **poi,
                "estimated_cost_per_person": _estimate_local_poi_cost_per_person(poi),
                "match_score": round(score, 2),
            }
        )

    return sorted(matched, key=lambda item: item.get("match_score", 0), reverse=True)[:limit]


def _read_local_guide(
    *,
    destination: str,
    interests: list[str],
    pace: str,
) -> list[str]:
    slug = SLUG_MAP.get(destination)
    if slug is None:
        return []

    guide_path = GUIDES_DIR / f"{slug}.md"
    if not guide_path.exists():
        return []

    text = guide_path.read_text(encoding="utf-8")
    paragraphs = [segment.strip() for segment in text.split("\n\n") if segment.strip()]
    filtered = []

    for paragraph in paragraphs:
        if any(interest in paragraph for interest in interests) or pace in paragraph:
            filtered.append(paragraph)

    return filtered[:3] or paragraphs[:3]


def _generate_destination_context(
    *,
    destination: str,
    interests: list[str],
    pace: str,
    poi_limit: int,
    debug_trace: list[dict[str, Any]] | None,
) -> DestinationContextResult:
    return generate_structured_output(
        model_class=DestinationContextResult,
        system_prompt=(
            "你是旅行目的地研究助手。\n"
            "请为指定目的地一次性生成两类信息：\n"
            "1. 用于后续行程规划的候选 POI\n"
            "2. 用于安排行程节奏和区域分配的攻略摘要\n"
            "所有输出都要尽量实用、简洁、可执行。\n"
            "category 只能是 attraction、food、shopping、rest 之一。"
        ),
        user_prompt=(
            f"目的地：{destination}\n"
            f"兴趣：{json.dumps(interests, ensure_ascii=False)}\n"
            f"节奏：{pace}\n"
            f"请返回 {min(max(poi_limit, 6), 12)} 个候选 POI 和 3 段攻略摘要。\n"
            "要求：\n"
            "1. 至少包含 2 个美食或餐饮相关地点。\n"
            "2. POI 的 area 填写城市中的片区、街区或地标周边。\n"
            "3. price_level 用 1 到 3 的整数表示。\n"
            "4. recommended_duration_minutes 给出合理停留时长。\n"
            "5. estimated_cost_per_person 给出单人预估花费，餐饮填人均，景点填门票或体验费。\n"
            "6. source 固定写 model_generated。\n"
            "7. guide_paragraphs 分别覆盖：区域安排建议、兴趣导向建议、交通/节奏提醒。"
        ),
        temperature=0.25,
        debug_trace=debug_trace,
        trace_step="prepare_destination_context",
        trace_label="generate_destination_context",
    )


def _normalize_location_text(value: str) -> str:
    normalized = value.strip().lower()
    for suffix in ("市", "区", "县", "特别行政区"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized


def _estimate_local_poi_cost_per_person(poi: dict[str, Any]) -> float:
    category = poi.get("category")
    price_level = int(poi.get("price_level", 1) or 1)
    if category == "food":
        return float({1: 45, 2: 90, 3: 160}.get(price_level, 90))
    if category == "attraction":
        return float({1: 40, 2: 85, 3: 150}.get(price_level, 85))
    if category == "shopping":
        return float({1: 60, 2: 120, 3: 220}.get(price_level, 120))
    return float({1: 20, 2: 35, 3: 55}.get(price_level, 35))
