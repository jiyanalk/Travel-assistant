from __future__ import annotations

from schemas.agent_context import AgentContext
from schemas.light_trip import LightTripRequest
from services.city_alias_service import detect_aliases_in_text
from services.light_rag_service import get_rag_context
from services.retrieval_service import CITY_FILE_MAP
from skills.base import BaseSkill, SkillResult


class RagContextSkill(BaseSkill):
    name = "rag_context_skill"
    intents = ["collect_info", "draft_plan", "revise_plan"]

    async def can_handle(self, context: AgentContext) -> bool:
        request = _request_from_context(context)
        if request and request.destination:
            return True
        message = context.user_message or ""
        if detect_aliases_in_text(message).get("replaced"):
            return True
        if any(city in message for city in CITY_FILE_MAP):
            return True
        return any(term in message for term in ["旅行", "旅游", "行程", "玩", "路线", "攻略", "city walk"])

    async def run(self, context: AgentContext) -> SkillResult:
        request = _request_from_context(context)
        output = get_rag_context(
            destination=request.destination if request else None,
            interests=request.interests if request else [],
            user_message=context.user_message,
        )
        return SkillResult(
            name=self.name,
            success=bool(output.get("available")),
            data={"rag_context": output},
            message=output.get("summary"),
        )


def _request_from_context(context: AgentContext) -> LightTripRequest | None:
    candidate = context.tool_context.get("updated_request") or context.latest_request
    if candidate is None:
        return None
    if isinstance(candidate, LightTripRequest):
        return candidate
    return LightTripRequest.model_validate(candidate)
