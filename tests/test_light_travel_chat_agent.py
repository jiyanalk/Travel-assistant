import asyncio

from agents import light_travel_chat_agent as agent_module
from agents.light_travel_chat_agent import FALLBACK_MESSAGE, LightTravelChatAgent
from schemas.light_trip import ChatAgentResult, LightTripPlan, LightTripRequest
from services import ws_session_manager as ws_module
from services.ws_session_manager import WSSessionManager


def test_light_travel_chat_agent_updates_session_and_uses_budget_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(ws_module, "SESSION_STORE_PATH", tmp_path / "ws_sessions.json")
    manager = WSSessionManager()
    monkeypatch.setattr(agent_module, "ws_session_manager", manager)
    calls = {"count": 0}

    def fake_chat_completion(**kwargs):
        calls["count"] += 1
        assert kwargs["json_mode"] is True
        return ChatAgentResult(
            intent="draft_plan",
            assistant_message="Here is a light draft.",
            updated_request=LightTripRequest(
                destination="Beijing",
                days=3,
                people=2,
                budget=3600,
                interests=["history"],
            ),
            updated_plan=LightTripPlan(
                destination="Beijing",
                days=3,
                summary="A light Beijing draft.",
                daily_plan=["Day 1: arrival", "Day 2: history", "Day 3: food"],
            ),
        ).model_dump_json()

    monkeypatch.setattr(agent_module.llm_service, "chat_completion", fake_chat_completion)

    result = asyncio.run(
        LightTravelChatAgent().chat(
            session_id="light-agent-success",
            user_id="tester",
            user_message="Plan Beijing for 3 days.",
        )
    )

    state = manager.get_light_state("light-agent-success")
    assert calls["count"] == 1
    assert result.intent == "draft_plan"
    assert result.updated_plan is not None
    assert result.updated_plan.budget_summary is not None
    assert "3600" in result.updated_plan.budget_summary
    assert result.used_tools == ["simple_budget_tool"]
    assert state["light_latest_request"]["destination"] == "Beijing"
    assert state["light_latest_plan"]["budget_summary"] == result.updated_plan.budget_summary
    assert [message["role"] for message in state["light_message_history"]] == ["user", "assistant"]


def test_light_travel_chat_agent_returns_fallback_for_invalid_json(monkeypatch, tmp_path):
    monkeypatch.setattr(ws_module, "SESSION_STORE_PATH", tmp_path / "ws_sessions.json")
    manager = WSSessionManager()
    monkeypatch.setattr(agent_module, "ws_session_manager", manager)
    calls = {"count": 0}

    def fake_chat_completion(**kwargs):
        calls["count"] += 1
        return "not json"

    monkeypatch.setattr(agent_module.llm_service, "chat_completion", fake_chat_completion)

    result = asyncio.run(
        LightTravelChatAgent().chat(
            session_id="light-agent-invalid-json",
            user_id=None,
            user_message="I want a trip.",
        )
    )

    state = manager.get_light_state("light-agent-invalid-json")
    assert calls["count"] == 1
    assert result.intent == "chat"
    assert result.assistant_message == FALLBACK_MESSAGE
    assert result.updated_plan is None
    assert state["light_latest_request"] is None
    assert state["light_latest_plan"] is None
    assert [message["role"] for message in state["light_message_history"]] == ["user", "assistant"]
