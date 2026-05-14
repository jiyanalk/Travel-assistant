from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from schemas.trip_plan import TripPlan
from schemas.trip_request import TripRequest
from services.debug_trace import append_debug_trace
from services.llm_service import generate_structured_output, load_prompt
from services.route_service import estimate_route


PACE_LIMITS = {
    "relaxed": 2,
    "normal": 3,
    "packed": 4,
}


class DayOutline(BaseModel):
    day: int
    theme: str
    selected_pois: list[str] = Field(default_factory=list)
    lunch_hint: str | None = None
    dinner_hint: str | None = None
    backup_plan: str | None = None
    transport_summary: str | None = None


class ItineraryOutline(BaseModel):
    trip_title: str
    summary: str
    travel_style: list[str] = Field(default_factory=list)
    days: list[DayOutline]
    backup_plans: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RevisionResult(BaseModel):
    changes: list[str] = Field(default_factory=list)
    updated_trip_plan: TripPlan


def build_trip_plan(
    request: TripRequest,
    ranked_pois: list[dict[str, Any]],
    guide_context: list[str],
    user_profile,
    debug_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prompt = load_prompt("itinerary_prompt.md")
    outline = generate_structured_output(
        model_class=ItineraryOutline,
        system_prompt=prompt,
        user_prompt=(
            "请根据旅行需求、候选 POI 和攻略片段，规划一个旅行行程大纲。\n"
            "要求：\n"
            "1. 只返回每天的主题、POI 选择、餐饮提示、交通摘要和备选方案。\n"
            "2. selected_pois 只能从给定候选 POI 名称中选择。\n"
            "3. 节奏必须匹配 pace，不要过满。\n"
            "4. 所有文案都用中文。\n"
            "5. 不要输出 budget 字段。\n"
            f"TripRequest:\n{json.dumps(request.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"候选 POI:\n{json.dumps(_slim_pois(ranked_pois), ensure_ascii=False, indent=2)}\n\n"
            f"攻略片段:\n{json.dumps(guide_context[:3], ensure_ascii=False, indent=2)}\n\n"
            f"用户画像:\n{json.dumps(user_profile.model_dump() if user_profile else {}, ensure_ascii=False, indent=2)}"
        ),
        temperature=0.25,
        debug_trace=debug_trace,
        trace_step="build_daily_itinerary",
        trace_label="initial_outline",
    )

    append_debug_trace(
        debug_trace,
        step="build_daily_itinerary",
        stage="outline_result",
        label="initial_outline",
        payload=outline,
    )

    draft = _build_plan_from_outline(
        outline=outline,
        request=request,
        ranked_pois=ranked_pois,
        guide_context=guide_context,
        debug_trace=debug_trace,
    )
    append_debug_trace(
        debug_trace,
        step="build_daily_itinerary",
        stage="draft_itinerary",
        payload=draft,
    )
    return draft


def validate_trip_plan(
    draft_plan: dict[str, Any],
    budget: dict[str, Any],
    request: TripRequest | dict,
) -> dict[str, Any]:
    if isinstance(request, dict):
        request = TripRequest.model_validate(request)

    issues: list[str] = []
    daily_limit = PACE_LIMITS.get(request.pace, 3) + 2
    for day in draft_plan["days"]:
        attraction_count = len(
            [item for item in day["items"] if item["type"] in {"attraction", "food"}]
        )
        if attraction_count > daily_limit:
            issues.append(f"第 {day['day']} 天安排偏满。")
        if not any(item["type"] in {"food", "rest"} for item in day["items"]):
            issues.append(f"第 {day['day']} 天缺少餐饮或休息安排。")
        if not day.get("backup_plan"):
            issues.append(f"第 {day['day']} 天缺少备选方案。")

    if budget.get("status") == "over_budget":
        issues.append("总预算超过用户预算。")

    return {"passed": not issues, "issues": issues}


def revise_trip_plan_from_message(
    *,
    current_plan: TripPlan,
    message: str,
    debug_trace: list[dict[str, Any]] | None = None,
) -> tuple[TripPlan, list[str]]:
    revision = generate_structured_output(
        model_class=RevisionResult,
        system_prompt=(
            "你是旅行规划修改助手。\n"
            "请根据用户的最新要求，在尽量保留原有合理安排的前提下修改当前 TripPlan。\n"
            "updated_trip_plan 必须返回完整 TripPlan。\n"
            "changes 只返回简短中文变更摘要列表。"
        ),
        user_prompt=(
            f"当前 TripPlan:\n{json.dumps(current_plan.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"用户最新要求：{message}\n\n"
            "请输出完整修改结果，不要省略预算、每天行程、warnings 或 sources。"
        ),
        temperature=0.2,
        debug_trace=debug_trace,
        trace_step="revise_trip_plan",
        trace_label="revision_result",
    )
    append_debug_trace(
        debug_trace,
        step="revise_trip_plan",
        stage="revision_result",
        payload=revision,
    )
    return revision.updated_trip_plan, revision.changes


def _build_plan_from_outline(
    *,
    outline: ItineraryOutline,
    request: TripRequest,
    ranked_pois: list[dict[str, Any]],
    guide_context: list[str],
    debug_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not outline.days:
        raise ValueError("模型没有返回任何行程天数。")
    if not ranked_pois:
        raise ValueError("当前没有可用于生成行程的候选 POI。")

    poi_lookup = {poi["name"].strip(): poi for poi in ranked_pois}
    daily_limit = PACE_LIMITS.get(request.pace, 3)
    days: list[dict[str, Any]] = []
    used_poi_names: set[str] = set()

    for day_outline in outline.days:
        selected: list[dict[str, Any]] = []
        for name in day_outline.selected_pois:
            poi = poi_lookup.get(name.strip())
            if poi is None or poi["name"] in used_poi_names:
                continue
            selected.append(poi)
            used_poi_names.add(poi["name"])
        selected = selected[:daily_limit]

        if not selected:
            selected = _fallback_day_pois(
                ranked_pois=ranked_pois,
                used_poi_names=used_poi_names,
                daily_limit=daily_limit,
                day_number=day_outline.day,
            )
            append_debug_trace(
                debug_trace,
                step="build_daily_itinerary",
                stage="outline_repair",
                label=f"day_{day_outline.day}_fallback_pois",
                payload={
                    "reason": "模型未提供可用 POI，已按候选池自动补齐。",
                    "selected_pois": [poi["name"] for poi in selected],
                },
            )

        days.append(
            _compose_day_plan(
                day_number=day_outline.day,
                theme=day_outline.theme,
                selected_pois=selected,
                request=request,
                backup_plan=day_outline.backup_plan
                or (
                    guide_context[(day_outline.day - 1) % len(guide_context)]
                    if guide_context
                    else "如遇下雨，可优先切换到室内方案。"
                ),
                transport_summary=day_outline.transport_summary or "以地铁和步行为主，交通时间与费用为估算值。",
                lunch_hint=day_outline.lunch_hint,
                dinner_hint=day_outline.dinner_hint,
            )
        )

    return {
        "trip_title": outline.trip_title,
        "destination": request.destination or "待确认目的地",
        "duration_days": request.duration_days or len(days),
        "travel_style": outline.travel_style or request.interests or ["城市漫游"],
        "summary": outline.summary,
        "days": days,
        "backup_plans": outline.backup_plans or [
            "雨天优先切换至室内景点、商场或观景台。",
            "体力不足时可以删减一个下午景点并增加休息。",
        ],
        "warnings": outline.warnings or [
            "价格为估算值，实际价格会受日期、库存和淡旺季影响。",
            "交通时间与交通费用为估算值，建议后续接入地图 API 做校准。",
            "营业时间、签证和天气请以官方及实时信息为准。",
        ],
        "sources": _merge_sources([], request.destination),
    }


def _fallback_day_pois(
    *,
    ranked_pois: list[dict[str, Any]],
    used_poi_names: set[str],
    daily_limit: int,
    day_number: int,
) -> list[dict[str, Any]]:
    fallback: list[dict[str, Any]] = []
    pool = [poi for poi in ranked_pois if poi["name"] not in used_poi_names]
    if not pool:
        pool = ranked_pois

    start_index = ((max(day_number, 1) - 1) * max(daily_limit, 1)) % len(pool)
    rotated_pool = pool[start_index:] + pool[:start_index]

    for poi in rotated_pool:
        if len(fallback) >= daily_limit:
            break
        fallback.append(poi)
        used_poi_names.add(poi["name"])

    return fallback


def _compose_day_plan(
    *,
    day_number: int,
    theme: str,
    selected_pois: list[dict[str, Any]],
    request: TripRequest,
    backup_plan: str,
    transport_summary: str,
    lunch_hint: str | None = None,
    dinner_hint: str | None = None,
) -> dict[str, Any]:
    travelers_count = max(
        request.travelers.adults + request.travelers.children + request.travelers.seniors,
        1,
    )
    items: list[dict[str, Any]] = []

    for index, poi in enumerate(selected_pois):
        item_type = "food" if poi["category"] == "food" else "attraction"
        time_slot = ["10:30", "12:30", "15:00", "18:30"][index % 4]
        cost_per_person = _estimate_item_cost_per_person(poi)
        estimated_item_cost = round(cost_per_person * travelers_count, 2)
        item = {
            "time": time_slot,
            "type": item_type,
            "title": poi["name"],
            "location": poi["area"],
            "duration_minutes": poi["recommended_duration_minutes"],
            "estimated_cost": estimated_item_cost,
            "is_cost_estimated": True,
            "reason": f"匹配兴趣标签：{', '.join(poi.get('tags', [])[:3]) or '综合推荐'}。",
            "notes": _build_cost_note(
                item_type=item_type,
                cost_per_person=cost_per_person,
                travelers_count=travelers_count,
                poi=poi,
            ),
        }
        items.append(item)

    if not any(item["type"] == "food" for item in items):
        lunch_cost_per_person = 80
        items.append(
            {
                "time": "12:30",
                "type": "food",
                "title": lunch_hint or f"{request.destination or '目的地'}特色午餐",
                "location": selected_pois[0]["area"] if selected_pois else (request.destination or "目的地"),
                "duration_minutes": 75,
                "estimated_cost": round(lunch_cost_per_person * travelers_count, 2),
                "is_cost_estimated": True,
                "reason": "补足当日餐饮安排。",
                "notes": f"按人均 {lunch_cost_per_person:.0f} 元估算，合计 {lunch_cost_per_person * travelers_count:.0f} 元。",
            }
        )

    if request.pace == "relaxed":
        rest_cost_per_person = 35
        items.append(
            {
                "time": "16:30",
                "type": "rest",
                "title": dinner_hint or "咖啡休息",
                "location": selected_pois[0]["area"] if selected_pois else (request.destination or "目的地"),
                "duration_minutes": 45,
                "estimated_cost": round(rest_cost_per_person * travelers_count, 2),
                "is_cost_estimated": True,
                "reason": "轻松节奏默认安排休息点。",
                "notes": f"按人均 {rest_cost_per_person:.0f} 元估算，合计 {rest_cost_per_person * travelers_count:.0f} 元。",
            }
        )

    _fill_transport(items, travelers_count=travelers_count)
    estimated_cost = round(
        sum(item.get("estimated_cost", 0) or 0 for item in items)
        + sum(item.get("transport_to_next", {}).get("estimated_cost", 0) or 0 for item in items),
        2,
    )
    return {
        "day": day_number,
        "date": request.start_date,
        "theme": theme,
        "pace": request.pace,
        "items": items,
        "estimated_cost": estimated_cost,
        "transport_summary": transport_summary,
        "backup_plan": backup_plan,
    }


def _estimate_item_cost_per_person(poi: dict[str, Any]) -> float:
    explicit = poi.get("estimated_cost_per_person")
    if explicit is not None:
        return float(explicit)

    category = poi.get("category")
    price_level = int(poi.get("price_level", 1) or 1)
    if category == "food":
        return float({1: 45, 2: 90, 3: 160}.get(price_level, 90))
    if category == "attraction":
        return float({1: 40, 2: 85, 3: 150}.get(price_level, 85))
    if category == "shopping":
        return float({1: 60, 2: 120, 3: 220}.get(price_level, 120))
    return float({1: 20, 2: 35, 3: 55}.get(price_level, 35))


def _build_cost_note(
    *,
    item_type: str,
    cost_per_person: float,
    travelers_count: int,
    poi: dict[str, Any],
) -> str:
    total = round(cost_per_person * travelers_count, 2)
    if item_type == "food":
        return f"按人均 {cost_per_person:.0f} 元估算，{travelers_count} 人合计约 {total:.0f} 元。"
    if item_type == "attraction":
        return f"门票或体验费按人均 {cost_per_person:.0f} 元估算，{travelers_count} 人合计约 {total:.0f} 元。"
    return (
        f"该项目按人均 {cost_per_person:.0f} 元估算，{travelers_count} 人合计约 {total:.0f} 元。"
        f" 参考区域：{poi.get('area', '未提供')}。"
    )


def _fill_transport(items: list[dict[str, Any]], travelers_count: int) -> None:
    for index, item in enumerate(items[:-1]):
        next_item = items[index + 1]
        if item.get("transport_to_next"):
            continue
        current_location = item.get("location")
        next_location = next_item.get("location")
        if current_location and next_location:
            item["transport_to_next"] = estimate_route(
                current_location,
                next_location,
                travelers_count=travelers_count,
            )


def _merge_sources(existing_sources: list[str], destination: str | None) -> list[str]:
    sources = set(existing_sources or [])
    sources.add("data/sample_pois.json")
    sources.add("data/sample_hotels.json")
    if destination:
        slug = _destination_to_slug(destination)
        if slug is not None:
            sources.add(f"data/guides/{slug}.md")
        else:
            sources.add("llm://generated-destination-context")
            sources.add("llm://generated-hotel-recommendations")
    return sorted(sources)


def _destination_to_slug(destination: str) -> str | None:
    mapping = {"大阪": "osaka", "东京": "tokyo", "曼谷": "bangkok"}
    return mapping.get(destination)


def _slim_pois(pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": poi["name"],
            "category": poi["category"],
            "area": poi["area"],
            "tags": poi.get("tags", []),
            "rating": poi.get("rating"),
            "estimated_cost_per_person": poi.get("estimated_cost_per_person"),
            "recommended_duration_minutes": poi.get("recommended_duration_minutes"),
        }
        for poi in pois[:12]
    ]
