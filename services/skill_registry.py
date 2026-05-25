from __future__ import annotations

from typing import Any

from schemas.agent_context import AgentContext
from skills import (
    BaseSkill,
    BudgetSkill,
    PlanRevisionSkill,
    PreferenceMemorySkill,
    RagContextSkill,
    SkillResult,
)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill

    def list_skills(self) -> list[BaseSkill]:
        return list(self._skills.values())

    async def select_skills(self, context: AgentContext) -> list[BaseSkill]:
        candidates = self.list_skills()
        intent = _context_intent(context)
        if intent:
            candidates.sort(key=lambda skill: intent not in skill.intents)

        selected: list[BaseSkill] = []
        for skill in candidates:
            try:
                if await skill.can_handle(context):
                    selected.append(skill)
            except Exception:
                continue
        return selected

    async def run_skills(
        self,
        context: AgentContext,
        skills: list[BaseSkill] | None = None,
    ) -> dict[str, Any]:
        selected = skills if skills is not None else await self.select_skills(context)
        outputs: dict[str, Any] = {}
        for skill in selected:
            try:
                result = await skill.run(context)
            except Exception as exc:
                result = SkillResult(
                    name=skill.name,
                    success=False,
                    data={"error": str(exc)},
                    message=str(exc),
                )
            outputs[skill.name] = result.model_dump(mode="json")
        return outputs


def create_default_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(RagContextSkill())
    registry.register(BudgetSkill())
    registry.register(PreferenceMemorySkill())
    registry.register(PlanRevisionSkill())
    return registry


def _context_intent(context: AgentContext) -> str | None:
    intent = context.tool_context.get("intent")
    return str(intent) if intent else None


default_skill_registry = create_default_skill_registry()
