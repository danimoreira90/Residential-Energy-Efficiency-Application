"""Pure-function tests for energia.evals.scorers. No API calls, no mocking."""
from energia.evals.scorers import (
    ExampleResult,
    ToolCallRecord,
    input_matches,
    output_matches_pattern,
    tool_called,
)


def _result(
    tool_name: str | None = None,
    args: dict[str, object] | None = None,
    message: str = "",
) -> ExampleResult:
    tool_calls = (
        [ToolCallRecord(name=tool_name, args=args or {})] if tool_name is not None else []
    )
    return ExampleResult(tool_calls=tool_calls, final_message=message)


# ---------------------------------------------------------------------------
# tool_called
# ---------------------------------------------------------------------------


def test_tool_called_returns_true_when_match() -> None:
    result = _result("hello_world")
    assert tool_called(result, "hello_world") is True


def test_tool_called_returns_false_when_different_tool() -> None:
    result = _result("hello_world")
    assert tool_called(result, "some_other_tool") is False


def test_tool_called_handles_none_expected() -> None:
    """expected_tool=None passes when NO tool was called, fails when any tool was called."""
    no_calls = _result()
    assert tool_called(no_calls, None) is True

    has_call = _result("hello_world")
    assert tool_called(has_call, None) is False


# ---------------------------------------------------------------------------
# input_matches
# ---------------------------------------------------------------------------


def test_input_matches_subset() -> None:
    result = _result("hello_world", {"name": "Daniel", "extra": "value"})
    assert input_matches(result, {"name": "Daniel"}) is True


def test_input_matches_returns_false_on_value_mismatch() -> None:
    result = _result("hello_world", {"name": "Daniel"})
    assert input_matches(result, {"name": "Maria"}) is False


def test_input_matches_returns_false_on_no_tool_calls() -> None:
    result = _result()
    assert input_matches(result, {"name": "Daniel"}) is False


# ---------------------------------------------------------------------------
# output_matches_pattern
# ---------------------------------------------------------------------------


def test_output_matches_pattern_regex() -> None:
    result = _result(message="Olá, Daniel! Como posso ajudar?")
    assert output_matches_pattern(result, r"Ol[aá].*Daniel") is True


def test_output_matches_pattern_no_match() -> None:
    result = _result(message="Não sei responder isso.")
    assert output_matches_pattern(result, r"Ol[aá].*Daniel") is False
