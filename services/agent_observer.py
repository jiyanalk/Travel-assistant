from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.config import ROOT_DIR


TRACE_PATH = ROOT_DIR / "data" / "agent_traces.jsonl"


class AgentTrace(BaseModel):
    trace_id: str
    session_id: str
    user_id: str | None = None
    user_message: str
    selected_tools: list[str] = Field(default_factory=list)
    tool_outputs: dict[str, Any] = Field(default_factory=dict)
    selected_skills: list[str] = Field(default_factory=list)
    skill_outputs: dict[str, Any] = Field(default_factory=dict)
    skill_errors: dict[str, Any] = Field(default_factory=dict)
    prompt_preview: str | None = None
    prompt_length: int | None = None
    raw_model_output: str | None = None
    validation_success: bool = False
    fallback_used: bool = False
    memory_update: dict[str, Any] = Field(default_factory=dict)
    final_intent: str | None = None
    created_at: str


class AgentObserver:
    def __init__(self, trace_path=TRACE_PATH) -> None:
        self.trace_path = trace_path

    def record(self, trace: AgentTrace | dict[str, Any]) -> None:
        try:
            trace_obj = trace if isinstance(trace, AgentTrace) else AgentTrace.model_validate(trace)
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("a", encoding="utf-8") as file:
                file.write(
                    json.dumps(trace_obj.model_dump(mode="json"), ensure_ascii=False)
                    + "\n"
                )
        except Exception:
            # Observability must never break the chat path.
            return


def build_trace_payload(
    *,
    trace_id: str,
    session_id: str,
    user_id: str | None,
    user_message: str,
    selected_tools: list[str],
    tool_outputs: dict[str, Any],
    selected_skills: list[str] | None = None,
    skill_outputs: dict[str, Any] | None = None,
    prompt_text: str,
    raw_model_output: str | None,
    validation_success: bool,
    fallback_used: bool,
    memory_update: dict[str, Any] | None = None,
    final_intent: str | None,
) -> AgentTrace:
    return AgentTrace(
        trace_id=trace_id,
        session_id=session_id,
        user_id=user_id,
        user_message=_truncate(user_message, 300),
        selected_tools=selected_tools,
        tool_outputs=_safe_tool_outputs(tool_outputs),
        selected_skills=selected_skills or [],
        skill_outputs=_safe_tool_outputs(skill_outputs or {}),
        skill_errors=_extract_skill_errors(skill_outputs or {}),
        prompt_preview=_truncate(prompt_text, 500),
        prompt_length=len(prompt_text),
        raw_model_output=_truncate(raw_model_output, 1000) if raw_model_output else None,
        validation_success=validation_success,
        fallback_used=fallback_used,
        memory_update=memory_update or {},
        final_intent=final_intent,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _safe_tool_outputs(tool_outputs: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(tool_outputs, ensure_ascii=False, default=str))
    except TypeError:
        return {"serialization_error": True}


def _extract_skill_errors(skill_outputs: dict[str, Any]) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    for name, output in skill_outputs.items():
        if isinstance(output, dict) and output.get("success") is False:
            errors[name] = output.get("message") or output.get("data", {}).get("error")
    return errors


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...[truncated]"


agent_observer = AgentObserver()
