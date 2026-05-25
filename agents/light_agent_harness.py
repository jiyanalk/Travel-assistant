from __future__ import annotations

import asyncio
from uuid import uuid4

from schemas.agent_context import AgentContext
from schemas.light_trip import ChatAgentResult, LightTripRequest
from services import llm_service, memory_service
from services.agent_observer import agent_observer, build_trace_payload
from services.light_prompt_builder import build_light_travel_prompt
from services.output_validator import validate_chat_agent_result
from services.skill_registry import SkillRegistry, default_skill_registry
from services.tool_registry import ToolRegistry, default_tool_registry
from skills import BaseSkill


FALLBACK_MESSAGE = "我刚刚理解得不够稳定，可以请你换个方式描述一下你的旅行需求吗？"
PRE_LLM_SKILLS = {"rag_context_skill", "plan_revision_skill"}
POST_LLM_SKILLS = {"budget_skill", "preference_memory_skill"}


class AgentHarness:
    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.tool_registry = tool_registry or default_tool_registry
        self.skill_registry = skill_registry or default_skill_registry

    async def run(self, context: AgentContext) -> ChatAgentResult:
        trace_id = context.trace_id or str(uuid4())
        context.trace_id = trace_id

        selected_skills = await self.skill_registry.select_skills(context)
        pre_skills = _filter_skills(selected_skills, PRE_LLM_SKILLS)
        pre_skill_outputs = await self.skill_registry.run_skills(context, pre_skills)
        self._apply_skill_outputs_to_context(context, pre_skill_outputs)

        selected_tools = self._select_pre_llm_tools(context, pre_skill_outputs)
        context.selected_tools = selected_tools
        context.selected_skills = [skill.name for skill in selected_skills]
        tool_outputs = await self._run_tools_safely(selected_tools, context)
        context.tool_context.update(tool_outputs)
        if "rag_context_tool" in tool_outputs:
            context.tool_context["rag_context"] = tool_outputs["rag_context_tool"]

        messages = build_light_travel_prompt(
            user_message=context.user_message,
            message_history=context.message_history,
            latest_request=context.latest_request,
            latest_plan=context.latest_plan,
            preference_memory=context.preference_memory,
            tool_context=context.tool_context,
        )
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]
        prompt_text = f"{system_prompt}\n\n{user_prompt}"

        raw_output: str | None = None
        validation_success = False
        fallback_used = False
        memory_update: dict = {"updated": False}
        skill_outputs: dict = dict(pre_skill_outputs)

        try:
            raw_output = await asyncio.to_thread(
                llm_service.chat_completion,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                json_mode=True,
                trace_step="light_travel_chat",
                trace_label="chat_agent_result",
            )
            result = validate_chat_agent_result(raw_output)
            validation_success = True
            result, memory_update, post_skill_outputs = await self._postprocess_with_tools_and_skills(
                result,
                context,
                tool_outputs,
                selected_tools,
            )
            skill_outputs.update(post_skill_outputs)
            result.used_tools = _dedupe(
                [*_skill_names_from_outputs(pre_skill_outputs), *result.used_tools]
            )
        except Exception:
            fallback_used = True
            result = self._fallback_result(context)

        self._record_trace(
            context=context,
            selected_tools=_dedupe([*selected_tools, *result.used_tools]),
            tool_outputs=tool_outputs,
            selected_skills=_dedupe([*context.selected_skills, *_skill_names_from_outputs(skill_outputs)]),
            skill_outputs=skill_outputs,
            prompt_text=prompt_text,
            raw_output=raw_output,
            validation_success=validation_success,
            fallback_used=fallback_used,
            memory_update=memory_update,
            final_intent=result.intent,
        )
        return result

    async def _postprocess_with_tools_and_skills(
        self,
        result: ChatAgentResult,
        context: AgentContext,
        tool_outputs: dict,
        selected_tools: list[str],
    ) -> tuple[ChatAgentResult, dict, dict]:
        if result.updated_request is not None or context.latest_request is not None:
            merge_context = context.model_copy(
                deep=True,
                update={
                    "tool_context": {
                        **context.tool_context,
                        "updated_request": result.updated_request.model_dump(mode="json")
                        if result.updated_request
                        else None,
                    }
                },
            )
            merge_output = await self._run_tool_safely("trip_request_merge_tool", merge_context)
            tool_outputs["trip_request_merge_tool"] = merge_output
            merged_payload = merge_output.get("merged_request")
            if merged_payload:
                result.updated_request = LightTripRequest.model_validate(merged_payload)
            _append_tool(result, "trip_request_merge_tool")

            alias_output = await self._run_tool_safely(
                "city_alias_tool",
                self._context_with_result(context, result),
            )
            tool_outputs["city_alias_tool"] = alias_output
            normalized_payload = alias_output.get("normalized_request")
            if normalized_payload:
                result.updated_request = LightTripRequest.model_validate(normalized_payload)
            if alias_output.get("replaced"):
                _append_tool(result, "city_alias_tool")

        post_context = self._context_with_result(context, result)
        post_context.tool_context["intent"] = result.intent
        post_skills = _filter_skills(
            await self.skill_registry.select_skills(post_context),
            POST_LLM_SKILLS,
        )
        post_skill_outputs = await self.skill_registry.run_skills(post_context, post_skills)

        budget_output = _skill_data(post_skill_outputs, "budget_skill")
        if budget_output:
            if result.updated_plan is not None and budget_output.get("budget_summary"):
                result.updated_plan.budget_summary = budget_output.get("budget_summary")
            _append_tool(result, "budget_skill")
        elif _request_has_budget_inputs(result.updated_request):
            simple_budget_output = await self._run_tool_safely("simple_budget_tool", post_context)
            tool_outputs["simple_budget_tool"] = simple_budget_output
            if simple_budget_output.get("available") and result.updated_plan is not None:
                result.updated_plan.budget_summary = simple_budget_output.get("summary")
            _append_tool(result, "simple_budget_tool")

        if result.updated_plan is not None:
            quality_output = await self._run_tool_safely("trip_quality_check_tool", post_context)
            tool_outputs["trip_quality_check_tool"] = quality_output
            _append_tool(result, "trip_quality_check_tool")

        preference_output = _skill_data(post_skill_outputs, "preference_memory_skill")
        if preference_output:
            memory_update = preference_output.get("memory_update", {"updated": False})
            _append_tool(result, "preference_memory_skill")
        else:
            preference_tool_output = await self._run_tool_safely(
                "preference_extractor_tool",
                post_context,
            )
            tool_outputs["preference_extractor_tool"] = preference_tool_output
            memory_update = self._apply_memory_update(context, preference_tool_output)
            if preference_tool_output.get("should_update"):
                _append_tool(result, "preference_extractor_tool")

        result.used_tools = _dedupe([*selected_tools, *result.used_tools])
        result.used_tools = _dedupe([*_skill_names_from_outputs(post_skill_outputs), *result.used_tools])
        return result, memory_update, post_skill_outputs

    def _apply_memory_update(self, context: AgentContext, preference_output: dict) -> dict:
        if not preference_output.get("should_update"):
            return {
                "updated": False,
                "reason": preference_output.get("reason", "没有明确长期记忆意图"),
            }
        if not context.user_id or context.user_id == "guest":
            return {
                "updated": False,
                "reason": "缺少有效 user_id，跳过长期记忆写入",
            }
        try:
            updated = memory_service.update_user_preferences(
                context.user_id,
                preference_output.get("preferences", {}),
            )
            return {
                "updated": True,
                "preferences": preference_output.get("preferences", {}),
                "profile": updated,
            }
        except Exception as exc:
            return {
                "updated": False,
                "reason": f"memory write failed: {exc}",
            }

    def _context_with_result(
        self,
        context: AgentContext,
        result: ChatAgentResult,
    ) -> AgentContext:
        return context.model_copy(
            deep=True,
            update={
                "latest_request": result.updated_request or context.latest_request,
                "latest_plan": result.updated_plan or context.latest_plan,
                "tool_context": {
                    **context.tool_context,
                    "updated_request": result.updated_request.model_dump(mode="json")
                    if result.updated_request
                    else None,
                    "updated_plan": result.updated_plan.model_dump(mode="json")
                    if result.updated_plan
                    else None,
                },
                "skill_context": dict(context.skill_context),
            },
        )

    def _select_pre_llm_tools(
        self,
        context: AgentContext,
        pre_skill_outputs: dict,
    ) -> list[str]:
        selected = self.tool_registry.select_tools(context)
        if "rag_context_skill" in pre_skill_outputs:
            selected = [name for name in selected if name != "rag_context_tool"]
        return selected

    def _apply_skill_outputs_to_context(
        self,
        context: AgentContext,
        skill_outputs: dict,
    ) -> None:
        context.skill_context.update(skill_outputs)
        context.tool_context["skill_context"] = context.skill_context

        rag_data = _skill_data(skill_outputs, "rag_context_skill")
        if rag_data and "rag_context" in rag_data:
            context.tool_context["rag_context"] = rag_data["rag_context"]

        revision_data = _skill_data(skill_outputs, "plan_revision_skill")
        if revision_data and "revision_hints" in revision_data:
            context.tool_context["revision_hints"] = revision_data["revision_hints"]

    async def _run_tools_safely(
        self,
        tool_names: list[str],
        context: AgentContext,
    ) -> dict:
        outputs: dict = {}
        for tool_name in tool_names:
            outputs[tool_name] = await self._run_tool_safely(tool_name, context)
        return outputs

    async def _run_tool_safely(
        self,
        tool_name: str,
        context: AgentContext,
    ) -> dict:
        try:
            return await self.tool_registry.run_tool(tool_name, context)
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    def _fallback_result(self, context: AgentContext) -> ChatAgentResult:
        return ChatAgentResult(
            intent="chat",
            assistant_message=FALLBACK_MESSAGE,
            updated_request=context.latest_request,
            updated_plan=context.latest_plan,
            missing_fields=[],
            used_tools=[],
        )

    def _record_trace(
        self,
        *,
        context: AgentContext,
        selected_tools: list[str],
        tool_outputs: dict,
        selected_skills: list[str],
        skill_outputs: dict,
        prompt_text: str,
        raw_output: str | None,
        validation_success: bool,
        fallback_used: bool,
        memory_update: dict,
        final_intent: str | None,
    ) -> None:
        trace = build_trace_payload(
            trace_id=context.trace_id or str(uuid4()),
            session_id=context.session_id,
            user_id=context.user_id,
            user_message=context.user_message,
            selected_tools=selected_tools,
            tool_outputs=tool_outputs,
            selected_skills=selected_skills,
            skill_outputs=skill_outputs,
            prompt_text=prompt_text,
            raw_model_output=raw_output,
            validation_success=validation_success,
            fallback_used=fallback_used,
            memory_update=memory_update,
            final_intent=final_intent,
        )
        agent_observer.record(trace)


def _request_has_budget_inputs(request: LightTripRequest | None) -> bool:
    return (
        request is not None
        and request.days is not None
        and request.people is not None
        and request.budget is not None
    )


def _filter_skills(skills: list[BaseSkill], names: set[str]) -> list[BaseSkill]:
    return [skill for skill in skills if skill.name in names]


def _skill_data(skill_outputs: dict, skill_name: str) -> dict:
    output = skill_outputs.get(skill_name)
    if not isinstance(output, dict) or output.get("success") is False:
        return {}
    data = output.get("data")
    return data if isinstance(data, dict) else {}


def _skill_names_from_outputs(skill_outputs: dict) -> list[str]:
    return [
        name
        for name, output in skill_outputs.items()
        if isinstance(output, dict) and output.get("success") is not False
    ]


def _append_tool(result: ChatAgentResult, tool_name: str) -> None:
    if tool_name not in result.used_tools:
        result.used_tools.append(tool_name)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
