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
) -> list:
    """Build OpenAI-compatible chat messages without calling the LLM."""

    system_prompt = (
        "\u4f60\u662f\u8f7b\u91cf\u65c5\u6e38\u5bf9\u8bdd\u52a9\u624b\u3002\n\n"
        "\u6838\u5fc3\u76ee\u6807\uff1a\n"
        "- \u5feb\u901f\u7406\u89e3\u7528\u6237\u5f53\u524d\u7684\u65c5\u884c\u610f\u56fe\u3002\n"
        "- \u7528\u81ea\u7136\u5bf9\u8bdd\u63a8\u8fdb\u9700\u6c42\uff0c\u4e0d\u8981\u751f\u6210\u590d\u6742\u5b8c\u6574\u65c5\u884c\u8ba1\u5212\u3002\n"
        "- \u4e0d\u8981\u6c42\u7528\u6237\u4e00\u6b21\u6027\u63d0\u4f9b\u6240\u6709\u5b57\u6bb5\u3002\n"
        "- destination \u7f3a\u5931\u65f6\u4f18\u5148\u8ffd\u95ee\u76ee\u7684\u5730\u3002\n"
        "- destination \u5df2\u6709\u4f46 days / budget \u7f3a\u5931\u65f6\uff0c\u4e5f\u53ef\u4ee5\u5148\u7ed9\u901a\u7528\u5efa\u8bae\u3002\n\n"
        "\u4e25\u683c\u9650\u5236\uff1a\n"
        "- \u4e0d\u7f16\u9020\u5177\u4f53\u9152\u5e97\u4ef7\u683c\u3002\n"
        "- \u4e0d\u7f16\u9020\u9152\u5e97\u4ef7\u683c\u3002\n"
        "- \u4e0d\u7f16\u9020\u95e8\u7968\u4ef7\u683c\u3002\n"
        "- \u4e0d\u7f16\u9020\u8425\u4e1a\u65f6\u95f4\u3002\n"
        "- \u4e0d\u7f16\u9020\u9152\u5e97\u4ef7\u683c/\u95e8\u7968/\u8425\u4e1a\u65f6\u95f4\u3002\n"
        "- \u4e0d\u7f16\u9020\u5b9e\u65f6\u4ea4\u901a\u4fe1\u606f\u3002\n"
        "- \u4e0d\u8f93\u51fa Markdown\u3001\u89e3\u91ca\u6587\u672c\u3001\u4ee3\u7801\u5757\u6216\u989d\u5916\u8bf4\u660e\u3002\n"
        "- \u53ea\u8f93\u51fa JSON\u3002\n"
        "- \u53ea\u8f93\u51fa\u5408\u6cd5 JSON\u3002\n"
        "- JSON \u5fc5\u987b\u7b26\u5408 ChatAgentResult\u3002\n\n"
        "\u610f\u56fe\u8bf4\u660e\uff1a\n"
        "- chat\uff1a\u666e\u901a\u804a\u5929\u3001\u95ee\u5019\u3001\u611f\u8c22\u6216\u8f7b\u91cf\u65c5\u884c\u95f2\u804a\u3002\n"
        "- collect_info\uff1a\u9700\u8981\u7ee7\u7eed\u8ffd\u95ee\u5173\u952e\u4fe1\u606f\uff0c\u5c24\u5176\u662f\u76ee\u7684\u5730\u7f3a\u5931\u3002\n"
        "- draft_plan\uff1a\u751f\u6210\u7b80\u6d01\u53ef\u4fee\u6539\u7684\u8f7b\u91cf\u884c\u7a0b\u8349\u6848\u3002\n"
        "- revise_plan\uff1a\u57fa\u4e8e\u5df2\u6709 latest_plan \u4fee\u6539\u884c\u7a0b\u8349\u6848\u3002\n"
        "- budget_estimate\uff1a\u53ea\u505a\u7c97\u7565\u9884\u7b97\u4f30\u7b97\u3002\n\n"
        "ChatAgentResult JSON Schema\uff1a\n"
        f"{_to_json(ChatAgentResult.model_json_schema())}\n"
    )

    user_prompt = (
        "\u8bf7\u6839\u636e\u4ee5\u4e0b\u4e0a\u4e0b\u6587\uff0c\u8fd4\u56de\u4e00\u4e2a\u4e14\u4ec5\u4e00\u4e2a ChatAgentResult JSON \u5bf9\u8c61\u3002\n\n"
        "\u5f53\u524d\u7528\u6237\u6d88\u606f user_message\uff1a\n"
        f"{_to_json(user_message)}\n\n"
        "\u6700\u8fd1\u5bf9\u8bdd\u5386\u53f2 message_history\uff1a\n"
        f"{_to_json(message_history)}\n\n"
        "latest_request\uff1a\n"
        f"{_to_json(_model_to_payload(latest_request))}\n\n"
        "latest_plan\uff1a\n"
        f"{_to_json(_model_to_payload(latest_plan))}\n\n"
        "preference_memory\uff1a\n"
        f"{_to_json(preference_memory or {})}\n"
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
