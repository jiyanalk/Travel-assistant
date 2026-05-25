from services.retrieval_service import (
    load_city_documents,
    retrieve_city_context,
    split_markdown_sections,
)


def test_load_city_documents_and_split_sections():
    documents = load_city_documents()

    assert "成都" in documents
    sections = split_markdown_sections(documents["成都"])
    assert any(section["title"] == "兴趣关键词" for section in sections)


def test_retrieve_chengdu_food_context():
    contexts = retrieve_city_context(
        destination="成都",
        interests=["美食"],
        user_message="我想去成都玩三天，喜欢美食",
    )

    assert contexts
    assert contexts[0]["city"] == "成都"
    assert any("美食" in context["content"] for context in contexts)


def test_retrieve_by_alias_when_destination_missing():
    contexts = retrieve_city_context(
        destination=None,
        interests=["美食"],
        user_message="我想去蓉城玩三天",
    )

    assert contexts
    assert contexts[0]["city"] == "成都"


def test_retrieve_unknown_city_returns_empty():
    contexts = retrieve_city_context(
        destination=None,
        interests=[],
        user_message="我想去不存在的星球散步",
    )

    assert contexts == []
