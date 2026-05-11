"""Eval runner for capability and regression evals (EDD discipline).

pass@3 math — capability
========================
An EXAMPLE passes if passing_attempts >= ceil(attempts / 2).
With attempts=3 the threshold is ceil(3/2) = 2, so an example needs at least
2-of-3 passing attempts to count as passing.

The CAPABILITY passes if (passing_examples / total_examples) >= 0.90.

Example: 5 examples, each attempted 3 times.
  4 examples pass 3/3 → each example passes   (3 >= 2)
  1 example passes 1/3 → that example fails    (1 < 2)
  Aggregate: 4/5 = 0.80 → CAPABILITY FAILS     (0.80 < 0.90)

pass^3 math — regression
========================
A regression example passes ONLY if ALL attempts pass (pass^3 = 1.00 gate).
One failing attempt anywhere → regression FAILS.
This stricter gate ensures previously working behaviour stays stable across
every single run — no non-determinism tolerated in the regression baseline.

Note: there are multiple "pass@k" definitions in the wild.  This file uses
the per-example majority-vote interpretation (>= ceil(k/2) passing attempts),
NOT the "at least one pass in k tries" definition used in some ML papers.
"""
from __future__ import annotations

import json
from math import ceil
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from energia.config import settings
from energia.evals.scorers import (
    ExampleResult,
    ToolCallRecord,
    input_matches,
    output_matches_pattern,
    tool_called,
)

__all__ = [
    "EvalSkipped",
    "MessageInput",
    "EvalExample",
    "ExampleReport",
    "CapabilityReport",
    "RegressionReport",
    "ExampleResult",
    "ToolCallRecord",
    "load_eval",
    "run_example",
    "score_attempt",
    "run_capability",
    "run_regression",
]


class EvalSkipped(Exception):
    """Raised when ANTHROPIC_API_KEY is not set; the eval cannot run."""


class MessageInput(BaseModel):
    role: str
    content: str


class EvalExample(BaseModel):
    name: str
    input_messages: list[MessageInput]
    expected_tool: str | None = None
    expected_input_match: dict[str, Any] | None = None
    expected_output_pattern: str | None = None


class ExampleReport(BaseModel):
    name: str
    passed: bool
    passing_attempts: int
    total_attempts: int


class CapabilityReport(BaseModel):
    capability_name: str
    total_examples: int
    passing_examples: int
    score: float
    passed: bool
    example_reports: list[ExampleReport]


class RegressionReport(BaseModel):
    total_examples: int
    all_passed: bool
    example_reports: list[ExampleReport]


def load_eval(path: Path) -> list[EvalExample]:
    """Load and parse a JSONL eval file.

    Lines starting with '#' are treated as comments and skipped.
    Empty lines are skipped.
    Raises ValueError on malformed JSON or Pydantic schema violations.
    """
    examples: list[EvalExample] = []
    with path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed JSON on line {lineno} of {path}: {exc}"
                ) from exc
            try:
                examples.append(EvalExample.model_validate(data))
            except ValidationError as exc:
                raise ValueError(
                    f"Schema error on line {lineno} of {path}: {exc}"
                ) from exc
    return examples


def _check_api_key() -> None:
    """Raise EvalSkipped when ANTHROPIC_API_KEY is absent.

    Called at the top of run_capability and run_regression so that missing
    credentials produce a clean, informative skip rather than a cryptic
    authentication error deep in LangGraph.
    """
    if not settings.anthropic_api_key:
        raise EvalSkipped(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or environment before running evals. "
            "Exiting with code 2 (skipped — not a test failure)."
        )


def run_example(example: EvalExample) -> ExampleResult:
    """Invoke the compiled GRAPH with the example's input messages.

    Captures which tools were called and the text of the final assistant message.
    Caller is responsible for verifying ANTHROPIC_API_KEY before calling this
    (see _check_api_key / run_capability / run_regression).
    """
    from energia.chat.graph import GRAPH  # lazy import — patched in tests

    messages = [
        HumanMessage(content=msg.content)
        for msg in example.input_messages
        if msg.role == "user"
    ]
    state: Any = GRAPH.invoke(
        {
            "messages": messages,
            "user_id": "eval-runner",
            "conversation_id": f"eval-{example.name}",
            "tokens_used": 0,
        }
    )

    tool_calls: list[ToolCallRecord] = []
    for msg in state["messages"]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    ToolCallRecord(
                        name=str(tc["name"]),  # type: ignore[index]
                        args=dict(tc["args"]),  # type: ignore[index]
                    )
                )

    final_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content:
            final_message = msg.content
            break

    return ExampleResult(tool_calls=tool_calls, final_message=final_message)


def score_attempt(result: ExampleResult, example: EvalExample) -> bool:
    """Apply all configured scorers; True only when every scorer passes.

    Scorers are applied in order: tool_called → input_matches → output_matches_pattern.
    The first failure short-circuits.
    """
    if not tool_called(result, example.expected_tool):
        return False
    if example.expected_input_match is not None:
        if not input_matches(result, example.expected_input_match):
            return False
    if example.expected_output_pattern is not None:
        if not output_matches_pattern(result, example.expected_output_pattern):
            return False
    return True


def run_capability(name: str, attempts: int = 3) -> CapabilityReport:
    """Run a named capability eval suite with pass@attempts gate.

    An example passes if passing_attempts >= ceil(attempts / 2).
    The capability passes if (passing_examples / total_examples) >= 0.90.
    """
    _check_api_key()

    eval_path = Path("evals") / "capability" / f"{name}.jsonl"
    examples = load_eval(eval_path)

    threshold = ceil(attempts / 2)
    example_reports: list[ExampleReport] = []

    for example in examples:
        passing = sum(
            1 for _ in range(attempts) if score_attempt(run_example(example), example)
        )
        example_reports.append(
            ExampleReport(
                name=example.name,
                passed=passing >= threshold,
                passing_attempts=passing,
                total_attempts=attempts,
            )
        )

    passing_examples = sum(1 for r in example_reports if r.passed)
    score = passing_examples / len(examples) if examples else 0.0

    return CapabilityReport(
        capability_name=name,
        total_examples=len(examples),
        passing_examples=passing_examples,
        score=score,
        passed=score >= 0.90,
        example_reports=example_reports,
    )


def run_regression(attempts: int = 3) -> RegressionReport:
    """Run the regression eval suite with pass^attempts gate.

    Every example must pass ALL attempts (pass^3 = 1.00).
    One failing attempt anywhere causes the regression to fail.
    """
    _check_api_key()

    eval_path = Path("evals") / "regression.jsonl"
    examples = load_eval(eval_path)

    if not examples:
        return RegressionReport(
            total_examples=0,
            all_passed=True,
            example_reports=[],
        )

    example_reports: list[ExampleReport] = []

    for example in examples:
        passing = sum(
            1 for _ in range(attempts) if score_attempt(run_example(example), example)
        )
        example_reports.append(
            ExampleReport(
                name=example.name,
                passed=passing == attempts,  # must pass ALL attempts
                passing_attempts=passing,
                total_attempts=attempts,
            )
        )

    return RegressionReport(
        total_examples=len(examples),
        all_passed=all(r.passed for r in example_reports),
        example_reports=example_reports,
    )
