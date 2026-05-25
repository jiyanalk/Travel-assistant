from __future__ import annotations

import json
from typing import Any, Optional

from schemas.light_trip import ChatAgentResult, LightTripPlan, LightTripRequest


def build_light_travel_prompt(
    user_message: str,
    message_history: list,
    latest_request: Optional[LightTripRequest],
    latest_plan: Optional[LightTripPlan],
    preference_memory: Optional[dict],
    tool_context: Optional[dict[str, Any]] = None,
) -> list:
    """Build OpenAI-compatible chat messages without calling the LLM."""

    system_prompt = (
        "你是轻量旅游对话助手。\n\n"
        "核心目标：\n"
        "- 快速理解用户当前的旅行意图。\n"
        "- 用自然对话推进需求，不要生成复杂完整旅行计划。\n"
        "- 不要求用户一次性提供所有字段。\n"
        "- destination 缺失时优先追问目的地。\n"
        "- destination 已有但 days / budget 缺失时，也可以先给通用建议。\n\n"
        "严格限制：\n"
        "- 不编造具体酒店价格。\n"
        "- 不编造门票价格。\n"
        "- 不编造营业时间。\n"
        "- 不编造实时交通信息。\n"
        "- 不输出 Markdown、解释文本、代码块或额外说明。\n"
        "- 只输出 JSON。\n"
        "- 只输出合法 JSON。\n"
        "- JSON 必须符合 ChatAgentResult。\n\n"
        "工具上下文规则：\n"
        "- 工具上下文只能作为参考信息。\n"
        "- 如果 tool_context.rag_context 存在，你可以参考本地城市知识，但不要逐字照抄。\n"
        "- 本地城市知识不是实时信息；如果知识不足，要谨慎表达。\n"
        "- 不编造实时价格。\n"
        "- 不要因为 RAG 或其他工具信息而编造实时价格、营业时间、门票或交通信息。\n\n"
        "意图说明：\n"
        "- chat：普通聊天、问候、感谢或轻量旅行闲聊。\n"
        "- collect_info：需要继续追问关键信息，尤其是目的地缺失。\n"
        "- draft_plan：生成简洁可修改的轻量行程草案。\n"
        "- revise_plan：基于已有 latest_plan 修改行程草案。\n"
        "- budget_estimate：只做粗略预算估算。\n\n"
        "ChatAgentResult JSON Schema：\n"
        f"{_to_json(ChatAgentResult.model_json_schema())}\n"
    )

    user_prompt = (
        "请根据以下上下文，返回一个且仅一个 ChatAgentResult JSON 对象。\n\n"
        "当前用户消息 user_message：\n"
        f"{_to_json(user_message)}\n\n"
        "最近对话历史 message_history：\n"
        f"{_to_json(message_history)}\n\n"
        "latest_request：\n"
        f"{_to_json(_model_to_payload(latest_request))}\n\n"
        "latest_plan：\n"
        f"{_to_json(_model_to_payload(latest_plan))}\n\n"
        "preference_memory：\n"
        f"{_to_json(preference_memory or {})}\n\n"
        "tool_context：\n"
        f"{_to_json(tool_context or {})}\n"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _model_to_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
