import asyncio

from schemas.agent_context import AgentContext
from schemas.light_trip import LightTripRequest
from services.skill_registry import SkillRegistry, create_default_skill_registry
from skills.base import BaseSkill, SkillResult


def test_skill_registry_can_register_and_list_skill():
    registry = SkillRegistry()
    skill = _AlwaysSkill()

    registry.register(skill)

    assert registry.list_skills() == [skill]


def test_skill_registry_selects_rag_and_budget_skills():
    registry = create_default_skill_registry()
    context = AgentContext(
        session_id="skill-select",
        user_id=None,
        user_message="我想去成都玩三天，喜欢美食",
        latest_request=LightTripRequest(destination="成都", days=3, people=2, budget=3000),
    )

    selected = asyncio.run(registry.select_skills(context))
    names = [skill.name for skill in selected]

    assert "rag_context_skill" in names
    assert "budget_skill" in names


def test_skill_registry_catches_skill_errors():
    registry = SkillRegistry()
    registry.register(_FailingSkill())
    context = AgentContext(
        session_id="skill-error",
        user_id=None,
        user_message="hello",
    )

    outputs = asyncio.run(registry.run_skills(context))

    assert outputs["failing_skill"]["success"] is False
    assert "boom" in outputs["failing_skill"]["message"]


class _AlwaysSkill(BaseSkill):
    name = "always_skill"
    intents = ["chat"]

    async def can_handle(self, context: AgentContext) -> bool:
        return True

    async def run(self, context: AgentContext) -> SkillResult:
        return SkillResult(name=self.name, data={"ok": True})


class _FailingSkill(BaseSkill):
    name = "failing_skill"
    intents = ["chat"]

    async def can_handle(self, context: AgentContext) -> bool:
        return True

    async def run(self, context: AgentContext) -> SkillResult:
        raise RuntimeError("boom")
