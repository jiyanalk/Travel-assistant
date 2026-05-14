from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import ROOT_DIR
from services.debug_trace import append_debug_trace
from services.llm_service import generate_structured_output


POI_DATA_PATH = ROOT_DIR / "data" / "sample_pois.json"


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


class GeneratedPoiList(BaseModel):
    pois: list[GeneratedPoi]


def load_pois() -> list[dict[str, Any]]:
    return json.loads(POI_DATA_PATH.read_text(encoding="utf-8"))


def search_candidate_pois(
    destination: str,
    interests: list[str],
    limit: int = 30,
    debug_trace: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    destination = destination.strip()
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
        matched.append({**poi, "match_score": round(score, 2)})

    if matched:
        sorted_pois = sorted(
            matched,
            key=lambda item: item.get("match_score", 0),
            reverse=True,
        )[:limit]
        append_debug_trace(
            debug_trace,
            step="search_candidate_pois",
            stage="poi_source",
            label="local_sample",
            payload={
                "destination": destination,
                "matched_count": len(sorted_pois),
            },
        )
        return sorted_pois

    generated = _generate_candidate_pois(
        destination=destination,
        interests=interests,
        limit=limit,
        debug_trace=debug_trace,
    )
    append_debug_trace(
        debug_trace,
        step="search_candidate_pois",
        stage="poi_source",
        label="model_generated",
        payload={
            "destination": destination,
            "matched_count": len(generated),
        },
    )
    return generated


def rank_pois(pois: list[dict[str, Any]], interests: list[str], pace: str) -> list[dict[str, Any]]:
    pace_bonus = {"relaxed": 0.2, "normal": 0.1, "packed": 0}.get(pace, 0)
    ranked = []
    for poi in pois:
        score = poi.get("rating", 0) + pace_bonus
        if any(tag in interests for tag in poi.get("tags", [])):
            score += 1.0
        ranked.append({**poi, "rank_score": round(score, 2)})
    return sorted(ranked, key=lambda item: item["rank_score"], reverse=True)


def _generate_candidate_pois(
    *,
    destination: str,
    interests: list[str],
    limit: int,
    debug_trace: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    result = generate_structured_output(
        model_class=GeneratedPoiList,
        system_prompt=(
            "你是旅行目的地研究助手。\n"
            "请根据目的地和兴趣生成一组合理的候选 POI，供后续行程规划使用。\n"
            "不要输出不存在的字段，所有文案使用中文或当地通用名称。\n"
            "category 只能是 attraction、food、shopping、rest 之一。"
        ),
        user_prompt=(
            f"目的地：{destination}\n"
            f"兴趣：{json.dumps(interests, ensure_ascii=False)}\n"
            f"请返回 {min(max(limit, 6), 12)} 个候选 POI。\n"
            "要求：\n"
            "1. 至少包含 2 个美食或餐饮相关地点。\n"
            "2. area 填写城市中的片区、街区或地标周边。\n"
            "3. price_level 用 1 到 3 的整数表示。\n"
            "4. recommended_duration_minutes 给出合理停留时长。\n"
            "5. source 固定写 model_generated。"
        ),
        temperature=0.3,
        debug_trace=debug_trace,
        trace_step="search_candidate_pois",
        trace_label="generate_candidate_pois",
    )
    return [poi.model_dump() for poi in result.pois[:limit]]


def _normalize_location_text(value: str) -> str:
    normalized = value.strip().lower()
    for suffix in ("市", "区", "县", "特别行政区"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized
