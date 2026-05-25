import json
import asyncio

from scripts.eval_light_agent import (
    compute_metrics,
    load_cases,
    run_evaluation,
)


def test_load_cases_reads_jsonl(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"id":"case_a","turns":[],"expected":{}}\n'
        '{"id":"case_b","turns":[],"expected":{}}\n',
        encoding="utf-8",
    )

    cases = load_cases(cases_path)

    assert [case["id"] for case in cases] == ["case_a", "case_b"]


def test_run_mock_eval_generates_result_json(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    result_path = tmp_path / "latest_eval_result.json"
    memory_path = tmp_path / "eval_memory.json"
    cases_path.write_text(
        json.dumps(
            {
                "id": "case_eval",
                "name": "mock_eval",
                "turns": [
                    {
                        "role": "user",
                        "content": "我想去成都玩三天，两个人，预算3000，喜欢美食",
                    }
                ],
                "mock_outputs": [
                    {
                        "intent": "draft_plan",
                        "assistant_message": "成都三天轻量草案。",
                        "updated_request": {
                            "destination": "成都",
                            "days": 3,
                            "people": 2,
                            "budget": 3000,
                            "interests": ["美食"],
                            "constraints": [],
                        },
                        "updated_plan": {
                            "destination": "成都",
                            "days": 3,
                            "summary": "成都三天轻量草案。",
                            "daily_plan": ["Day 1", "Day 2", "Day 3"],
                            "tips": [],
                        },
                        "missing_fields": [],
                        "used_tools": [],
                    }
                ],
                "expected": {
                    "destination": "成都",
                    "days": 3,
                    "people": 2,
                    "budget": 3000,
                    "interests_contains": ["美食"],
                    "intent_any_of": ["draft_plan"],
                    "tools_contains_any": ["budget_skill"],
                    "plan_should_exist": True,
                    "should_not_contain": ["实时酒店价格"],
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = asyncio.run(
        run_evaluation(
            cases_path=cases_path,
            result_path=result_path,
            memory_path=memory_path,
        )
    )

    assert payload["metrics"]["total_cases"] == 1
    assert payload["metrics"]["passed_cases"] == 1
    assert result_path.exists()
    saved = json.loads(result_path.read_text(encoding="utf-8"))
    assert saved["cases"][0]["passed"] is True


def test_compute_metrics_counts_failures_without_interrupting():
    metrics = compute_metrics(
        [
            {
                "passed": True,
                "checks": {
                    "json_valid": True,
                    "destination": True,
                    "tools": True,
                    "hallucination_guard": True,
                },
            },
            {
                "passed": False,
                "checks": {
                    "json_valid": True,
                    "destination": False,
                    "tools": False,
                    "hallucination_guard": True,
                },
            },
        ]
    )

    assert metrics["total_cases"] == 2
    assert metrics["passed_cases"] == 1
    assert metrics["pass_rate"] == 0.5
    assert metrics["field_extraction_accuracy"] == 0.5
    assert metrics["tool_or_skill_match_rate"] == 0.5
    assert metrics["hallucination_guard_pass_rate"] == 1.0


def test_should_not_contain_check_can_fail_case(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    result_path = tmp_path / "latest_eval_result.json"
    memory_path = tmp_path / "eval_memory.json"
    cases_path.write_text(
        json.dumps(
            {
                "id": "case_guard",
                "name": "guard_failure",
                "turns": [{"role": "user", "content": "给我酒店价格"}],
                "mock_outputs": [
                    {
                        "intent": "chat",
                        "assistant_message": "实时酒店价格为 200 元。",
                        "updated_request": None,
                        "updated_plan": None,
                        "missing_fields": [],
                        "used_tools": [],
                    }
                ],
                "expected": {
                    "intent_any_of": ["chat"],
                    "should_not_contain": ["实时酒店价格"],
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = asyncio.run(
        run_evaluation(
            cases_path=cases_path,
            result_path=result_path,
            memory_path=memory_path,
        )
    )

    assert payload["metrics"]["passed_cases"] == 0
    assert payload["cases"][0]["checks"]["hallucination_guard"] is False
    assert "check failed: hallucination_guard" in payload["cases"][0]["errors"]
