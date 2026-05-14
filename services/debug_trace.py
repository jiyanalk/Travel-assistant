from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def append_debug_trace(
    trace: list[dict[str, Any]] | None,
    *,
    step: str,
    stage: str,
    payload: Any = None,
    label: str | None = None,
) -> None:
    if trace is None:
        return

    trace.append(
        {
            "step": step,
            "stage": stage,
            "label": label,
            "payload": to_debug_value(payload),
        }
    )


def to_debug_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): to_debug_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_debug_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)
