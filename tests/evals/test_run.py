"""Tests for energia.evals.run CLI — exit codes 0 / 1 / 2 (TE-06)."""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from energia.evals.run import main

# ---------------------------------------------------------------------------
# capability sub-command
# ---------------------------------------------------------------------------


def test_capability_exits_0_when_gate_passes() -> None:
    with patch("energia.evals.run._run_capability", return_value=0), patch.object(
        sys, "argv", ["run", "capability", "hello_world"]
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0


def test_capability_exits_1_when_gate_fails() -> None:
    with patch("energia.evals.run._run_capability", return_value=1), patch.object(
        sys, "argv", ["run", "capability", "hello_world"]
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_capability_exits_2_when_skipped() -> None:
    with patch("energia.evals.run._run_capability", return_value=2), patch.object(
        sys, "argv", ["run", "capability", "hello_world"]
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# regression sub-command
# ---------------------------------------------------------------------------


def test_regression_exits_0_when_gate_passes() -> None:
    with patch("energia.evals.run._run_regression", return_value=0), patch.object(
        sys, "argv", ["run", "regression"]
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0


def test_regression_exits_1_when_gate_fails() -> None:
    with patch("energia.evals.run._run_regression", return_value=1), patch.object(
        sys, "argv", ["run", "regression"]
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_regression_exits_2_when_skipped() -> None:
    with patch("energia.evals.run._run_regression", return_value=2), patch.object(
        sys, "argv", ["run", "regression"]
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 2
