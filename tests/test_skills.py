import asyncio

from schemas.agent_context import AgentContext
from schemas.light_trip import LightTripPlan, LightTripRequest
from services import memory_service
from skills import BudgetSkill, PlanRevisionSkill, PreferenceMemorySkill, RagContextSkill


def test_budget_skill_runs_when_budget_fields_complete():
    context = AgentContext(
        session_id="budget-skill",
        user_id=None,
        user_message="成都三天两人预算3000",
        latest_request=LightTripRequest(destination="成都", days=3, people=2, budget=3000),
    )
    skill = BudgetSkill()

    assert asyncio.run(skill.can_handle(context)) is True
    result = asyncio.run(skill.run(context))

    assert result.success is True
    assert result.data["budget"]["available"] is True
    assert "舒适型" in result.data["budget_summary"]


def test_budget_skill_does_not_run_when_fields_missing():
    context = AgentContext(
        session_id="budget-skill-missing",
        user_id=None,
        user_message="成都三天",
        latest_request=LightTripRequest(destination="成都", days=3),
    )

    assert asyncio.run(BudgetSkill().can_handle(context)) is False


def test_rag_context_skill_returns_context():
    context = AgentContext(
        session_id="rag-skill",
        user_id=None,
        user_message="我想去蓉城玩三天，喜欢美食",
        latest_request=LightTripRequest(destination="蓉城", interests=["美食"]),
    )
    skill = RagContextSkill()

    assert asyncio.run(skill.can_handle(context)) is True
    result = asyncio.run(skill.run(context))

    assert result.success is True
    assert result.data["rag_context"]["available"] is True
    assert result.data["rag_context"]["contexts"][0]["city"] == "成都"


def test_preference_memory_skill_only_runs_for_explicit_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_service, "MEMORY_PATH", tmp_path / "user_memory.json")
    memory_service.IN_MEMORY_PROFILES.clear()
    skill = PreferenceMemorySkill()
    remember_context = AgentContext(
        session_id="memory-skill",
        user_id="skill-user",
        user_message="记住我以后喜欢美食和夜景，不喜欢太赶",
    )
    one_off_context = AgentContext(
        session_id="memory-skill-one-off",
        user_id="skill-user",
        user_message="我这次去成都玩三天，两个人预算3000",
    )

    assert asyncio.run(skill.can_handle(one_off_context)) is False
    assert asyncio.run(skill.can_handle(remember_context)) is True
    result = asyncio.run(skill.run(remember_context))
    profile = memory_service.get_user_preferences("skill-user")

    assert result.data["memory_update"]["updated"] is True
    assert profile["interests"] == ["美食", "夜景"]
    assert profile["disliked_tags"] == ["太赶"]
    assert "destination" not in profile


def test_plan_revision_skill_detects_relaxed_revision():
    context = AgentContext(
        session_id="revision-skill",
        user_id=None,
        user_message="把计划改轻松一点，不要太赶",
        latest_plan=LightTripPlan(
            destination="成都",
            days=3,
            summary="成都计划",
            daily_plan=["Day 1", "Day 2", "Day 3"],
        ),
    )
    skill = PlanRevisionSkill()

    assert asyncio.run(skill.can_handle(context)) is True
    result = asyncio.run(skill.run(context))

    assert result.success is True
    assert any("降低每日点位密度" in hint for hint in result.data["revision_hints"])
