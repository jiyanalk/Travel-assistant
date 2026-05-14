from graphs.travel_graph import build_travel_graph
from schemas.trip_request import Budget, TripRequest, Travelers


def test_graph_returns_trip_plan_for_complete_request(monkeypatch):
    def fake_parse(**kwargs):
        return TripRequest(
            origin="上海",
            destination="大阪",
            duration_days=5,
            travelers=Travelers(adults=2),
            budget=Budget(amount=15000, currency="CNY"),
            hotel_budget_per_night=300,
            interests=["美食", "拍照"],
            pace="relaxed",
            special_requirements=["不想太累"],
        )

    def fake_outline(**kwargs):
        from services.itinerary_service import DayOutline, ItineraryOutline

        return ItineraryOutline(
            trip_title="大阪 5 日美食拍照轻松行程",
            summary="测试用模型行程摘要。",
            travel_style=["美食", "拍照", "轻松"],
            days=[
                DayOutline(day=1, theme="抵达大阪与难波夜景", selected_pois=["道顿堀", "黑门市场"]),
                DayOutline(day=2, theme="大阪城与梅田观景", selected_pois=["大阪城公园", "梅田蓝天大厦空中庭园"]),
                DayOutline(day=3, theme="慢游大阪", selected_pois=["道顿堀", "黑门市场"]),
                DayOutline(day=4, theme="拍照与美食", selected_pois=["大阪城公园", "道顿堀"]),
                DayOutline(day=5, theme="返程前轻松收尾", selected_pois=["黑门市场", "道顿堀"]),
            ],
        )

    monkeypatch.setattr("services.request_parser.generate_structured_output", fake_parse)
    monkeypatch.setattr("services.request_parser.generate_text", lambda **kwargs: "请补充信息")
    monkeypatch.setattr("services.itinerary_service.generate_structured_output", fake_outline)

    graph = build_travel_graph()
    result = graph.invoke(
        {
            "user_id": "tester",
            "user_message": "我想6月从上海去大阪玩5天，2个人，总预算15000，酒店预算300一晚，喜欢美食和拍照，不想太累。",
            "agent_steps": [],
        }
    )
    assert result["need_clarification"] is False
    assert result["formatted_trip_plan"].destination == "大阪"
    assert result["formatted_trip_plan"].budget.hotel_recommendations
    assert result["formatted_trip_plan"].days[0].items[0].estimated_cost is not None
