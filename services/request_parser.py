from __future__ import annotations

from typing import Any

from schemas.trip_request import TripRequest
from services.llm_service import generate_structured_output, generate_text, load_prompt


def parse_trip_request(
    message: str,
    debug_trace: list[dict[str, Any]] | None = None,
) -> TripRequest:
    prompt = load_prompt("requirement_prompt.md")
    return generate_structured_output(
        model_class=TripRequest,
        system_prompt=prompt,
        user_prompt=(
            "请从下面的用户旅行需求中提取结构化字段。\n"
            "要求：\n"
            "1. 不要猜测未提供的信息，未知字段必须为 null 或空数组。\n"
            "2. 如果用户只说“6月”这类模糊时间，不要擅自补成具体日期。\n"
            "3. pace 只能是 relaxed、normal、packed。\n"
            "4. travelers 必须始终返回 adults、children、seniors。\n"
            "5. 如果用户表达的是偏好或顾虑，也要尽量放入 special_requirements。\n"
            "6. 如果用户提到了‘酒店预算 200 元/晚’、‘住宿 300 一晚’这类信息，请提取到 hotel_budget_per_night。\n"
            f"用户输入：{message}"
        ),
        temperature=0.1,
        debug_trace=debug_trace,
        trace_step="parse_user_request",
        trace_label="trip_request_extraction",
    )


def detect_missing_fields(request: TripRequest) -> list[str]:
    missing_fields = []
    if not request.origin:
        missing_fields.append("origin")
    if not request.destination:
        missing_fields.append("destination")
    if not request.duration_days:
        missing_fields.append("duration_days")
    if not request.budget:
        missing_fields.append("budget")
    if not request.interests:
        missing_fields.append("interests")
    return missing_fields


def build_clarification_question(
    *,
    user_message: str,
    parsed_request: TripRequest,
    missing_fields: list[str],
    debug_trace: list[dict[str, Any]] | None = None,
) -> str:
    missing_text = "、".join(missing_fields)
    return generate_text(
        system_prompt=(
            "你是旅行规划助手。\n"
            "当用户信息不足时，请用简洁、自然的中文提出补充问题。\n"
            "不要编造用户没有提到过的目的地、天数、出发地、预算或身份信息。\n"
            "只输出给用户看的追问内容，不要输出分析过程。"
        ),
        user_prompt=(
            f"用户原始输入：{user_message}\n"
            f"当前已解析请求：{parsed_request.model_dump_json(indent=2)}\n"
            f"缺失字段：{missing_text}\n"
            "请生成一段友好的追问，优先整理成 1. 2. 3. 这样的短列表。"
        ),
        temperature=0.2,
        debug_trace=debug_trace,
        trace_step="check_missing_fields",
        trace_label="clarification_question",
    )
