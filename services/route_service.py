AREA_GROUPS = {
    ("难波", "心斋桥"): (12, 2.2),
    ("梅田", "难波"): (24, 6.8),
    ("浅草", "涩谷"): (35, 12.5),
    ("暹罗", "素坤逸"): (20, 7.0),
}


def estimate_route(area_from: str, area_to: str, travelers_count: int = 1) -> dict:
    if area_from == area_to:
        duration, distance = 10, 1.2
    else:
        duration, distance = (
            AREA_GROUPS.get((area_from, area_to))
            or AREA_GROUPS.get((area_to, area_from))
            or (25, 8.0)
        )

    estimated_cost = _estimate_local_transport_cost(distance_km=distance, travelers_count=travelers_count)
    return {
        "mode": "metro",
        "duration_minutes": duration,
        "distance_km": distance,
        "estimated_cost": estimated_cost,
        "description": f"从 {area_from} 前往 {area_to}，时间与费用为估算值。",
        "is_estimated": True,
    }


def _estimate_local_transport_cost(distance_km: float, travelers_count: int) -> float:
    if distance_km <= 2:
        per_person_cost = 4
    elif distance_km <= 7:
        per_person_cost = 6
    elif distance_km <= 12:
        per_person_cost = 8
    else:
        per_person_cost = 10
    return round(per_person_cost * max(travelers_count, 1), 2)
