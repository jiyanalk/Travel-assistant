import pytest

from services.output_validator import OutputValidationError, validate_chat_agent_result


def test_output_validator_parses_plain_json():
    result = validate_chat_agent_result(
        '{"intent":"chat","assistant_message":"你好","missing_fields":[],"used_tools":[]}'
    )

    assert result.intent == "chat"
    assert result.assistant_message == "你好"


def test_output_validator_parses_fenced_json():
    result = validate_chat_agent_result(
        '```json\n{"intent":"collect_info","assistant_message":"想去哪里？","missing_fields":["destination"],"used_tools":[]}\n```'
    )

    assert result.intent == "collect_info"
    assert result.missing_fields == ["destination"]


def test_output_validator_extracts_json_from_text():
    result = validate_chat_agent_result(
        '好的，结果如下：{"intent":"chat","assistant_message":"收到","missing_fields":[],"used_tools":[]}谢谢'
    )

    assert result.assistant_message == "收到"


def test_output_validator_rejects_invalid_json():
    with pytest.raises(OutputValidationError):
        validate_chat_agent_result("not json")
