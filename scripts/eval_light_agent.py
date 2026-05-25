from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.light_travel_chat_agent import FALLBACK_MESSAGE, LightTravelChatAgent
from agents import light_agent_harness as harness_module
from app.config import ROOT_DIR
from schemas.light_trip import ChatAgentResult
from services import memory_service


DEFAULT_CASES_PATH = ROOT_DIR / "evals" / "light_agent_cases.jsonl"
DEFAULT_RESULT_PATH = ROOT_DIR / "evals" / "results" / "latest_eval_result.json"
DEFAULT_MEMORY_PATH = ROOT_DIR / "evals" / "results" / "eval_user_memory.json"

FIELD_CHECKS = {"destination", "days", "people", "budget", "interests_contains"}
FALLBACK_CHECKS = {"fallback"}
TOOL_CHECKS = {"tools", "rag_hit"}
MEMORY_CHECKS = {"memory_update", "memory_not_polluted"}
HALLUCINATION_CHECKS = {"hallucination_guard"}


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                cases.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
    return cases


async def run_evaluation(
    cases_path: str | Path = DEFAULT_CASES_PATH,
    *,
    live: bool = False,
    result_path: str | Path = DEFAULT_RESULT_PATH,
    memory_path: str | Path = DEFAULT_MEMORY_PATH,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    result_path = Path(result_path)
    memory_path = Path(memory_path)

    original_chat_completion = harness_module.llm_service.chat_completion
    original_memory_path = memory_service.MEMORY_PATH
    memory_service.MEMORY_PATH = memory_path
    memory_service.IN_MEMORY_PROFILES.clear()
    if memory_path.exists():
        memory_path.unlink()

    case_results: list[dict[str, Any]] = []
    try:
        for case in cases:
            case_results.append(
                await _run_case(
                    case=case,
                    live=live,
                    original_chat_completion=original_chat_completion,
                )
            )
    finally:
        harness_module.llm_service.chat_completion = original_chat_completion
        memory_service.MEMORY_PATH = original_memory_path
        memory_service.IN_MEMORY_PROFILES.clear()

    metrics = compute_metrics(case_results)
    payload = {
        "mode": "live" if live else "mock",
        "metrics": metrics,
        "cases": case_results,
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


async def _run_case(
    *,
    case: dict[str, Any],
    live: bool,
    original_chat_completion,
) -> dict[str, Any]:
    session_id = f"eval_{case.get('id', 'case')}_{uuid4().hex[:8]}"
    user_id = f"eval_user_{case.get('id', 'case')}_{uuid4().hex[:8]}"
    turns = [turn for turn in case.get("turns", []) if turn.get("role") == "user"]
    mock_outputs = list(case.get("mock_outputs", []))
    mock_index = {"value": 0}

    if not live:
        def fake_chat_completion(**kwargs):
            index = mock_index["value"]
            mock_index["value"] += 1
            if index >= len(mock_outputs):
                return _default_mock_output(turns[index]["content"] if index < len(turns) else "")
            output = mock_outputs[index]
            if isinstance(output, str):
                return output
            return json.dumps(output, ensure_ascii=False)

        harness_module.llm_service.chat_completion = fake_chat_completion
    else:
        harness_module.llm_service.chat_completion = original_chat_completion

    errors: list[str] = []
    final_result: ChatAgentResult | None = None
    try:
        agent = LightTravelChatAgent()
        for turn in turns:
            final_result = await agent.chat(
                session_id=session_id,
                user_id=user_id,
                user_message=turn["content"],
            )
    except Exception as exc:
        errors.append(f"case execution failed: {exc}")

    checks = _evaluate_case(
        case=case,
        result=final_result,
        user_id=user_id,
        errors=errors,
    )
    passed = not errors and all(checks.values())
    return {
        "id": case.get("id"),
        "name": case.get("name"),
        "passed": passed,
        "checks": checks,
        "errors": errors,
        "result": final_result.model_dump(mode="json") if final_result else None,
    }


def _evaluate_case(
    *,
    case: dict[str, Any],
    result: ChatAgentResult | None,
    user_id: str,
    errors: list[str],
) -> dict[str, bool]:
    expected = case.get("expected", {})
    checks: dict[str, bool] = {"json_valid": result is not None}
    if result is None:
        for key in expected:
            checks[key] = False
        return checks

    request = result.updated_request
    plan = result.updated_plan

    if "destination" in expected:
        checks["destination"] = request is not None and request.destination == expected["destination"]
    if "days" in expected:
        checks["days"] = request is not None and _number_equal(request.days, expected["days"])
    if "people" in expected:
        checks["people"] = request is not None and _number_equal(request.people, expected["people"])
    if "budget" in expected:
        checks["budget"] = request is not None and _number_equal(request.budget, expected["budget"])
    if "interests_contains" in expected:
        interests = request.interests if request else []
        checks["interests_contains"] = all(item in interests for item in expected["interests_contains"])
    if "intent_any_of" in expected:
        checks["intent"] = result.intent in expected["intent_any_of"]
    if "missing_fields_contains" in expected:
        checks["missing_fields"] = all(item in result.missing_fields for item in expected["missing_fields_contains"])
    if "assistant_contains_any" in expected:
        checks["assistant_contains"] = any(item in result.assistant_message for item in expected["assistant_contains_any"])
    if "tools_contains_any" in expected:
        checks["tools"] = _contains_any_tool(result.used_tools, expected["tools_contains_any"])
    if "rag_should_hit" in expected:
        checks["rag_hit"] = (
            not expected["rag_should_hit"]
            or _contains_any_tool(result.used_tools, ["rag_context_skill", "rag_context_tool", "RagContextSkill"])
        )
    if "plan_should_exist" in expected:
        checks["plan_exists"] = bool(plan) is bool(expected["plan_should_exist"])
    if "plan_summary_contains" in expected:
        summary = plan.summary if plan else ""
        checks["plan_summary"] = all(item in summary for item in expected["plan_summary_contains"])
    if "budget_summary_contains" in expected:
        budget_summary = plan.budget_summary if plan else ""
        checks["budget_summary"] = all(item in (budget_summary or "") for item in expected["budget_summary_contains"])
    if "should_not_contain" in expected:
        text = _result_text(result)
        checks["hallucination_guard"] = all(item not in text for item in expected["should_not_contain"])
    if "memory_should_update" in expected:
        profile = memory_service.get_user_preferences(user_id)
        updated = _profile_has_stable_values(profile)
        checks["memory_update"] = updated is bool(expected["memory_should_update"])
    if "memory_contains" in expected:
        profile = memory_service.get_user_preferences(user_id)
        checks["memory_contains"] = _profile_contains(profile, expected["memory_contains"])
    if "memory_should_not_contain" in expected:
        profile = memory_service.get_user_preferences(user_id)
        checks["memory_not_polluted"] = all(field not in profile for field in expected["memory_should_not_contain"])
    if expected.get("fallback_expected"):
        checks["fallback"] = result.assistant_message == FALLBACK_MESSAGE and result.intent == "chat"

    for name, passed in checks.items():
        if not passed:
            errors.append(f"check failed: {name}")
    return checks


def compute_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    total_cases = len(case_results)
    passed_cases = sum(1 for result in case_results if result.get("passed"))
    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "pass_rate": _rate(passed_cases, total_cases),
        "json_valid_rate": _check_rate(case_results, {"json_valid"}),
        "field_extraction_accuracy": _check_rate(case_results, FIELD_CHECKS),
        "tool_or_skill_match_rate": _check_rate(case_results, TOOL_CHECKS),
        "memory_update_accuracy": _check_rate(case_results, MEMORY_CHECKS),
        "rag_hit_rate": _check_rate(case_results, {"rag_hit"}),
        "hallucination_guard_pass_rate": _check_rate(case_results, HALLUCINATION_CHECKS),
        "fallback_success_rate": _check_rate(case_results, FALLBACK_CHECKS),
    }


def _check_rate(case_results: list[dict[str, Any]], names: set[str]) -> float:
    values: list[bool] = []
    for result in case_results:
        checks = result.get("checks", {})
        for name, passed in checks.items():
            if name in names:
                values.append(bool(passed))
    return _rate(sum(1 for value in values if value), len(values))


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)


def _default_mock_output(user_message: str) -> str:
    return json.dumps(
        {
            "intent": "chat",
            "assistant_message": f"收到：{user_message}",
            "updated_request": None,
            "updated_plan": None,
            "missing_fields": [],
            "used_tools": [],
        },
        ensure_ascii=False,
    )


def _number_equal(left: Any, right: Any) -> bool:
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return left == right


def _contains_any_tool(used_tools: list[str], expected_tools: list[str]) -> bool:
    normalized_used = {_normalize_tool_name(name) for name in used_tools}
    normalized_expected = {_normalize_tool_name(name) for name in expected_tools}
    return bool(normalized_used & normalized_expected)


def _normalize_tool_name(name: str) -> str:
    return "".join(char for char in name.lower() if char.isalnum())


def _result_text(result: ChatAgentResult) -> str:
    payload = result.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False)


def _profile_has_stable_values(profile: dict[str, Any]) -> bool:
    return any(
        key in profile and profile[key]
        for key in ["interests", "disliked_tags", "pace_preference", "budget_preference", "travel_style"]
    )


def _profile_contains(profile: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        actual = profile.get(key)
        if isinstance(expected_value, list):
            if not isinstance(actual, list):
                return False
            if not all(item in actual for item in expected_value):
                return False
        elif actual != expected_value:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the lightweight travel agent.")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="Path to JSONL eval cases.")
    parser.add_argument("--live", action="store_true", help="Call the real configured LLM instead of mock outputs.")
    parser.add_argument("--result", default=str(DEFAULT_RESULT_PATH), help="Path to write latest eval result JSON.")
    args = parser.parse_args()

    payload = asyncio.run(
        run_evaluation(
            cases_path=args.cases,
            live=args.live,
            result_path=args.result,
        )
    )
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))
    print(f"Saved result to {args.result}")
    return 0 if payload["metrics"]["passed_cases"] == payload["metrics"]["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
