"""CLI entrypoint for the energia eval runner.

Usage
-----
    python -m energia.evals.run capability <name>
    python -m energia.evals.run regression
    python -m energia.evals.run parser <labels_path> <bills_dir>

Exit codes
----------
    0  Capability/regression gate passed (>= 0.90 / = 1.00) OR parser eval ran cleanly.
    1  Capability/regression gate failed.
    2  Skipped: ANTHROPIC_API_KEY not set (capability/regression), or
       labels file is empty / missing (parser eval).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _run_capability(name: str) -> int:
    from energia.evals.runner import EvalSkipped, run_capability

    try:
        report = run_capability(name)
    except EvalSkipped as exc:
        print(f"SKIPPED: {exc}")
        return 2

    total_calls = report.total_examples * 3
    print(f"Running {report.total_examples} examples × 3 attempts = {total_calls} calls")
    print(
        f"Capability pass@3: {report.score:.2f}"
        f" ({report.passing_examples}/{report.total_examples})"
    )
    for ex in report.example_reports:
        status = "OK  " if ex.passed else "FAIL"
        print(f"  [{status}] {ex.name} ({ex.passing_attempts}/{ex.total_attempts} attempts passed)")

    if report.passed:
        print(f"PASS — capability '{name}' meets the >= 0.90 gate.")
        return 0
    else:
        print(
            f"FAIL — capability '{name}' score {report.score:.2f}"
            " is below the 0.90 gate."
        )
        return 1


def _run_regression() -> int:
    from energia.evals.runner import EvalSkipped, run_regression

    try:
        report = run_regression()
    except EvalSkipped as exc:
        print(f"SKIPPED: {exc}")
        return 2

    if report.total_examples == 0:
        print("No regression examples yet — skipping.")
        return 0

    print(f"Running {report.total_examples} regression examples × 3 attempts each")
    for ex in report.example_reports:
        status = "OK  " if ex.passed else "FAIL"
        print(f"  [{status}] {ex.name} ({ex.passing_attempts}/{ex.total_attempts} attempts)")

    if report.all_passed:
        print("PASS — regression pass^3 = 1.00.")
        return 0
    else:
        print("FAIL — regression gate requires every example to pass all 3 attempts.")
        return 1


def _run_parser(labels_path: Path, bills_dir: Path) -> int:
    from energia.evals.parser_reliability import (
        format_report,
        run_parser_reliability,
    )

    if not labels_path.exists() or labels_path.stat().st_size == 0:
        print(f"SKIPPED: labels file is empty or missing: {labels_path}")
        return 2

    report = run_parser_reliability(labels_path=labels_path, bills_dir=bills_dir)

    if not report.comparisons:
        print(f"SKIPPED: no labels found in {labels_path}")
        return 2

    print(format_report(report))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m energia.evals.run",
        description="Energia eval runner — capability, regression, and parser-reliability.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    cap_parser = subparsers.add_parser("capability", help="Run a capability eval suite.")
    cap_parser.add_argument(
        "name",
        help="Capability name — matches evals/capability/<name>.jsonl",
    )

    subparsers.add_parser("regression", help="Run the regression eval suite.")

    parser_eval = subparsers.add_parser(
        "parser",
        help="Run the parser-reliability eval (parse_bill_image vs hand-written labels).",
    )
    parser_eval.add_argument(
        "labels_path",
        type=Path,
        help="Path to the labels JSONL file (typically evals/parser_reliability/labels.jsonl).",
    )
    parser_eval.add_argument(
        "bills_dir",
        type=Path,
        help="Directory containing the bill images referenced by labels.image.",
    )

    args = parser.parse_args()

    if args.command == "capability":
        code = _run_capability(args.name)
    elif args.command == "parser":
        code = _run_parser(args.labels_path, args.bills_dir)
    else:
        code = _run_regression()

    sys.exit(code)


if __name__ == "__main__":
    main()
