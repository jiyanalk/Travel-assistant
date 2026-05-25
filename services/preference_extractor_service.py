from __future__ import annotations

from typing import Any


MEMORY_TRIGGERS = [
    "记住",
    "帮我记住",
    "下次也这样",
    "下次也",
    "以后也这样",
    "以后也",
    "以后推荐",
    "我一直喜欢",
    "我通常喜欢",
    "我的偏好是",
    "remember",
    "next time",
    "my preference",
]

INTEREST_KEYWORDS = {
    "美食": ["美食", "吃", "小吃", "火锅", "food"],
    "夜景": ["夜景", "夜生活", "night view", "nightlife"],
    "city walk": ["city walk", "City Walk", "城市漫步", "散步"],
    "亲子游": ["亲子", "带孩子", "family"],
}


def extract_preference_updates(user_message: str) -> dict[str, Any]:
    if not _has_memory_intent(user_message):
        return {
            "should_update": False,
            "preferences": {},
            "reason": "没有明确长期记忆意图",
        }

    preferences: dict[str, Any] = {}
    interests = _extract_interests(user_message)
    if interests:
        preferences["interests"] = interests

    avoid = []
    if (
        "不喜欢太赶" in user_message
        or "不要太赶" in user_message
        or "不要安排太赶" in user_message
        or "别太赶" in user_message
    ):
        avoid.append("太赶")
        preferences["pace_preference"] = "relaxed"
    if "慢节奏" in user_message or "轻松" in user_message:
        preferences["pace_preference"] = "relaxed"
    if "预算偏经济" in user_message or "经济型" in user_message:
        preferences["budget_preference"] = "economy"
    home_city = _extract_home_city(user_message)
    if home_city:
        preferences["home_city"] = home_city
    if avoid:
        preferences["disliked_tags"] = avoid

    return {
        "should_update": bool(preferences),
        "preferences": preferences,
        "reason": "用户明确要求记住偏好" if preferences else "有记忆意图但未识别到稳定偏好",
    }


def _has_memory_intent(user_message: str) -> bool:
    lowered = user_message.lower()
    return any(trigger.lower() in lowered for trigger in MEMORY_TRIGGERS)


def _extract_interests(user_message: str) -> list[str]:
    lowered = user_message.lower()
    interests: list[str] = []
    for interest, keywords in INTEREST_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            interests.append(interest)
    return interests


def _extract_home_city(user_message: str) -> str | None:
    markers = ["我通常从", "我一般从", "我经常从", "常从"]
    for marker in markers:
        if marker not in user_message:
            continue
        after = user_message.split(marker, 1)[1]
        city = after.split("出发", 1)[0].strip(" ，,。.")
        if city and len(city) <= 8:
            return city
    return None
