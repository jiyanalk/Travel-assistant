from __future__ import annotations

from typing import Optional

from services.retrieval_service import retrieve_city_context


def get_rag_context(
    destination: Optional[str],
    interests: list[str],
    user_message: str,
) -> dict:
    """Return lightweight local city knowledge for prompt grounding."""

    contexts = retrieve_city_context(
        destination=destination,
        interests=interests or [],
        user_message=user_message,
        top_k=3,
    )
    if not contexts:
        return {
            "available": False,
            "contexts": [],
            "summary": "没有找到匹配的本地城市知识。",
        }

    city = contexts[0].get("city") or destination or "目标城市"
    return {
        "available": True,
        "contexts": contexts,
        "summary": f"已检索到{city}相关轻量城市知识。",
    }
