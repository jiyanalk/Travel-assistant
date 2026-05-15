from fastapi.testclient import TestClient

from api.routes import trip_ws
from app.main import app
from schemas.light_trip import ChatAgentResult, LightTripPlan, LightTripRequest
from services import ws_session_manager as ws_module
from services.ws_session_manager import WSSessionManager


def test_trip_ws_always_uses_light_agent_for_user_message(monkeypatch, tmp_path):
    monkeypatch.setattr(ws_module, "SESSION_STORE_PATH", tmp_path / "ws_sessions.json")
    manager = WSSessionManager()
    monkeypatch.setattr(trip_ws, "ws_session_manager", manager)
    calls = {"light": 0}

    class FakeLightTravelChatAgent:
        async def chat(self, session_id, user_id, user_message):
            calls["light"] += 1
            return ChatAgentResult(
                intent="draft_plan",
                assistant_message="light agent response",
                updated_request=LightTripRequest(destination="Chengdu", days=3),
                updated_plan=LightTripPlan(
                    destination="Chengdu",
                    days=3,
                    summary="Light plan",
                    daily_plan=["Day 1", "Day 2", "Day 3"],
                ),
                used_tools=["simple_budget_tool"],
            )

    monkeypatch.setattr(trip_ws, "LightTravelChatAgent", FakeLightTravelChatAgent)

    client = TestClient(app)
    with client.websocket_connect("/ws/trips/light-only-user-message") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json({"type": "user_message", "message": "plan chengdu"})
        response = websocket.receive_json()

    assert calls["light"] == 1
    assert response["type"] == "assistant_message"
    assert response["message"] == "light agent response"
    assert response["request"]["destination"] == "Chengdu"
    assert response["plan"]["summary"] == "Light plan"
    assert response["metadata"] == {
        "intent": "draft_plan",
        "used_tools": ["simple_budget_tool"],
    }


def test_trip_ws_treats_revise_plan_as_light_agent_message(monkeypatch, tmp_path):
    monkeypatch.setattr(ws_module, "SESSION_STORE_PATH", tmp_path / "ws_sessions.json")
    manager = WSSessionManager()
    monkeypatch.setattr(trip_ws, "ws_session_manager", manager)
    calls = {"light": 0}

    class FakeLightTravelChatAgent:
        async def chat(self, session_id, user_id, user_message):
            calls["light"] += 1
            assert user_message == "make it relaxed"
            return ChatAgentResult(
                intent="revise_plan",
                assistant_message="revised by light agent",
                updated_request=None,
                updated_plan=None,
            )

    monkeypatch.setattr(trip_ws, "LightTravelChatAgent", FakeLightTravelChatAgent)

    client = TestClient(app)
    with client.websocket_connect("/ws/trips/light-only-revise") as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json({"type": "revise_plan", "message": "make it relaxed"})
        response = websocket.receive_json()

    assert calls["light"] == 1
    assert response["type"] == "assistant_message"
    assert response["message"] == "revised by light agent"
    assert "request" in response
    assert "plan" in response
    assert response["metadata"]["intent"] == "revise_plan"
