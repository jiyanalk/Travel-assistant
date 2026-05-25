from __future__ import annotations

import json
import re

from pydantic import ValidationError

from schemas.light_trip import ChatAgentResult


class OutputValidationError(ValueError):
    """Raised when model output cannot be parsed as ChatAgentResult."""


def validate_chat_agent_result(raw_output: str) -> ChatAgentResult:
    """Parse and validate model output as a ChatAgentResult.

    The validator is intentionally forgiving about wrappers: it accepts a plain
    JSON object, a fenced ```json block, or text that contains one JSON object.
    """

    try:
        payload = _extract_json_object(raw_output)
        return ChatAgentResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise OutputValidationError(f"Invalid ChatAgentResult output: {exc}") from exc


def _extract_json_object(raw_output: str) -> dict:
    text = (raw_output or "").strip()
    if not text:
        raise OutputValidationError("Empty model output.")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    json_text = _first_balanced_json_object(text)
    if json_text is None:
        raise OutputValidationError("No JSON object found in model output.")
    return json.loads(json_text)


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
