"""Deterministic runner-contract checks for Sprint 2 tariff-awareness fixtures.

These tests score captured tool-call records. They do not evaluate LLM tool selection.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from energia.chat.tools import ALL_TOOLS
from energia.evals.runner import EvalExample, load_eval, run_capability, run_regression
from energia.evals.scorers import ExampleResult, ToolCallRecord

_ROOT = Path(__file__).resolve().parents[2]
_CAPABILITY_PATH = _ROOT / "evals" / "capability" / "tariff_awareness.jsonl"
_REGRESSION_PATH = _ROOT / "evals" / "regression.jsonl"


def _captured_result_for(example: EvalExample) -> ExampleResult:
    """Build an allowed captured tool-call record for one JSONL contract."""
    return ExampleResult(
        tool_calls=[
            ToolCallRecord(
                name=example.expected_tool or "",
                args=example.expected_input_match or {},
            )
        ],
        final_message="Resposta determinística do harness.",
    )


def _three_attempts(examples: Iterable[EvalExample]) -> list[ExampleResult]:
    return [_captured_result_for(example) for example in examples for _ in range(3)]


def test_tariff_awareness_capability_fixture_contracts_match_registered_tools_and_inputs() -> None:
    examples = load_eval(_CAPABILITY_PATH)

    assert [example.name for example in examples] == [
        "current_bandeira",
        "bandeira_history",
        "simulate_tarifa_branca",
    ]
    assert [example.expected_tool for example in examples] == [
        "current_bandeira",
        "bandeira_history",
        "simulate_tarifa_branca",
    ]
    assert examples[1].expected_input_match == {"months": 12}
    assert examples[2].expected_input_match == {
        "distributor": "Enel Rio",
        "ponta_kwh": 30,
        "intermediaria_kwh": 20,
        "fora_ponta_kwh": 250,
    }

    names = {tool.name for tool in ALL_TOOLS}
    assert {example.expected_tool for example in examples} <= names


def test_tariff_awareness_runner_scores_captured_records_against_both_gates(
    mocker: Any, monkeypatch: Any
) -> None:
    """The runner scores deterministic records; live LLM selection is a separate gate."""
    monkeypatch.chdir(_ROOT)
    capability_examples = load_eval(_CAPABILITY_PATH)
    regression_examples = load_eval(_REGRESSION_PATH)

    assert len(regression_examples) == 2
    assert regression_examples[0].name == "get_tariff_stays_a_pure_lookup"
    assert regression_examples[0].expected_tool == "get_tariff"
    assert regression_examples[0].expected_input_match == {"distributor": "Enel Rio"}
    assert regression_examples[1].name == "get_tariff_rejects_tariff_awareness_tools"
    assert regression_examples[1].forbidden_tools == [
        "current_bandeira",
        "bandeira_history",
        "simulate_tarifa_branca",
    ]

    mocker.patch("energia.evals.runner._check_api_key")
    mocker.patch(
        "energia.evals.runner.run_example",
        side_effect=_three_attempts(capability_examples),
    )
    capability = run_capability("tariff_awareness", attempts=3)

    assert capability.total_examples == 3
    assert capability.passing_examples == 3
    assert capability.score == 1.0
    assert capability.passed is True

    mocker.patch(
        "energia.evals.runner.run_example",
        side_effect=_three_attempts(regression_examples),
    )
    regression = run_regression(attempts=3)

    assert regression.total_examples == 2
    assert regression.all_passed is True
    assert regression.example_reports[0].passing_attempts == 3
