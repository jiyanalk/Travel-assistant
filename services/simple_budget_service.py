from __future__ import annotations

from typing import Optional


def estimate_simple_budget(
    days: Optional[int],
    people: Optional[int],
    budget: Optional[float],
) -> dict:
    """Estimate a lightweight budget level without model or price lookup."""

    if not _is_positive_number(days) or not _is_positive_number(people) or not _is_positive_number(budget):
        return {
            "available": False,
            "summary": "预算信息不足，暂时只能给出粗略建议。",
        }

    safe_days = int(days)
    safe_people = int(people)
    total_budget = round(float(budget), 2)
    per_person_total = round(total_budget / safe_people, 2)
    per_person_per_day = round(per_person_total / safe_days, 2)
    level = _budget_level(per_person_per_day)

    return {
        "available": True,
        "total_budget": total_budget,
        "per_person_total": per_person_total,
        "per_person_per_day": per_person_per_day,
        "level": level,
        "summary": (
            f"总预算约 {total_budget:g} 元，"
            f"人均约 {per_person_total:g} 元，"
            f"人均每天约 {per_person_per_day:g} 元，属于{level}。"
        ),
    }


def _budget_level(per_person_per_day: float) -> str:
    if per_person_per_day < 300:
        return "经济型"
    if per_person_per_day <= 800:
        return "舒适型"
    return "高预算型"


def _is_positive_number(value: Optional[float]) -> bool:
    if value is None:
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False
