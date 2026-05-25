from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from schemas.agent_context import AgentContext


class SkillResult(BaseModel):
    name: str
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class BaseSkill(ABC):
    name: str
    intents: list[str] = []

    @abstractmethod
    async def can_handle(self, context: AgentContext) -> bool:
        """Return whether this skill should run for the current context."""

    @abstractmethod
    async def run(self, context: AgentContext) -> SkillResult:
        """Run the skill and return structured context or side-effect results."""
