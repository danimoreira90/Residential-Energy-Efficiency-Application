"""Expected input must belong to the expected tool's call."""

from energia.evals.runner import EvalExample, MessageInput, score_attempt
from energia.evals.scorers import ExampleResult, ToolCallRecord


def test_score_attempt_rejects_expected_args_on_a_different_tool() -> None:
    example = EvalExample(
        name="get-tariff-input-binding",
        input_messages=[MessageInput(role="user", content="Tarifa da Enel Rio")],
        expected_tool="get_tariff",
        expected_input_match={"distributor": "Enel Rio"},
    )
    result = ExampleResult(
        tool_calls=[
            ToolCallRecord(name="get_tariff", args={"distributor": "Light"}),
            ToolCallRecord(name="other_tool", args={"distributor": "Enel Rio"}),
        ],
        final_message="Resposta.",
    )

    assert score_attempt(result, example) is False
