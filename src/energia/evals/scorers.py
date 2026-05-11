"""Scoring primitives for capability and regression evals.

Each scorer takes an ExampleResult and a single expected value, returning bool.
All configured scorers for an attempt must pass for the attempt to be scored as passing.

ExampleResult and ToolCallRecord are defined here to avoid circular imports:
runner.py imports from scorers.py; scorers.py does not import from runner.py.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


class ToolCallRecord(BaseModel):
    """A single tool invocation captured during an eval attempt."""

    name: str
    args: dict[str, Any]


class ExampleResult(BaseModel):
    """Output captured from one GRAPH.invoke call during an eval attempt."""

    tool_calls: list[ToolCallRecord]
    final_message: str


def tool_called(result: ExampleResult, expected_tool: str | None) -> bool:
    """True when the expected tool was (or was not) invoked.

    - expected_tool=None  → passes when NO tool was called (use for out-of-scope inputs).
    - expected_tool="foo" → passes when "foo" appears in result.tool_calls.
    """
    if expected_tool is None:
        return len(result.tool_calls) == 0
    return any(tc.name == expected_tool for tc in result.tool_calls)


def input_matches(result: ExampleResult, expected: dict[str, Any]) -> bool:
    """True when any tool call's args are a superset of expected (subset match).

    Checks all calls; passes if at least one satisfies every expected key=value pair.
    """
    for tc in result.tool_calls:
        if all(tc.args.get(k) == v for k, v in expected.items()):
            return True
    return False


def output_matches_pattern(result: ExampleResult, pattern: str) -> bool:
    """True when the final assistant message matches the given regex pattern (DOTALL)."""
    return bool(re.search(pattern, result.final_message, re.DOTALL))
