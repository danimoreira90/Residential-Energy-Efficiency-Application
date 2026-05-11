"""Tests for energia.evals.runner — GRAPH is mocked, no real Anthropic API calls."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from energia.evals.runner import (
    EvalExample,
    EvalSkipped,
    MessageInput,
    load_eval,
    run_capability,
    run_example,
    run_regression,
    score_attempt,
)
from energia.evals.scorers import ExampleResult, ToolCallRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph_state(
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    final_content: str = "Resposta do assistente.",
) -> dict[str, Any]:
    """Build a minimal ChatState-like dict for mocking GRAPH.invoke return values."""
    messages: list[Any] = [HumanMessage(content="input")]
    if tool_name is not None:
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": tool_name,
                    "args": tool_args or {},
                    "id": "tc-001",
                    "type": "tool_call",
                }
            ],
        )
        messages.append(ai_with_tool)
        messages.append(ToolMessage(content='{"result": "ok"}', tool_call_id="tc-001"))
    messages.append(AIMessage(content=final_content))
    return {
        "messages": messages,
        "user_id": "eval-runner",
        "conversation_id": "eval-test",
        "tokens_used": 10,
    }


def _passing_result(tool_name: str = "hello_world") -> ExampleResult:
    return ExampleResult(
        tool_calls=[ToolCallRecord(name=tool_name, args={})],
        final_message="Olá!",
    )


def _failing_result() -> ExampleResult:
    return ExampleResult(tool_calls=[], final_message="Não sei.")


def _simple_examples(n: int, expected_tool: str = "hello_world") -> list[EvalExample]:
    return [
        EvalExample(
            name=f"ex{i}",
            input_messages=[MessageInput(role="user", content=f"test {i}")],
            expected_tool=expected_tool,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# load_eval
# ---------------------------------------------------------------------------


def test_load_eval_parses_jsonl(tmp_path: Path) -> None:
    content = (
        '{"name": "t1", "input_messages": [{"role": "user", "content": "hello"}],'
        ' "expected_tool": "hello_world"}\n'
        "# this is a comment — should be ignored\n"
        "\n"
        '{"name": "t2", "input_messages": [{"role": "user", "content": "bye"}],'
        ' "expected_tool": null}\n'
    )
    eval_file = tmp_path / "test.jsonl"
    eval_file.write_text(content, encoding="utf-8")

    examples = load_eval(eval_file)

    assert len(examples) == 2
    assert examples[0].name == "t1"
    assert examples[0].expected_tool == "hello_world"
    assert examples[1].name == "t2"
    assert examples[1].expected_tool is None


def test_load_eval_rejects_malformed_line(tmp_path: Path) -> None:
    eval_file = tmp_path / "bad.jsonl"
    eval_file.write_text("not valid json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed JSON"):
        load_eval(eval_file)


# ---------------------------------------------------------------------------
# run_example
# ---------------------------------------------------------------------------


def test_run_example_captures_tool_calls(mocker: Any) -> None:
    state = _make_graph_state("hello_world", {"name": "Test"}, "Olá, Test!")
    mock_graph = mocker.patch("energia.chat.graph.GRAPH")
    mock_graph.invoke.return_value = state

    example = EvalExample(
        name="test",
        input_messages=[MessageInput(role="user", content="Oi")],
    )
    result = run_example(example)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "hello_world"
    assert result.tool_calls[0].args == {"name": "Test"}
    assert result.final_message == "Olá, Test!"
    mock_graph.invoke.assert_called_once()


# ---------------------------------------------------------------------------
# score_attempt
# ---------------------------------------------------------------------------


def test_score_attempt_combines_scorers() -> None:
    example = EvalExample(
        name="test",
        input_messages=[MessageInput(role="user", content="test")],
        expected_tool="hello_world",
        expected_input_match={"name": "Daniel"},
        expected_output_pattern=r"Ol[aá].*Daniel",
    )

    good = ExampleResult(
        tool_calls=[ToolCallRecord(name="hello_world", args={"name": "Daniel"})],
        final_message="Olá, Daniel!",
    )
    assert score_attempt(good, example) is True

    wrong_tool = ExampleResult(
        tool_calls=[ToolCallRecord(name="other_tool", args={"name": "Daniel"})],
        final_message="Olá, Daniel!",
    )
    assert score_attempt(wrong_tool, example) is False

    wrong_input = ExampleResult(
        tool_calls=[ToolCallRecord(name="hello_world", args={"name": "Maria"})],
        final_message="Olá, Daniel!",
    )
    assert score_attempt(wrong_input, example) is False

    wrong_output = ExampleResult(
        tool_calls=[ToolCallRecord(name="hello_world", args={"name": "Daniel"})],
        final_message="Oi!",
    )
    assert score_attempt(wrong_output, example) is False


# ---------------------------------------------------------------------------
# run_capability
# ---------------------------------------------------------------------------


def test_run_capability_computes_pass_at_3_correctly(mocker: Any) -> None:
    """4/5 examples pass → score=0.80 → below the 0.90 gate → passed=False.

    Example pass rule: >= ceil(3/2) = 2 passing attempts.
    - examples 0–3: 3/3 attempts pass → each example passes
    - example 4:    1/3 attempts pass → example fails
    """
    examples = _simple_examples(5)
    mocker.patch("energia.evals.runner.load_eval", return_value=examples)
    mocker.patch("energia.evals.runner._check_api_key")

    # 4 examples × 3 attempts = 12 calls (all pass), then 3 calls for ex4 (1 pass, 2 fail)
    side_effects = [_passing_result()] * 12 + [
        _passing_result(),
        _failing_result(),
        _failing_result(),
    ]
    mocker.patch("energia.evals.runner.run_example", side_effect=side_effects)

    report = run_capability("hello_world")

    assert report.total_examples == 5
    assert report.passing_examples == 4
    assert abs(report.score - 0.80) < 0.01
    assert report.passed is False  # 0.80 < 0.90 gate


# ---------------------------------------------------------------------------
# run_regression
# ---------------------------------------------------------------------------


def test_run_regression_requires_pass_cubed(mocker: Any) -> None:
    """One failing attempt in any example causes all_passed=False (pass^3 gate)."""
    examples = _simple_examples(3)
    mocker.patch("energia.evals.runner.load_eval", return_value=examples)
    mocker.patch("energia.evals.runner._check_api_key")

    # examples 0, 1: all 3 attempts pass  (6 calls)
    # example 2:     2/3 pass — fails once (3 calls: pass, pass, FAIL)
    side_effects = [_passing_result()] * 6 + [
        _passing_result(),
        _passing_result(),
        _failing_result(),
    ]
    mocker.patch("energia.evals.runner.run_example", side_effect=side_effects)

    report = run_regression()

    assert report.total_examples == 3
    assert report.all_passed is False
    # example 2 must be the failing one
    assert report.example_reports[2].passed is False
    assert report.example_reports[2].passing_attempts == 2


# ---------------------------------------------------------------------------
# API-key guard
# ---------------------------------------------------------------------------


def test_runner_skips_cleanly_without_api_key(mocker: Any) -> None:
    """run_capability and run_regression raise EvalSkipped when API key is absent."""
    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = ""
    mocker.patch("energia.evals.runner.settings", mock_settings)

    with pytest.raises(EvalSkipped, match="ANTHROPIC_API_KEY"):
        run_capability("hello_world")

    with pytest.raises(EvalSkipped, match="ANTHROPIC_API_KEY"):
        run_regression()
