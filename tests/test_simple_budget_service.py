from services.simple_budget_service import estimate_simple_budget


def test_simple_budget_returns_unavailable_when_missing_info():
    result = estimate_simple_budget(days=3, people=None, budget=3000)

    assert result == {
        "available": False,
        "summary": "预算信息不足，暂时只能给出粗略建议。",
    }


def test_simple_budget_detects_economy_level():
    result = estimate_simple_budget(days=3, people=2, budget=1200)

    assert result["available"] is True
    assert result["total_budget"] == 1200
    assert result["per_person_total"] == 600
    assert result["per_person_per_day"] == 200
    assert result["level"] == "经济型"


def test_simple_budget_detects_comfort_level():
    result = estimate_simple_budget(days=3, people=2, budget=3600)

    assert result["available"] is True
    assert result["per_person_per_day"] == 600
    assert result["level"] == "舒适型"


def test_simple_budget_detects_high_budget_level():
    result = estimate_simple_budget(days=2, people=2, budget=4000)

    assert result["available"] is True
    assert result["per_person_per_day"] == 1000
    assert result["level"] == "高预算型"
