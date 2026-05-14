from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.config import ROOT_DIR
from schemas.api import TripPlanResponse
from schemas.trip_plan import TripPlan


SESSION_STORE_PATH = ROOT_DIR / "data" / "ws_sessions.json"


@dataclass
class SessionState:
    session_id: str
    user_id: str = "guest"
    thread_id: str | None = None
    trip_id: str | None = None
    awaiting_clarification: bool = False
    latest_trip_plan: TripPlan | None = None
    last_plan_response: TripPlanResponse | None = None
    message_history: list[dict[str, str]] = field(default_factory=list)


class WSSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = self._load_sessions()

    def get_or_create(self, session_id: str, user_id: str | None = None) -> SessionState:
        session = self._sessions.get(session_id)
        if session is None:
            session = SessionState(session_id=session_id, user_id=user_id or "guest")
            self._sessions[session_id] = session
            self._persist()
            return session

        if user_id:
            session.user_id = user_id
        return session

    def update_plan_response(self, session: SessionState, response: TripPlanResponse) -> None:
        session.thread_id = response.thread_id
        session.trip_id = response.trip_id
        session.awaiting_clarification = response.need_clarification
        session.last_plan_response = response
        if response.trip_plan is not None:
            session.latest_trip_plan = response.trip_plan
        self._persist()

    def append_user_message(self, session: SessionState, message: str) -> None:
        session.message_history.append({"role": "user", "content": message})
        self._persist()

    def append_assistant_message(self, session: SessionState, message: str) -> None:
        session.message_history.append({"role": "assistant", "content": message})
        self._persist()

    def update_revised_plan(
        self,
        session: SessionState,
        updated_plan: TripPlan,
    ) -> None:
        session.latest_trip_plan = updated_plan
        session.awaiting_clarification = False
        if session.last_plan_response is not None:
            session.last_plan_response.trip_plan = updated_plan
        self._persist()

    def to_snapshot(self, session: SessionState) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "thread_id": session.thread_id,
            "trip_id": session.trip_id,
            "user_id": session.user_id,
            "awaiting_clarification": session.awaiting_clarification,
            "latest_trip_plan": session.latest_trip_plan.model_dump(mode="json")
            if session.latest_trip_plan
            else None,
            "last_plan_response": session.last_plan_response.model_dump(mode="json")
            if session.last_plan_response
            else None,
            "message_history": session.message_history,
        }

    def _load_sessions(self) -> dict[str, SessionState]:
        if not SESSION_STORE_PATH.exists():
            return {}
        try:
            raw = json.loads(SESSION_STORE_PATH.read_text(encoding="utf-8"))
        except (PermissionError, OSError, json.JSONDecodeError):
            return {}

        sessions: dict[str, SessionState] = {}
        for session_id, payload in raw.items():
            last_plan_response = (
                TripPlanResponse.model_validate(payload["last_plan_response"])
                if payload.get("last_plan_response")
                else None
            )
            latest_trip_plan = (
                TripPlan.model_validate(payload["latest_trip_plan"])
                if payload.get("latest_trip_plan")
                else None
            )
            sessions[session_id] = SessionState(
                session_id=session_id,
                user_id=payload.get("user_id", "guest"),
                thread_id=payload.get("thread_id"),
                trip_id=payload.get("trip_id"),
                awaiting_clarification=payload.get("awaiting_clarification", False),
                latest_trip_plan=latest_trip_plan,
                last_plan_response=last_plan_response,
                message_history=payload.get("message_history", []),
            )
        return sessions

    def _persist(self) -> None:
        SESSION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            session_id: {
                "user_id": session.user_id,
                "thread_id": session.thread_id,
                "trip_id": session.trip_id,
                "awaiting_clarification": session.awaiting_clarification,
                "latest_trip_plan": session.latest_trip_plan.model_dump(mode="json")
                if session.latest_trip_plan
                else None,
                "last_plan_response": session.last_plan_response.model_dump(mode="json")
                if session.last_plan_response
                else None,
                "message_history": session.message_history,
            }
            for session_id, session in self._sessions.items()
        }
        try:
            SESSION_STORE_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except PermissionError:
            pass


ws_session_manager = WSSessionManager()
