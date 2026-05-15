from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.config import ROOT_DIR
from schemas.light_trip import LightTripPlan, LightTripRequest


SESSION_STORE_PATH = ROOT_DIR / "data" / "ws_sessions.json"


@dataclass
class SessionState:
    session_id: str
    user_id: str = "guest"
    light_latest_request: LightTripRequest | None = None
    light_latest_plan: LightTripPlan | None = None
    light_message_history: list[dict[str, str]] = field(default_factory=list)
    light_preference_memory: dict[str, Any] = field(default_factory=dict)


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
            self._persist()
        return session

    def get_light_state(self, session_id: str) -> dict[str, Any]:
        session = self.get_or_create(session_id)
        return {
            "session_id": session.session_id,
            "light_latest_request": session.light_latest_request.model_dump(mode="json")
            if session.light_latest_request
            else None,
            "light_latest_plan": session.light_latest_plan.model_dump(mode="json")
            if session.light_latest_plan
            else None,
            "light_message_history": list(session.light_message_history),
            "light_preference_memory": dict(session.light_preference_memory),
        }

    def update_light_request(
        self,
        session_id: str,
        request: LightTripRequest | dict[str, Any] | None,
    ) -> None:
        session = self.get_or_create(session_id)
        session.light_latest_request = (
            LightTripRequest.model_validate(request)
            if request is not None
            else None
        )
        self._persist()

    def update_light_plan(
        self,
        session_id: str,
        plan: LightTripPlan | dict[str, Any] | None,
    ) -> None:
        session = self.get_or_create(session_id)
        session.light_latest_plan = (
            LightTripPlan.model_validate(plan)
            if plan is not None
            else None
        )
        self._persist()

    def append_light_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get_or_create(session_id)
        session.light_message_history.append({"role": role, "content": content})
        self._persist()

    def get_light_message_history(self, session_id: str, limit: int = 10) -> list[dict[str, str]]:
        session = self.get_or_create(session_id)
        if limit <= 0:
            return []
        return session.light_message_history[-limit:]

    def to_snapshot(self, session: SessionState) -> dict[str, Any]:
        latest_request = (
            session.light_latest_request.model_dump(mode="json")
            if session.light_latest_request
            else None
        )
        latest_plan = (
            session.light_latest_plan.model_dump(mode="json")
            if session.light_latest_plan
            else None
        )
        message_history = list(session.light_message_history)
        preference_memory = dict(session.light_preference_memory)

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "latest_request": latest_request,
            "latest_plan": latest_plan,
            "message_history": message_history,
            "preference_memory": preference_memory,
            # Temporary aliases for already-open frontend tabs during this transition.
            "light_latest_request": latest_request,
            "light_latest_plan": latest_plan,
            "light_message_history": message_history,
            "light_preference_memory": preference_memory,
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
            latest_request_payload = payload.get("light_latest_request") or payload.get("latest_request")
            latest_plan_payload = payload.get("light_latest_plan") or payload.get("latest_plan")
            sessions[session_id] = SessionState(
                session_id=session_id,
                user_id=payload.get("user_id", "guest"),
                light_latest_request=(
                    LightTripRequest.model_validate(latest_request_payload)
                    if latest_request_payload
                    else None
                ),
                light_latest_plan=(
                    LightTripPlan.model_validate(latest_plan_payload)
                    if latest_plan_payload
                    else None
                ),
                light_message_history=payload.get("light_message_history")
                or payload.get("message_history", []),
                light_preference_memory=payload.get("light_preference_memory")
                or payload.get("preference_memory", {}),
            )
        return sessions

    def _persist(self) -> None:
        SESSION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            session_id: self.to_snapshot(session)
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
