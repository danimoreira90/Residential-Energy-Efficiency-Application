"""Parser-reliability eval harness — unit tests (RED first).

The harness measures how accurately `parse_bill_image` reads real bills by
comparing its structured Bill output against hand-written ground-truth labels.
This file unit-tests the harness only:

- Loader: BillLabel schema + JSONL loader (comments / blanks / bad period).
- Scorer: MATCH / MISS / MISREAD / INVENTION + PARSE_FAILED, including the
  Decimal normalization for kWh/BRL and the leading-zero normalization for
  installation_number.
- Redaction (HR-6): installation_number's VALUE never appears in the in-memory
  FieldComparison record OR in the formatted console report — only the verdict.
  Normalization runs in-flight and never leaks the UC.
- End-to-end pipeline (the wiring test): parse_bill_image is MOCKED so no real
  vision API call happens; a temp labels file points at a temp PNG; the
  aggregate report counts match.

All data in this file is FABRICATED. No real bill values, no real CPF, no real
UC, no real period from any real bill. The harness never invents — it only
compares (HR-5). The harness never persists or logs PII (HR-6).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from energia.bill.parser import BillParseError
from energia.evals.parser_reliability import (
    BillComparison,
    BillLabel,
    FieldComparison,
    FieldVerdict,
    ParserReliabilityReport,
    format_report,
    load_labels,
    run_parser_reliability,
    score_bill,
)
from energia.models import Bill, BillComposition

# ---------------------------------------------------------------------------
# Helpers (fabricated values only — no PII, no real bills)
# ---------------------------------------------------------------------------


_FAKE_UC = "000000"  # deliberately not a real UC; tests must never print this
_FAKE_DISTRIBUTOR = "Fakedist"
_FAKE_PERIOD = "1999-01"


def _make_bill(
    *,
    distributor: str = _FAKE_DISTRIBUTOR,
    installation_number: str = _FAKE_UC,
    period: str = _FAKE_PERIOD,
    consumption_kwh: str = "374",
    total_brl: str = "416.94",
    composition: BillComposition | None = None,
) -> Bill:
    return Bill(
        distributor=distributor,
        installation_number=installation_number,
        period=period,
        issue_date=date(1999, 1, 1),
        due_date=date(1999, 1, 15),
        consumption_kwh=Decimal(consumption_kwh),
        tariff_group="B1",
        modalidade="Convencional",
        bandeira="Verde",
        total_brl=Decimal(total_brl),
        composition=composition,
        confidence=0.95,
    )


def _make_label(
    *,
    image: str = "fake_bill.png",
    distributor: str | None = _FAKE_DISTRIBUTOR,
    installation_number: str | None = _FAKE_UC,
    period: str | None = _FAKE_PERIOD,
    consumption_kwh: str | None = "374",
    total_brl: str | None = "416.94",
) -> BillLabel:
    return BillLabel(
        image=image,
        distributor=distributor,
        installation_number=installation_number,
        period=period,
        consumption_kwh=consumption_kwh,
        total_brl=total_brl,
    )


def _verdict_for(report: BillComparison, field_name: str) -> FieldVerdict:
    for f in report.fields:
        if f.name == field_name:
            return f.verdict
    raise AssertionError(f"field {field_name!r} not in comparison")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_load_labels_round_trips_two_fake_rows(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        '{"image":"a.png","distributor":"Fakedist","installation_number":"000000",'
        '"period":"1999-01","consumption_kwh":"100","total_brl":"100.00"}\n'
        '{"image":"b.png","distributor":"Testco","installation_number":"999999",'
        '"period":"2099-12","consumption_kwh":null,"total_brl":null}\n',
        encoding="utf-8",
    )

    labels = load_labels(labels_path)

    assert len(labels) == 2
    assert labels[0].image == "a.png"
    assert labels[0].distributor == "Fakedist"
    assert labels[1].consumption_kwh is None
    assert labels[1].total_brl is None


def test_load_labels_ignores_legacy_composition_key(tmp_path: Path) -> None:
    """Old labels.jsonl files with a 'composition' key still load — Pydantic v2's
    default extra='ignore' drops unknown fields silently. Daniel does not have
    to re-edit his labels file after the field was removed in TD-016."""
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        '{"image":"a.png","distributor":"Fakedist","installation_number":"000000",'
        '"period":"1999-01","consumption_kwh":"100","total_brl":"100.00",'
        '"composition":"present"}\n',
        encoding="utf-8",
    )

    labels = load_labels(labels_path)

    assert len(labels) == 1
    assert labels[0].image == "a.png"
    assert not hasattr(labels[0], "composition")


def test_load_labels_rejects_bad_period_format(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        '{"image":"a.png","distributor":"Fakedist","installation_number":"000000",'
        '"period":"1999-13","consumption_kwh":"100","total_brl":"100.00"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_labels(labels_path)


def test_load_labels_skips_comments_and_empty_lines(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        "# header comment\n"
        "\n"
        '{"image":"a.png","distributor":"Fakedist","installation_number":"000000",'
        '"period":"1999-01","consumption_kwh":"100","total_brl":"100.00"}\n'
        "\n"
        "# trailing comment\n",
        encoding="utf-8",
    )

    labels = load_labels(labels_path)

    assert len(labels) == 1
    assert labels[0].image == "a.png"


# ---------------------------------------------------------------------------
# Scorer — MATCH
# ---------------------------------------------------------------------------


def test_score_match_when_all_fields_equal() -> None:
    bill = _make_bill()
    label = _make_label()

    cmp = score_bill(bill=bill, label=label)

    assert cmp.parse_failed is False
    for f in cmp.fields:
        assert f.verdict == FieldVerdict.MATCH, (
            f"expected MATCH on {f.name}, got {f.verdict.value}"
        )


def test_score_match_decimal_normalizes_trailing_zeros() -> None:
    """consumption_kwh label '374' must match bill Decimal('374.00')."""
    bill = _make_bill(consumption_kwh="374.00", total_brl="416.940")
    label = _make_label(consumption_kwh="374", total_brl="416.94")

    cmp = score_bill(bill=bill, label=label)

    assert _verdict_for(cmp, "consumption_kwh") == FieldVerdict.MATCH
    assert _verdict_for(cmp, "total_brl") == FieldVerdict.MATCH


# ---------------------------------------------------------------------------
# Scorer — MISREAD / MISS / INVENTION
# ---------------------------------------------------------------------------


def test_score_misread_when_value_differs() -> None:
    """label distributor 'Fakedist', bill 'Otherdist' -> MISREAD."""
    bill = _make_bill(distributor="Otherdist")
    label = _make_label(distributor="Fakedist")

    cmp = score_bill(bill=bill, label=label)

    assert _verdict_for(cmp, "distributor") == FieldVerdict.MISREAD


def test_score_miss_when_label_present_and_parse_failed() -> None:
    """parse_bill_image raised -> every labeled field counts as MISS."""
    label = _make_label()

    cmp = score_bill(bill=None, label=label)

    assert cmp.parse_failed is True
    for f in cmp.fields:
        assert f.verdict == FieldVerdict.MISS, (
            f"expected MISS on {f.name} after parse_failed, got {f.verdict.value}"
        )


def test_score_invention_when_label_null_and_bill_has_value() -> None:
    """label total_brl is null (illegible); bill produced a value -> INVENTION."""
    bill = _make_bill(total_brl="100")
    label = _make_label(total_brl=None)

    cmp = score_bill(bill=bill, label=label)

    assert _verdict_for(cmp, "total_brl") == FieldVerdict.INVENTION


# ---------------------------------------------------------------------------
# Redaction (HR-6)
# ---------------------------------------------------------------------------


def test_field_comparison_for_installation_number_carries_no_raw_values() -> None:
    """The in-memory record for installation_number stores verdict only.

    The expected/parsed slots must be None to prevent accidental leakage when
    a report is pickled, logged, or serialized. Verdict is sufficient signal.
    """
    bill = _make_bill(installation_number="UNIQUE_UC_VALUE_1234")
    label = _make_label(installation_number="UNIQUE_UC_VALUE_1234")

    cmp = score_bill(bill=bill, label=label)

    uc_record: FieldComparison | None = next(
        (f for f in cmp.fields if f.name == "installation_number"), None
    )
    assert uc_record is not None
    assert uc_record.verdict == FieldVerdict.MATCH
    assert uc_record.expected is None, (
        "expected slot must stay None for installation_number — HR-6 redaction"
    )
    assert uc_record.parsed is None, (
        "parsed slot must stay None for installation_number — HR-6 redaction"
    )


def test_format_report_never_emits_installation_number_value() -> None:
    """The formatted console report must redact the UC value across all verdicts.

    Run two bills: one MATCH, one MISREAD on installation_number. Neither raw
    value appears in the formatted output.
    """
    uc_a = "REAL_UC_AAA_999_777"
    uc_b = "REAL_UC_BBB_111_222"

    bill_a = _make_bill(installation_number=uc_a)
    label_a = _make_label(image="a.png", installation_number=uc_a)

    bill_b = _make_bill(installation_number=uc_b)
    label_b = _make_label(image="b.png", installation_number="EXPECTED_UC_CCC")

    report = ParserReliabilityReport(
        comparisons=[
            score_bill(bill=bill_a, label=label_a),
            score_bill(bill=bill_b, label=label_b),
        ]
    )

    out = format_report(report)
    assert uc_a not in out, "MATCH path leaked the parsed UC value"
    assert uc_b not in out, "MISREAD path leaked the parsed UC value"
    assert "EXPECTED_UC_CCC" not in out, "MISREAD path leaked the expected UC"
    assert "[redacted" in out, "redaction marker must be visible in output"


def test_score_installation_number_normalizes_leading_zeros() -> None:
    """Bills render the UC with different zero-padding widths (e.g. 0006354013
    vs 000006354013) — same identifier. The scorer normalizes leading zeros on
    both sides before comparison, so the verdict is MATCH.

    Redaction continuity (HR-6) is pinned in the same test: even after
    normalization, the FieldComparison record carries no raw UC and the
    formatted report contains neither raw string.
    """
    parsed_uc = "0006354013"
    expected_uc = "000006354013"
    bill = _make_bill(installation_number=parsed_uc)
    label = _make_label(installation_number=expected_uc)

    cmp = score_bill(bill=bill, label=label)

    uc_record: FieldComparison | None = next(
        (f for f in cmp.fields if f.name == "installation_number"), None
    )
    assert uc_record is not None
    assert uc_record.verdict == FieldVerdict.MATCH, (
        "UC values that differ only in leading-zero padding must MATCH; "
        f"got verdict={uc_record.verdict.value}"
    )
    assert uc_record.expected is None, (
        "normalization must not leak the expected UC into the record (HR-6)"
    )
    assert uc_record.parsed is None, (
        "normalization must not leak the parsed UC into the record (HR-6)"
    )

    report = ParserReliabilityReport(comparisons=[cmp])
    out = format_report(report)
    assert parsed_uc not in out, "normalized MATCH path leaked the parsed UC value"
    assert expected_uc not in out, "normalized MATCH path leaked the expected UC value"


# ---------------------------------------------------------------------------
# Full pipeline — parse_bill_image MOCKED, no real vision call
# ---------------------------------------------------------------------------


def test_run_parser_reliability_with_mocked_parse_bill_image(
    tmp_path: Path, mocker: Any
) -> None:
    """End-to-end wiring with no real API call.

    Writes a temp labels.jsonl pointing at a temp PNG; mocks parse_bill_image
    to return a known Bill; asserts the report aggregates verdicts correctly
    and the parse was invoked once with the file bytes + correct media_type.
    """
    bills_dir = tmp_path / "bills"
    bills_dir.mkdir()
    bill_path = bills_dir / "fake_bill.png"
    bill_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        '{"image":"fake_bill.png","distributor":"Fakedist",'
        '"installation_number":"000000","period":"1999-01",'
        '"consumption_kwh":"374","total_brl":"100"}\n',
        encoding="utf-8",
    )

    expected_bill = _make_bill(
        distributor="Fakedist",
        installation_number="000000",
        period="1999-01",
        consumption_kwh="374",
        total_brl="100",
    )

    from energia.models import ParseResult

    mock_parse = mocker.patch(
        "energia.evals.parser_reliability.parse_bill_image",
        return_value=ParseResult(bill=expected_bill, needs_user_confirmation=False),
    )

    report = run_parser_reliability(labels_path=labels_path, bills_dir=bills_dir)

    mock_parse.assert_called_once_with(b"\x89PNG\r\n\x1a\n", "image/png")
    assert len(report.comparisons) == 1
    cmp = report.comparisons[0]
    assert cmp.parse_failed is False
    for f in cmp.fields:
        assert f.verdict == FieldVerdict.MATCH


def test_run_parser_reliability_records_parse_failure(
    tmp_path: Path, mocker: Any
) -> None:
    """BillParseError on a bill -> parse_failed=True, all fields MISS, no crash."""
    bills_dir = tmp_path / "bills"
    bills_dir.mkdir()
    (bills_dir / "fake_bill.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        '{"image":"fake_bill.png","distributor":"Fakedist",'
        '"installation_number":"000000","period":"1999-01",'
        '"consumption_kwh":"100","total_brl":"100"}\n',
        encoding="utf-8",
    )

    mocker.patch(
        "energia.evals.parser_reliability.parse_bill_image",
        side_effect=BillParseError("malformed"),
    )

    report = run_parser_reliability(labels_path=labels_path, bills_dir=bills_dir)

    assert len(report.comparisons) == 1
    cmp = report.comparisons[0]
    assert cmp.parse_failed is True
    for f in cmp.fields:
        assert f.verdict == FieldVerdict.MISS


def test_run_parser_reliability_infers_jpeg_media_type(
    tmp_path: Path, mocker: Any
) -> None:
    """.jpg and .jpeg both infer image/jpeg before calling parse_bill_image."""
    bills_dir = tmp_path / "bills"
    bills_dir.mkdir()
    (bills_dir / "fake_bill.jpg").write_bytes(b"\xff\xd8\xff")

    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text(
        '{"image":"fake_bill.jpg","distributor":"Fakedist",'
        '"installation_number":"000000","period":"1999-01",'
        '"consumption_kwh":"100","total_brl":"100"}\n',
        encoding="utf-8",
    )

    from energia.models import ParseResult

    mock_parse = mocker.patch(
        "energia.evals.parser_reliability.parse_bill_image",
        return_value=ParseResult(
            bill=_make_bill(consumption_kwh="100", total_brl="100"),
            needs_user_confirmation=False,
        ),
    )

    run_parser_reliability(labels_path=labels_path, bills_dir=bills_dir)

    mock_parse.assert_called_once_with(b"\xff\xd8\xff", "image/jpeg")
