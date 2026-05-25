# Light Agent Eval Harness

This folder contains repeatable evaluation cases for the lightweight travel assistant.

## Purpose

The eval harness checks whether the agent can keep stable lightweight behavior across:

- JSON output validation
- structured trip request extraction
- multi-turn request merge
- missing-field clarification
- plan revision behavior
- hallucination guardrails for prices, tickets, business hours, and availability
- tool / skill activation
- preference memory updates
- local lightweight RAG hits
- fallback behavior

## Run Mock Eval

Mock mode is the default and does not call the real LLM:

```powershell
.\.venv\Scripts\python.exe scripts\eval_light_agent.py --cases evals\light_agent_cases.jsonl
```

## Run Live Eval

Live mode calls the configured model and must be explicitly enabled:

```powershell
.\.venv\Scripts\python.exe scripts\eval_light_agent.py --cases evals\light_agent_cases.jsonl --live
```

## Results

The latest result is written to:

```text
evals/results/latest_eval_result.json
```

## Add a Case

Add one JSON object per line to `light_agent_cases.jsonl`.

For mock mode, include `mock_outputs` with one output per user turn. Use a JSON object for normal model output or a string such as `not json` to test fallback.
