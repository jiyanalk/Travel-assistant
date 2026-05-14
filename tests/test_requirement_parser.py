from schemas.trip_request import Budget, TripRequest, Travelers
from services.request_parser import detect_missing_fields, parse_trip_request


def test_parse_trip_request_basic_fields(monkeypatch):
    def fake_generate_structured_output(**kwargs):
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

    monkeypatch.setattr(
        "services.request_parser.generate_structured_output",
        fake_generate_structured_output,
    )

    request = parse_trip_request(
        "我想6月从上海去大阪玩5天，2个人，总预算15000，酒店预算300一晚，喜欢美食和拍照，不想太累。"
    )
    assert request.origin == "上海"
    assert request.destination == "大阪"
    assert request.duration_days == 5
    assert request.travelers.adults == 2
    assert request.budget is not None
    assert request.hotel_budget_per_night == 300
    assert request.pace == "relaxed"


def test_detect_missing_fields():
    request = TripRequest(
        destination="大阪",
        duration_days=5,
        travelers=Travelers(adults=1),
        pace="normal",
    )
    missing_fields = detect_missing_fields(request)
    assert "origin" in missing_fields
    assert "budget" in missing_fields
