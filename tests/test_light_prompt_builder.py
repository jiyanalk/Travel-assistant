from schemas.light_trip import LightTripPlan, LightTripRequest
from services.light_prompt_builder import build_light_travel_prompt


def test_light_prompt_builder_contains_key_constraints():
    messages = build_light_travel_prompt(
        user_message="我想去北京玩，但还没想好几天。",
        message_history=[{"role": "assistant", "content": "你想去哪里玩？"}],
        latest_request=LightTripRequest(destination="北京", interests=["历史"]),
        latest_plan=LightTripPlan(
            destination="北京",
            days=None,
            summary="北京轻量行程草案",
            daily_plan=["先确认天数后再细化。"],
        ),
        preference_memory={"travel_style": "轻松"},
    )

    assert isinstance(messages, list)
    assert [message["role"] for message in messages] == ["system", "user"]

    combined_prompt = "\n".join(message["content"] for message in messages)
    assert "轻量旅游对话助手" in combined_prompt
    assert "不要生成复杂完整旅行计划" in combined_prompt
    assert "不要求用户一次性提供所有字段" in combined_prompt
    assert "destination 缺失时" in combined_prompt
    assert "只输出合法 JSON" in combined_prompt
    assert "JSON 必须符合 ChatAgentResult" in combined_prompt
    assert "不编造具体酒店价格" in combined_prompt
    assert "不编造营业时间" in combined_prompt
    assert "不编造门票价格" in combined_prompt
    assert "不编造实时交通信息" in combined_prompt
    assert "我想去北京玩" in combined_prompt
    assert "latest_request" in combined_prompt
    assert "latest_plan" in combined_prompt
    assert "preference_memory" in combined_prompt
