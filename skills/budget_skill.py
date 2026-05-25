from __future__ import annotations

from schemas.agent_context import AgentContext
from schemas.light_trip import LightTripRequest
from services.simple_budget_service import estimate_simple_budget
from skills.base import BaseSkill, SkillResult


class BudgetSkill(BaseSkill):
    name = "budget_skill"
    intents = ["draft_plan", "budget_estimate", "revise_plan", "collect_info"]

    async def can_handle(self, context: AgentContext) -> bool:
        request = _request_from_context(context)
        return (
            request is not None
            and request.days is not None
            and request.people is not None
            and request.budget is not None
        )

    async def run(self, context: AgentContext) -> SkillResult:
        request = _request_from_context(context)
        if request is None:
            output = estimate_simple_budget(days=None, people=None, budget=None)
        else:
            output = estimate_simple_budget(
                days=request.days,
                people=request.people,
                budget=request.budget,
            )
        return SkillResult(
            name=self.name,
            success=bool(output.get("available")),
            data={
                "budget": output,
                "budget_summary": output.get("summary"),
            },
        )


def _request_from_context(context: AgentContext) -> LightTripRequest | None:
    candidate = context.tool_context.get("updated_request") or context.latest_request
    if candidate is None:
        return None
    if isinstance(candidate, LightTripRequest):
        return candidate
    return LightTripRequest.model_validate(candidate)
