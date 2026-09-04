"""Deterministic contracts for the three solar-payback capability fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from energia.chat.tools import ALL_TOOLS
from energia.evals import runner
from energia.evals.runner import EvalExample, load_eval
from energia.evals.scorers import ExampleResult, ToolCallRecord

_ROOT = Path(__file__).resolve().parents[2]
_CAPABILITY = _ROOT / "evals" / "capability" / "solar_payback.jsonl"


def _captured(example: EvalExample) -> ExampleResult:
    calls = (
        []
        if example.expected_tool is None
        else [ToolCallRecord(name=example.expected_tool, args=example.expected_input_match or {})]
    )
    return ExampleResult(tool_calls=calls, final_message="Deterministic harness output.")


def test_fixture_has_three_bounded_tool_selection_contracts() -> None:
    examples = load_eval(_CAPABILITY)
    assert [example.name for example in examples] == [
        "solar_payback_complete_grounded",
        "solar_payback_missing_grounded_inputs",
        "solar_sizing_only_keeps_existing_tool",
    ]
    assert examples[0].expected_tool == "solar_payback"
    assert set(examples[0].expected_input_match or {}) == {
        "monthly_consumption_kwh",
        "monthly_generation_kwh",
        "system_cost_brl",
        "distributor",
        "connection_year",
        "connection_type",
        "real_tariff_inflation_rate",
        "annual_generation_degradation_rate",
    }
    assert examples[1].expected_tool is None
    assert examples[1].forbidden_tools == ["solar_payback"]
    assert examples[2].expected_tool == "estimate_solar_system"
    assert examples[2].forbidden_tools == ["solar_payback"]
    registered = {tool.name for tool in ALL_TOOLS}
    assert {example.expected_tool for example in examples if example.expected_tool} <= registered


def test_runner_scores_three_captured_attempts_per_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    examples = load_eval(_CAPABILITY)
    attempts = iter(_captured(example) for example in examples for _ in range(3))

    def fake_run_example(_example: EvalExample) -> ExampleResult:
        return next(attempts)

    monkeypatch.chdir(_ROOT)
    monkeypatch.setattr(runner, "_check_api_key", lambda: None)
    monkeypatch.setattr(runner, "run_example", fake_run_example)

    report = runner.run_capability("solar_payback", attempts=3)

    assert report.total_examples == 3
    assert report.passing_examples == 3
    assert report.score == 1.0
    assert report.passed is True
    assert all(item.passing_attempts == 3 for item in report.example_reports)
