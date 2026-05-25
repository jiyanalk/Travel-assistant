from services.agent_observer import AgentObserver, build_trace_payload


def test_agent_observer_writes_trace(tmp_path):
    trace_path = tmp_path / "agent_traces.jsonl"
    observer = AgentObserver(trace_path=trace_path)
    trace = build_trace_payload(
        trace_id="trace-1",
        session_id="session-1",
        user_id="user-1",
        user_message="我想去成都玩三天",
        selected_tools=["simple_budget_tool"],
        tool_outputs={"simple_budget_tool": {"available": True}},
        prompt_text="prompt",
        raw_model_output='{"intent":"chat"}',
        validation_success=True,
        fallback_used=False,
        final_intent="chat",
    )

    observer.record(trace)

    assert trace_path.exists()
    assert "trace-1" in trace_path.read_text(encoding="utf-8")


def test_agent_observer_ignores_write_failure(tmp_path):
    observer = AgentObserver(trace_path=tmp_path)

    observer.record(
        {
            "trace_id": "trace-2",
            "session_id": "session-2",
            "user_message": "hello",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
