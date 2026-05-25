from __future__ import annotations

from typing import Optional

from agents.light_agent_harness import FALLBACK_MESSAGE, AgentHarness
from schemas.agent_context import AgentContext
from schemas.light_trip import ChatAgentResult
from services.memory_service import get_user_preferences
from services.ws_session_manager import ws_session_manager


class LightTravelChatAgent:
    async def chat(
        self,
        session_id: str,
        user_id: Optional[str],
        user_message: str,
    ) -> ChatAgentResult:
        session = ws_session_manager.get_or_create(session_id, user_id=user_id)
        message_history = ws_session_manager.get_light_message_history(session_id, limit=10)
        effective_user_id = user_id or session.user_id
        preference_memory = (
            get_user_preferences(effective_user_id)
            if effective_user_id and effective_user_id != "guest"
            else session.light_preference_memory
        )

        context = AgentContext(
            session_id=session_id,
            user_id=effective_user_id,
            user_message=user_message,
            message_history=message_history,
            latest_request=session.light_latest_request,
            latest_plan=session.light_latest_plan,
            preference_memory=preference_memory,
        )
        result = await AgentHarness().run(context)

        ws_session_manager.append_light_message(session_id, "user", user_message)
        ws_session_manager.append_light_message(session_id, "assistant", result.assistant_message)
        if result.updated_request is not None:
            ws_session_manager.update_light_request(session_id, result.updated_request)
        if result.updated_plan is not None:
            ws_session_manager.update_light_plan(session_id, result.updated_plan)

        return result
