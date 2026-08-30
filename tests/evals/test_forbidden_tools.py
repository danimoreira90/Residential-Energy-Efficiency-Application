"""Regression-eval contracts for forbidden tool calls."""

from __future__ import annotations

from pathlib import Path

from energia.evals.runner import EvalExample, MessageInput, load_eval, score_attempt
from energia.evals.scorers import ExampleResult, ToolCallRecord

_REGRESSION_PATH = Path(__file__).resolve().parents[2] / "evals" / "regression.jsonl"


def test_score_attempt_fails_when_a_forbidden_tool_is_invoked() -> None:
    example = EvalExample(
        name="get-tariff-only",
        input_messages=[MessageInput(role="user", content="Tarifa da Enel Rio")],
        expected_tool="get_tariff",
        forbidden_tools=["current_bandeira"],
    )
    result = ExampleResult(
        tool_calls=[
            ToolCallRecord(name="get_tariff", args={"distributor": "Enel Rio"}),
            ToolCallRecord(name="current_bandeira", args={}),
        ],
        final_message="Resposta.",
    )

    assert score_attempt(result, example) is False


def test_regression_fixture_declares_tools_get_tariff_must_not_invoke() -> None:
    examples = load_eval(_REGRESSION_PATH)
    example = next(
        item for item in examples if item.name == "get_tariff_rejects_tariff_awareness_tools"
    )

    assert example.forbidden_tools == [
        "current_bandeira",
        "bandeira_history",
        "simulate_tarifa_branca",
    ]
