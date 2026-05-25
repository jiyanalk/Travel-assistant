from __future__ import annotations

from schemas.agent_context import AgentContext
from services import memory_service
from services.preference_extractor_service import extract_preference_updates
from skills.base import BaseSkill, SkillResult


class PreferenceMemorySkill(BaseSkill):
    name = "preference_memory_skill"
    intents = ["chat", "collect_info", "draft_plan", "revise_plan"]

    async def can_handle(self, context: AgentContext) -> bool:
        return bool(extract_preference_updates(context.user_message).get("should_update"))

    async def run(self, context: AgentContext) -> SkillResult:
        preference_output = extract_preference_updates(context.user_message)
        memory_update = _apply_memory_update(context, preference_output)
        return SkillResult(
            name=self.name,
            success=True,
            data={
                "preference_output": preference_output,
                "memory_update": memory_update,
            },
            message=memory_update.get("reason"),
        )


def _apply_memory_update(context: AgentContext, preference_output: dict) -> dict:
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
