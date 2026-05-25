from services.light_rag_service import get_rag_context


def test_light_rag_service_returns_available_context():
    output = get_rag_context(
        destination="成都",
        interests=["美食", "city walk"],
        user_message="我想去成都玩三天，喜欢美食和city walk",
    )

    assert output["available"] is True
    assert output["contexts"]
    assert output["summary"] == "已检索到成都相关轻量城市知识。"


def test_light_rag_service_returns_unavailable_for_no_match():
    output = get_rag_context(
        destination=None,
        interests=[],
        user_message="我想去不存在的星球散步",
    )

    assert output["available"] is False
    assert output["contexts"] == []
