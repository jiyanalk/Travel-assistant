from schemas.light_trip import LightTripPlan, LightTripRequest
from services import ws_session_manager as ws_module
from services.ws_session_manager import WSSessionManager


def test_light_session_state_can_save_and_load_request_plan_and_history(monkeypatch, tmp_path):
    monkeypatch.setattr(ws_module, "SESSION_STORE_PATH", tmp_path / "ws_sessions.json")
    manager = WSSessionManager()
    session_id = "light-session-1"

    request = LightTripRequest(
        origin="Zhongshan",
        destination="Beijing",
        days=3,
        people=2,
        budget=3600,
        interests=["food", "history"],
        travel_style="relaxed",
        constraints=["not too rushed"],
    )
    plan = LightTripPlan(
        destination="Beijing",
        days=3,
        summary="A lightweight Beijing draft plan.",
        daily_plan=["Day 1: arrival", "Day 2: history walk", "Day 3: food and return"],
        budget_summary="Comfort level based on rough budget.",
        tips=["Check official opening hours before departure"],
    )

    manager.update_light_request(session_id, request)
    manager.update_light_plan(session_id, plan)
    manager.append_light_message(session_id, "user", "Plan Beijing for me.")
    manager.append_light_message(session_id, "assistant", "Here is a light draft.")

    state = manager.get_light_state(session_id)
    assert state["light_latest_request"]["destination"] == "Beijing"
    assert state["light_latest_plan"]["summary"] == "A lightweight Beijing draft plan."
    assert len(state["light_message_history"]) == 2
    assert state["light_preference_memory"] == {}
    assert manager.get_light_message_history(session_id, limit=1) == [
        {"role": "assistant", "content": "Here is a light draft."}
    ]

    reloaded = WSSessionManager()
    reloaded_state = reloaded.get_light_state(session_id)
    assert reloaded_state["light_latest_request"]["days"] == 3
    assert reloaded_state["light_latest_plan"]["daily_plan"][1] == "Day 2: history walk"
    assert len(reloaded.get_light_message_history(session_id)) == 2
