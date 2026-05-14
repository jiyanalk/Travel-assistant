from schemas.trip_plan import TripPlan


def test_trip_plan_schema_validation():
    payload = {
        "trip_title": "大阪 3 日旅行计划",
        "destination": "大阪",
        "duration_days": 3,
        "travel_style": ["美食"],
        "summary": "测试用行程。",
        "days": [
            {
                "day": 1,
                "theme": "测试日程",
                "pace": "relaxed",
                "items": [
                    {
                        "time": "10:00",
                        "type": "attraction",
                        "title": "道顿堀",
                        "estimated_cost": 80,
                        "transport_to_next": {
                            "mode": "metro",
                            "estimated_cost": 12,
                            "is_estimated": True,
                        },
                    }
                ],
                "estimated_cost": 92,
            }
        ],
        "budget": {
            "currency": "CNY",
            "estimated_total": 1200,
            "hotel_total": 600,
            "status": "within_budget",
            "hotel_recommendations": [
                {
                    "name": "大阪心斋桥城市酒店",
                    "area": "心斋桥",
                    "nightly_price": 300,
                    "is_estimated": True,
                    "source": "local_sample",
                }
            ],
        },
    }
    plan = TripPlan.model_validate(payload)
    assert plan.destination == "大阪"
    assert plan.budget.hotel_total == 600
