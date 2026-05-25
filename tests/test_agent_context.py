from schemas.agent_context import AgentContext
from schemas.light_trip import LightTripPlan, LightTripRequest


def test_agent_context_can_be_instantiated():
    context = AgentContext(
        session_id="session-1",
        user_id="user-1",
        user_message="帮我规划成都三天",
        message_history=[{"role": "user", "content": "喜欢美食"}],
        latest_request=LightTripRequest(destination="成都", days=3),
        latest_plan=LightTripPlan(
            destination="成都",
            days=3,
            summary="成都轻量计划",
            daily_plan=["Day 1", "Day 2", "Day 3"],
        ),
        preference_memory={"interests": ["美食"]},
    )

    assert context.session_id == "session-1"
    assert context.latest_request is not None
    assert context.latest_plan is not None
    assert context.tool_context == {}
    assert context.selected_tools == []
