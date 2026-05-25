from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LightTripRequest(BaseModel):
    origin: str | None = Field(default=None, description="出发地，可以为空。")
    destination: str | None = Field(default=None, description="目的地，可以为空。")
    days: int | None = Field(default=None, description="旅行天数，可以为空。")
    people: int = Field(default=1, description="出行人数，默认为 1 人。")
    budget: float | None = Field(default=None, description="总预算，默认按人民币估算。")
    interests: list[str] = Field(default_factory=list, description="用户感兴趣的旅行主题。")
    travel_style: str | None = Field(
        default=None,
        description="旅行风格，例如轻松、亲子、美食、拍照。",
    )
    constraints: list[str] = Field(default_factory=list, description="用户限制或特殊要求。")


class LightTripPlan(BaseModel):
    destination: str | None = Field(default=None, description="行程目的地。")
    days: int | None = Field(default=None, description="行程天数。")
    summary: str = Field(description="行程草案摘要。")
    daily_plan: list[str] = Field(default_factory=list, description="按天组织的简要行程安排。")
    budget_summary: str | None = Field(default=None, description="粗略预算说明。")
    tips: list[str] = Field(default_factory=list, description="轻量旅行提示。")


class ChatAgentResult(BaseModel):
    intent: Literal["chat", "collect_info", "draft_plan", "revise_plan", "budget_estimate"] = Field(
        description="本轮对话意图。"
    )
    assistant_message: str = Field(description="返回给用户的自然语言回复。")
    updated_request: LightTripRequest | None = Field(
        default=None,
        description="本轮更新后的轻量旅行需求。",
    )
    updated_plan: LightTripPlan | None = Field(
        default=None,
        description="本轮更新后的轻量行程草案。",
    )
    missing_fields: list[str] = Field(default_factory=list, description="仍需补充的关键字段。")
    used_tools: list[str] = Field(default_factory=list, description="本轮使用过的工具名称。")
