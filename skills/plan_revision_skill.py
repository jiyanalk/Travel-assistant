from __future__ import annotations

from schemas.agent_context import AgentContext
from skills.base import BaseSkill, SkillResult


REVISION_KEYWORDS = ["修改", "改成", "改得", "调整", "不要太赶", "轻松一点", "放松一点", "慢一点"]


class PlanRevisionSkill(BaseSkill):
    name = "plan_revision_skill"
    intents = ["revise_plan"]

    async def can_handle(self, context: AgentContext) -> bool:
        intent = str(context.tool_context.get("intent") or "").strip()
        if intent == "revise_plan":
            return True
        return any(keyword in context.user_message for keyword in REVISION_KEYWORDS)

    async def run(self, context: AgentContext) -> SkillResult:
        hints = []
        message = context.user_message
        if any(keyword in message for keyword in ["不要太赶", "轻松一点", "放松一点", "慢一点"]):
            hints.append("降低每日点位密度，减少跨区域移动，保留休息和自由活动时间。")
        if any(keyword in message for keyword in ["修改", "改成", "改得", "调整"]):
            hints.append("基于 latest_plan 修改，不要完全重写无关内容。")
        if context.latest_plan is None:
            hints.append("当前没有已有计划时，先把用户修改要求转为新的轻量草案约束。")
        return SkillResult(
            name=self.name,
            success=True,
            data={"revision_hints": hints},
        )
