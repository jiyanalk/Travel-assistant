from __future__ import annotations

import asyncio
from typing import Optional

from pydantic import ValidationError

from schemas.light_trip import ChatAgentResult, LightTripPlan, LightTripRequest
from services import llm_service
from services.light_prompt_builder import build_light_travel_prompt
from services.simple_budget_service import estimate_simple_budget
from services.ws_session_manager import ws_session_manager


FALLBACK_MESSAGE = "我刚刚理解得不够稳定，可以请你换个方式描述一下你的旅行需求吗？"


class LightTravelChatAgent:
    async def chat(
        self,
        session_id: str,
        user_id: Optional[str],
        user_message: str,
    ) -> ChatAgentResult:
        session = ws_session_manager.get_or_create(session_id, user_id=user_id)
        message_history = ws_session_manager.get_light_message_history(session_id, limit=10)
        messages = build_light_travel_prompt(
            user_message=user_message,
            message_history=message_history,
            latest_request=session.light_latest_request,
            latest_plan=session.light_latest_plan,
            preference_memory=session.light_preference_memory,
        )

        result = await self._call_model(messages)
        result = self._postprocess_budget(result)

        ws_session_manager.append_light_message(session_id, "user", user_message)
        ws_session_manager.append_light_message(session_id, "assistant", result.assistant_message)
        if result.updated_request is not None:
            ws_session_manager.update_light_request(session_id, result.updated_request)
        if result.updated_plan is not None:
            ws_session_manager.update_light_plan(session_id, result.updated_plan)

        return result

    async def _call_model(self, messages: list[dict[str, str]]) -> ChatAgentResult:
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]
        try:
            raw_content = await asyncio.to_thread(
                llm_service.chat_completion,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                json_mode=True,
                trace_step="light_travel_chat",
                trace_label="chat_agent_result",
            )
            return ChatAgentResult.model_validate_json(raw_content)
        except (ValidationError, ValueError, TypeError, llm_service.LLMServiceError):
            return ChatAgentResult(
                intent="chat",
                assistant_message=FALLBACK_MESSAGE,
            )

    def _postprocess_budget(self, result: ChatAgentResult) -> ChatAgentResult:
        request = result.updated_request
        if request is None or request.days is None or request.people is None or request.budget is None:
            return result

        budget_result = estimate_simple_budget(
            days=request.days,
            people=request.people,
            budget=request.budget,
        )
        if not budget_result.get("available"):
            return result

        if result.updated_plan is not None:
            result.updated_plan.budget_summary = budget_result["summary"]
        if "simple_budget_tool" not in result.used_tools:
            result.used_tools.append("simple_budget_tool")
        return result
