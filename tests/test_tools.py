from services.poi_service import GeneratedPoi, GeneratedPoiList, search_candidate_pois
from services.rag_service import GuideContextResult, retrieve_guide_context
from tools.budget_tools import estimate_budget
from tools.poi_tools import search_pois


def test_budget_tool_returns_total_and_hotels():
    result = estimate_budget("大阪", 5, 2, "relaxed", 15000)
    assert result["estimated_total"] > 0
    assert result["hotel_total"] > 0
    assert result["hotel_recommendations"]


def test_poi_tool_returns_results():
    results = search_pois("大阪", ["美食", "拍照"], limit=5)
    assert results
    assert results[0]["city"] == "大阪"


def test_search_candidate_pois_falls_back_to_model(monkeypatch):
    def fake_generate_structured_output(**kwargs):
        return GeneratedPoiList(
            pois=[
                GeneratedPoi(
                    name="卢浮宫",
                    city="巴黎",
                    country="法国",
                    category="attraction",
                    area="第一区",
                    tags=["艺术", "拍照"],
                    rating=4.8,
                    price_level=2,
                    estimated_cost_per_person=140,
                    recommended_duration_minutes=180,
                    address="Rue de Rivoli",
                ),
                GeneratedPoi(
                    name="圣日耳曼甜品店",
                    city="巴黎",
                    country="法国",
                    category="food",
                    area="圣日耳曼",
                    tags=["美食", "咖啡"],
                    rating=4.5,
                    price_level=2,
                    estimated_cost_per_person=90,
                    recommended_duration_minutes=75,
                    address="Saint-Germain",
                ),
            ]
        )

    monkeypatch.setattr(
        "services.poi_service.generate_structured_output",
        fake_generate_structured_output,
    )

    results = search_candidate_pois("巴黎", ["艺术", "美食"], limit=5)
    assert results
    assert results[0]["city"] == "巴黎"
    assert results[0]["source"] == "model_generated"


def test_retrieve_guide_context_falls_back_to_model(monkeypatch):
    def fake_generate_structured_output(**kwargs):
        return GuideContextResult(
            paragraphs=[
                "巴黎适合按左岸、右岸和塞纳河沿线分区安排。",
                "如果偏好艺术与美食，可以把博物馆和街区餐馆穿插安排。",
                "热门景点排队时间较长，建议预留交通和休息弹性。",
            ]
        )

    monkeypatch.setattr(
        "services.rag_service.generate_structured_output",
        fake_generate_structured_output,
    )

    paragraphs = retrieve_guide_context("巴黎", ["艺术", "美食"], "relaxed")
    assert len(paragraphs) == 3
    assert "巴黎" in paragraphs[0]
