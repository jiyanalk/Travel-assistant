import asyncio
import json

from agents import light_agent_harness as harness_module
from agents.light_agent_harness import FALLBACK_MESSAGE, AgentHarness
from schemas.agent_context import AgentContext
from schemas.light_trip import ChatAgentResult, LightTripPlan, LightTripRequest
from services import memory_service
from services.agent_observer import AgentObserver


def test_agent_harness_returns_valid_result_and_runs_skills(monkeypatch, tmp_path):
    trace_path = tmp_path / "agent_traces.jsonl"
    monkeypatch.setattr(
        harness_module,
        "agent_observer",
        AgentObserver(trace_path=trace_path),
    )
    calls = {"llm": 0, "user_prompt": ""}

    def fake_chat_completion(**kwargs):
        calls["llm"] += 1
        calls["user_prompt"] = kwargs["user_prompt"]
        assert kwargs["json_mode"] is True
        return ChatAgentResult(
            intent="draft_plan",
            assistant_message="成都三天轻量计划来了。",
            updated_request=LightTripRequest(
                destination="成都",
                days=3,
                people=2,
                budget=3000,
                interests=["美食"],
            ),
            updated_plan=LightTripPlan(
                destination="成都",
                days=3,
                summary="成都美食轻量计划",
                daily_plan=["Day 1", "Day 2", "Day 3"],
            ),
        ).model_dump_json()

    monkeypatch.setattr(harness_module.llm_service, "chat_completion", fake_chat_completion)

    result = asyncio.run(
        AgentHarness().run(
            AgentContext(
                session_id="harness-success",
                user_id="tester",
                user_message="我想去成都玩三天，两个人，预算3000，喜欢美食",
            )
        )
    )
    trace = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])

    assert calls["llm"] == 1
    assert "rag_context" in calls["user_prompt"]
    assert result.intent == "draft_plan"
    assert result.updated_plan is not None
    assert result.updated_plan.budget_summary is not None
    assert "rag_context_skill" in result.used_tools
    assert "budget_skill" in result.used_tools
    assert "trip_quality_check_tool" in result.used_tools
    assert "trip_request_merge_tool" in result.used_tools
    assert "rag_context_tool" not in result.used_tools
    assert "selected_skills" in trace
    assert "rag_context_skill" in trace["selected_skills"]
    assert "skill_outputs" in trace


def test_agent_harness_falls_back_for_invalid_model_output(monkeypatch, tmp_path):
    monkeypatch.setattr(
        harness_module,
        "agent_observer",
        AgentObserver(trace_path=tmp_path / "agent_traces.jsonl"),
    )

    def fake_chat_completion(**kwargs):
        return "not json"

    monkeypatch.setattr(harness_module.llm_service, "chat_completion", fake_chat_completion)

    context = AgentContext(
        session_id="harness-fallback",
        user_id=None,
        user_message="帮我旅行",
        latest_request=LightTripRequest(destination="杭州"),
        latest_plan=LightTripPlan(
            destination="杭州",
            days=2,
            summary="杭州轻量计划",
            daily_plan=["Day 1", "Day 2"],
        ),
    )
    result = asyncio.run(AgentHarness().run(context))

    assert result.intent == "chat"
    assert result.assistant_message == FALLBACK_MESSAGE
    assert result.updated_request == context.latest_request
    assert result.updated_plan == context.latest_plan
    assert result.used_tools == []


def test_agent_harness_skill_failure_does_not_break_result(monkeypatch, tmp_path):
    monkeypatch.setattr(
        harness_module,
        "agent_observer",
        AgentObserver(trace_path=tmp_path / "agent_traces.jsonl"),
    )

    harness = AgentHarness()
    original_run_skills = harness.skill_registry.run_skills

    async def fake_run_skills(context, skills=None):
        outputs = await original_run_skills(context, skills)
        if skills and any(skill.name == "rag_context_skill" for skill in skills):
            outputs["rag_context_skill"] = {
                "name": "rag_context_skill",
                "success": False,
                "data": {"error": "rag failed"},
                "message": "rag failed",
            }
        return outputs

    monkeypatch.setattr(harness.skill_registry, "run_skills", fake_run_skills)

    def fake_chat_completion(**kwargs):
        return ChatAgentResult(
            intent="chat",
            assistant_message="可以，我先给你一个轻量建议。",
            updated_request=LightTripRequest(destination="成都"),
            updated_plan=None,
        ).model_dump_json()

    monkeypatch.setattr(harness_module.llm_service, "chat_completion", fake_chat_completion)

    result = asyncio.run(
        harness.run(
            AgentContext(
                session_id="harness-rag-failure",
                user_id="tester",
                user_message="我想去成都玩",
            )
        )
    )

    assert result.intent == "chat"
    assert result.assistant_message == "可以，我先给你一个轻量建议。"


def test_agent_harness_merges_model_request_with_history(monkeypatch, tmp_path):
    monkeypatch.setattr(
        harness_module,
        "agent_observer",
        AgentObserver(trace_path=tmp_path / "agent_traces.jsonl"),
    )

    def fake_chat_completion(**kwargs):
        return ChatAgentResult(
            intent="collect_info",
            assistant_message="已补充人数。",
            updated_request=LightTripRequest(people=2),
            updated_plan=None,
        ).model_dump_json()

    monkeypatch.setattr(harness_module.llm_service, "chat_completion", fake_chat_completion)

    result = asyncio.run(
        AgentHarness().run(
            AgentContext(
                session_id="harness-merge",
                user_id="tester",
                user_message="两个人",
                latest_request=LightTripRequest(destination="成都", days=3, interests=["美食"]),
            )
        )
    )

    assert result.updated_request is not None
    assert result.updated_request.destination == "成都"
    assert result.updated_request.days == 3
    assert result.updated_request.people == 2
    assert result.updated_request.interests == ["美食"]
    assert "trip_request_merge_tool" in result.used_tools


def test_agent_harness_writes_memory_only_with_user_id(monkeypatch, tmp_path):
    monkeypatch.setattr(
        harness_module,
        "agent_observer",
        AgentObserver(trace_path=tmp_path / "agent_traces.jsonl"),
    )
    monkeypatch.setattr(memory_service, "MEMORY_PATH", tmp_path / "user_memory.json")
    memory_service.IN_MEMORY_PROFILES.clear()

    def fake_chat_completion(**kwargs):
        return ChatAgentResult(
            intent="chat",
            assistant_message="我会记住你的偏好。",
            updated_request=None,
            updated_plan=None,
        ).model_dump_json()

    monkeypatch.setattr(harness_module.llm_service, "chat_completion", fake_chat_completion)

    result = asyncio.run(
        AgentHarness().run(
            AgentContext(
                session_id="harness-memory",
                user_id="user-memory",
                user_message="记住我喜欢美食和夜景，不喜欢太赶",
            )
        )
    )
    profile = memory_service.get_user_preferences("user-memory")

    assert "preference_memory_skill" in result.used_tools
    assert profile["interests"] == ["美食", "夜景"]
    assert profile["disliked_tags"] == ["太赶"]
    assert profile["pace_preference"] == "relaxed"
    assert "destination" not in profile


def test_agent_harness_skips_memory_without_user_id(monkeypatch, tmp_path):
    monkeypatch.setattr(
        harness_module,
        "agent_observer",
        AgentObserver(trace_path=tmp_path / "agent_traces.jsonl"),
    )
    monkeypatch.setattr(memory_service, "MEMORY_PATH", tmp_path / "user_memory.json")
    memory_service.IN_MEMORY_PROFILES.clear()

    def fake_chat_completion(**kwargs):
        return ChatAgentResult(
            intent="chat",
            assistant_message="收到。",
            updated_request=None,
            updated_plan=None,
        ).model_dump_json()

    monkeypatch.setattr(harness_module.llm_service, "chat_completion", fake_chat_completion)

    result = asyncio.run(
        AgentHarness().run(
            AgentContext(
                session_id="harness-no-user",
                user_id=None,
                user_message="记住我喜欢美食",
            )
        )
    )

    assert "preference_memory_skill" in result.used_tools
    assert not (tmp_path / "user_memory.json").exists()


def test_agent_harness_memory_write_failure_does_not_break_result(monkeypatch, tmp_path):
    monkeypatch.setattr(
        harness_module,
        "agent_observer",
        AgentObserver(trace_path=tmp_path / "agent_traces.jsonl"),
    )

    def fake_chat_completion(**kwargs):
        return ChatAgentResult(
            intent="chat",
            assistant_message="收到。",
            updated_request=None,
            updated_plan=None,
        ).model_dump_json()

    def fail_update_user_preferences(user_id, preferences):
        raise PermissionError("blocked")

    monkeypatch.setattr(harness_module.llm_service, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(
        harness_module.memory_service,
        "update_user_preferences",
        fail_update_user_preferences,
    )

    result = asyncio.run(
        AgentHarness().run(
            AgentContext(
                session_id="harness-memory-failure",
                user_id="user-memory",
                user_message="记住我喜欢美食",
            )
        )
    )

    assert result.intent == "chat"
    assert result.assistant_message == "收到。"
    assert "preference_memory_skill" in result.used_tools
