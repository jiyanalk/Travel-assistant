from services import memory_service


def test_update_user_preferences_merges_lists_and_filters_trip_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_service, "MEMORY_PATH", tmp_path / "user_memory.json")
    memory_service.IN_MEMORY_PROFILES.clear()

    first = memory_service.update_user_preferences(
        "user-1",
        {
            "interests": ["美食"],
            "destination": "成都",
            "budget": 3000,
            "people": 2,
            "days": 3,
        },
    )
    second = memory_service.update_user_preferences(
        "user-1",
        {
            "interests": ["夜景", "美食"],
            "disliked_tags": ["太赶"],
            "pace_preference": "relaxed",
        },
    )

    assert first["interests"] == ["美食"]
    assert second["interests"] == ["美食", "夜景"]
    assert second["disliked_tags"] == ["太赶"]
    assert second["pace_preference"] == "relaxed"
    assert "destination" not in second
    assert "budget" not in second
    assert "people" not in second
    assert "days" not in second


def test_update_user_preferences_skips_empty_user_id(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_service, "MEMORY_PATH", tmp_path / "user_memory.json")
    memory_service.IN_MEMORY_PROFILES.clear()

    assert memory_service.update_user_preferences("", {"interests": ["美食"]}) == {}
    assert not (tmp_path / "user_memory.json").exists()
