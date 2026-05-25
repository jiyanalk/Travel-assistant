import asyncio

from schemas.agent_context import AgentContext
from schemas.light_trip import LightTripPlan, LightTripRequest
from services.tool_registry import create_default_tool_registry


def test_tool_registry_selects_and_runs_tools():
    registry = create_default_tool_registry()
    context = AgentContext(
        session_id="tool-session",
        user_id=None,
        user_message="我想去蓉城玩三天，喜欢美食",
        latest_request=LightTripRequest(destination="蓉城", days=3, people=2, budget=3000),
        latest_plan=LightTripPlan(
            destination="成都",
            days=3,
            summary="成都轻量计划",
            daily_plan=["Day 1", "Day 2", "Day 3"],
        ),
    )

    selected = registry.select_tools(context)
    outputs = asyncio.run(registry.run_tools(selected, context))

    assert "rag_context_tool" in selected
    assert "city_alias_tool" in selected
    assert "simple_budget_tool" in selected
    assert "trip_quality_check_tool" in selected
    assert outputs["rag_context_tool"]["available"] is True
    assert outputs["rag_context_tool"]["contexts"][0]["city"] == "成都"
    assert outputs["city_alias_tool"]["destination"] == "成都"
    assert outputs["simple_budget_tool"]["available"] is True
    assert outputs["simple_budget_tool"]["level"] == "舒适型"
    assert outputs["trip_quality_check_tool"]["available"] is True
    assert "daily_plan_matches_days" in outputs["trip_quality_check_tool"]["checks"]


def test_rag_context_tool_can_be_called_directly():
    registry = create_default_tool_registry()
    context = AgentContext(
        session_id="rag-tool-session",
        user_id=None,
        user_message="我想去成都玩三天，喜欢美食和city walk",
        latest_request=LightTripRequest(destination="成都", interests=["美食", "city walk"]),
    )

    output = asyncio.run(registry.run_tool("rag_context_tool", context))

    assert output["available"] is True
    assert output["contexts"]
    assert output["contexts"][0]["city"] == "成都"


def test_trip_request_merge_tool_merges_multiturn_fields_and_dedupes_lists():
    registry = create_default_tool_registry()
    context = AgentContext(
        session_id="merge-session",
        user_id=None,
        user_message="两个人，预算3000，也喜欢city walk",
        latest_request=LightTripRequest(
            destination="成都",
            days=3,
            people=4,
            interests=["美食"],
        ),
        tool_context={
            "updated_request": LightTripRequest(
                people=2,
                budget=3000,
                interests=["city walk", "美食"],
            ).model_dump(mode="json")
        },
    )

    output = asyncio.run(registry.run_tool("trip_request_merge_tool", context))
    merged = output["merged_request"]

    assert merged["destination"] == "成都"
    assert merged["days"] == 3
    assert merged["people"] == 2
    assert merged["budget"] == 3000
    assert merged["interests"] == ["美食", "city walk"]


def test_trip_request_merge_tool_does_not_let_default_people_override_existing_value():
    registry = create_default_tool_registry()
    context = AgentContext(
        session_id="merge-people-session",
        user_id=None,
        user_message="预算3000",
        latest_request=LightTripRequest(destination="成都", days=3, people=2),
        tool_context={
            "updated_request": LightTripRequest(budget=3000).model_dump(mode="json")
        },
    )

    output = asyncio.run(registry.run_tool("trip_request_merge_tool", context))

    assert output["merged_request"]["people"] == 2
    assert output["merged_request"]["budget"] == 3000


def test_city_alias_tool_normalizes_known_aliases_and_leaves_unknown():
    registry = create_default_tool_registry()
    rongcheng = AgentContext(
        session_id="alias-1",
        user_id=None,
        user_message="我想去蓉城",
        latest_request=LightTripRequest(destination="蓉城"),
    )
    modou = AgentContext(
        session_id="alias-2",
        user_id=None,
        user_message="去魔都",
        latest_request=LightTripRequest(destination="魔都"),
    )
    unknown = AgentContext(
        session_id="alias-3",
        user_id=None,
        user_message="去未知城",
        latest_request=LightTripRequest(destination="未知城"),
    )

    assert asyncio.run(registry.run_tool("city_alias_tool", rongcheng))["destination"] == "成都"
    assert asyncio.run(registry.run_tool("city_alias_tool", modou))["destination"] == "上海"
    assert asyncio.run(registry.run_tool("city_alias_tool", unknown))["replaced"] is False


def test_preference_extractor_tool_only_triggers_on_explicit_memory_intent():
    registry = create_default_tool_registry()
    remember = AgentContext(
        session_id="pref-1",
        user_id="u1",
        user_message="记住我喜欢美食和夜景",
    )
    one_off = AgentContext(
        session_id="pref-2",
        user_id="u1",
        user_message="我这次去成都玩三天，两个人预算3000",
    )
    relaxed = AgentContext(
        session_id="pref-3",
        user_id="u1",
        user_message="下次也不要安排太赶",
    )

    remember_output = asyncio.run(registry.run_tool("preference_extractor_tool", remember))
    one_off_output = asyncio.run(registry.run_tool("preference_extractor_tool", one_off))
    relaxed_output = asyncio.run(registry.run_tool("preference_extractor_tool", relaxed))

    assert remember_output["should_update"] is True
    assert remember_output["preferences"]["interests"] == ["美食", "夜景"]
    assert one_off_output["should_update"] is False
    assert relaxed_output["preferences"]["disliked_tags"] == ["太赶"]
    assert relaxed_output["preferences"]["pace_preference"] == "relaxed"
