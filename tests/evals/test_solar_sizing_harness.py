"""Deterministic contracts for solar-sizing eval fixtures, not live LLM selection."""
from __future__ import annotations

from pathlib import Path

import pytest

from energia.chat.tools import ALL_TOOLS
from energia.evals import runner
from energia.evals.runner import EvalExample, load_eval
from energia.evals.scorers import ExampleResult, ToolCallRecord

_ROOT = Path(__file__).resolve().parents[2]
_CAPABILITY = _ROOT / "evals" / "capability" / "estimate_solar_system.jsonl"


def _captured(example: EvalExample) -> ExampleResult:
    calls = (
        []
        if example.expected_tool is None
        else [
            ToolCallRecord(
                name=example.expected_tool,
                args=example.expected_input_match or {},
            )
        ]
    )
    return ExampleResult(tool_calls=calls, final_message="Deterministic harness output.")


def test_solar_fixture_contracts_match_registered_tools() -> None:
    examples = load_eval(_CAPABILITY)
    assert [example.name for example in examples] == [
        "solar_request_complete_null_island",
        "solar_request_missing_coordinates",
        "tariff_lookup_enel_rio",
    ]
    assert examples[0].expected_tool == "estimate_solar_system"
    assert examples[0].expected_input_match == {
        "latitude": 0,
        "longitude": 0,
        "monthly_consumption_kwh": 400,
        "roof_orientation": "N",
        "roof_tilt_deg": 15,
    }
    assert examples[1].expected_tool is None
    assert examples[1].forbidden_tools == ["estimate_solar_system"]
    assert examples[2].expected_tool == "get_tariff"
    assert examples[2].expected_input_match == {"distributor": "Enel Rio"}
    assert examples[2].forbidden_tools == ["estimate_solar_system"]

    registered = {tool.name for tool in ALL_TOOLS}
    assert {example.expected_tool for example in examples if example.expected_tool} <= registered


def test_solar_runner_scores_three_captured_attempts_per_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    examples = load_eval(_CAPABILITY)
    attempts = iter(_captured(example) for example in examples for _ in range(3))
    monkeypatch.chdir(_ROOT)
    def no_api_key() -> None:
        return None

    def run_example(_example: EvalExample) -> ExampleResult:
        return next(attempts)

    monkeypatch.setattr(runner, "_check_api_key", no_api_key)
    monkeypatch.setattr(runner, "run_example", run_example)

    report = runner.run_capability("estimate_solar_system", attempts=3)

    assert report.total_examples == 3
    assert report.passing_examples == 3
    assert report.score == 1.0
    assert report.passed is True
    assert all(item.passing_attempts == 3 for item in report.example_reports)
