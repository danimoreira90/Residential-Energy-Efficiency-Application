"""Parser-reliability eval harness — parser-direct, label-graded.

Measures how accurately ``parse_bill_image`` reads real bills by comparing its
structured ``Bill`` output against hand-written ground-truth labels. The
harness only compares — it never invents, back-fills, or guesses a value
(HR-5). Labels are written by Daniel; auto-labeling with an LLM would grade
Claude-vision against itself.

Per-field verdicts
==================
- ``MATCH``      — both label and parsed value are present and equal
                   (Decimal compare for kWh/BRL: ``"374" == "374.00"``;
                    leading-zero-normalized compare for ``installation_number``:
                    ``"0006354013" == "000006354013"``).
- ``MISS``       — label has a value, parser returned nothing for that field
                   (or the whole parse failed with ``BillParseError``).
- ``MISREAD``    — label has a value, parser produced a different value.
- ``INVENTION``  — label says the field is not legibly on the bill (null),
                   parser produced a value anyway. **HR-5 violation flag.**

HR-6 redaction
==============
``installation_number`` is PII (UC). Its value is NEVER written into the
``FieldComparison`` record or surfaced in the console report — only the
verdict. The UC normalization that powers the leading-zero compare runs
in-flight inside ``_score_uc``; normalized values never leave that scope.
Other fields may carry values for debugging.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field, ValidationError, field_validator

from energia.bill.parser import BillParseError, parse_bill_image
from energia.models import Bill, PeriodStr

__all__ = [
    "BillLabel",
    "FieldVerdict",
    "FieldComparison",
    "BillComparison",
    "ParserReliabilityReport",
    "load_labels",
    "score_bill",
    "run_parser_reliability",
    "format_report",
]


_MEDIA_TYPE_BY_EXT: Final[dict[str, str]] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

_REDACTED_FIELDS: Final[frozenset[str]] = frozenset({"installation_number"})
_REDACTION_MARKER: Final[str] = "[redacted — HR-6]"

_SCORED_STRING_FIELDS: Final[tuple[str, ...]] = (
    "distributor",
    "installation_number",
    "period",
)
_SCORED_DECIMAL_FIELDS: Final[tuple[str, ...]] = (
    "consumption_kwh",
    "total_brl",
)


# ---------------------------------------------------------------------------
# Label schema
# ---------------------------------------------------------------------------


class BillLabel(BaseModel):
    """Ground-truth label for a single bill image.

    A field is ``None`` when the value is not legibly on the bill — that's
    different from "we didn't bother to label it". Old labels with a
    ``"composition"`` key still load: Pydantic v2's default is
    ``extra="ignore"`` so unknown keys are silently dropped.
    """

    image: str = Field(description="Filename relative to bills_dir")
    distributor: str | None = None
    installation_number: str | None = None
    period: PeriodStr | None = Field(
        default=None, description="YYYY-MM, or null if illegible"
    )
    consumption_kwh: str | None = None
    total_brl: str | None = None

    @field_validator("consumption_kwh", "total_brl")
    @classmethod
    def _validate_numeric_string(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            Decimal(v)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"not a valid numeric string: {v!r}") from exc
        return v


# ---------------------------------------------------------------------------
# Verdicts + per-field comparison
# ---------------------------------------------------------------------------


class FieldVerdict(StrEnum):
    MATCH = "MATCH"
    MISS = "MISS"
    MISREAD = "MISREAD"
    INVENTION = "INVENTION"


class FieldComparison(BaseModel):
    """One field's verdict + (optionally) the values that produced it.

    For ``installation_number`` (HR-6), ``expected`` and ``parsed`` MUST stay
    ``None`` — the verdict carries all reportable signal. Other fields may
    populate them for debugging.
    """

    name: str
    verdict: FieldVerdict
    expected: str | None = None
    parsed: str | None = None


class BillComparison(BaseModel):
    image: str
    parse_failed: bool
    fields: list[FieldComparison]


class ParserReliabilityReport(BaseModel):
    comparisons: list[BillComparison]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_labels(path: Path) -> list[BillLabel]:
    """Load BillLabel rows from a JSONL file.

    Blank lines and ``#``-prefixed comments are skipped. Raises ``ValueError``
    on any malformed line so the caller can fail loudly rather than silently
    skipping rows with bad data (PII / typos).
    """
    labels: list[BillLabel] = []
    with path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"malformed JSON on line {lineno} of {path}: {exc}"
                ) from exc
            try:
                labels.append(BillLabel.model_validate(data))
            except ValidationError as exc:
                raise ValueError(
                    f"schema error on line {lineno} of {path}: {exc}"
                ) from exc
    return labels


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


def _make_field(
    name: str,
    verdict: FieldVerdict,
    *,
    expected: str | None = None,
    parsed: str | None = None,
) -> FieldComparison:
    """Build a FieldComparison, enforcing HR-6 redaction at the constructor.

    The redaction guard lives here so any future scorer extension cannot leak
    UC values into the record by accident — the FieldComparison for a redacted
    field always has expected=None and parsed=None.
    """
    if name in _REDACTED_FIELDS:
        return FieldComparison(name=name, verdict=verdict, expected=None, parsed=None)
    return FieldComparison(
        name=name, verdict=verdict, expected=expected, parsed=parsed
    )


def _score_string(
    name: str, expected: str | None, parsed: str
) -> FieldComparison:
    if expected is None:
        return _make_field(name, FieldVerdict.INVENTION, expected=None, parsed=parsed)
    if expected.strip() == parsed.strip():
        return _make_field(
            name, FieldVerdict.MATCH, expected=expected, parsed=parsed
        )
    return _make_field(
        name, FieldVerdict.MISREAD, expected=expected, parsed=parsed
    )


def _normalize_uc(value: str | None) -> str | None:
    """Strip leading zeros from a UC string.

    Brazilian bill templates render the same UC with different left-pad widths
    (``0006354013`` vs ``000006354013``). The number is identical; the padding
    is formatting. ``"0"`` (all-zeros edge case) is preserved as ``"0"`` so a
    fabricated-data test of all-zero values doesn't collapse to an empty string.
    """
    if value is None:
        return None
    return value.strip().lstrip("0") or "0"


def _score_uc(expected: str | None, parsed: str) -> FieldComparison:
    """installation_number scorer.

    Compares leading-zero-normalized UCs but emits a FieldComparison via
    ``_make_field``, which already enforces HR-6 redaction (expected/parsed
    forced to None for the installation_number name). The normalized values
    never escape this function's scope.
    """
    if expected is None:
        return _make_field(
            "installation_number", FieldVerdict.INVENTION, expected=None, parsed=parsed
        )
    if _normalize_uc(expected) == _normalize_uc(parsed):
        return _make_field(
            "installation_number", FieldVerdict.MATCH, expected=expected, parsed=parsed
        )
    return _make_field(
        "installation_number", FieldVerdict.MISREAD, expected=expected, parsed=parsed
    )


def _score_decimal(
    name: str, expected: str | None, parsed: Decimal
) -> FieldComparison:
    if expected is None:
        return _make_field(
            name, FieldVerdict.INVENTION, expected=None, parsed=str(parsed)
        )
    if Decimal(expected) == parsed:
        return _make_field(
            name, FieldVerdict.MATCH, expected=expected, parsed=str(parsed)
        )
    return _make_field(
        name, FieldVerdict.MISREAD, expected=expected, parsed=str(parsed)
    )


def _all_miss(label: BillLabel) -> list[FieldComparison]:
    fields: list[FieldComparison] = []
    for name in _SCORED_STRING_FIELDS:
        expected = getattr(label, name)
        fields.append(_make_field(name, FieldVerdict.MISS, expected=expected))
    for name in _SCORED_DECIMAL_FIELDS:
        expected = getattr(label, name)
        fields.append(_make_field(name, FieldVerdict.MISS, expected=expected))
    return fields


def score_bill(*, bill: Bill | None, label: BillLabel) -> BillComparison:
    """Compare a parsed Bill against its hand-written label.

    bill=None signals parse_bill_image raised; every field is MISS in that
    case (the parser produced no data at all, regardless of what the label
    said). HR-5 INVENTION detection only fires when a Bill exists and a label
    field is null. installation_number is routed through ``_score_uc`` which
    normalizes leading zeros; other strings go through plain ``_score_string``.
    """
    if bill is None:
        return BillComparison(image=label.image, parse_failed=True, fields=_all_miss(label))

    fields: list[FieldComparison] = []
    for name in _SCORED_STRING_FIELDS:
        expected = getattr(label, name)
        parsed = getattr(bill, name)
        if name == "installation_number":
            fields.append(_score_uc(expected, parsed))
        else:
            fields.append(_score_string(name, expected, parsed))
    for name in _SCORED_DECIMAL_FIELDS:
        fields.append(_score_decimal(name, getattr(label, name), getattr(bill, name)))

    return BillComparison(image=label.image, parse_failed=False, fields=fields)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _media_type_for(image_path: Path) -> str:
    ext = image_path.suffix.lower()
    media = _MEDIA_TYPE_BY_EXT.get(ext)
    if media is None:
        raise ValueError(
            f"unsupported image extension {ext!r} for {image_path.name} — "
            f"expected one of {sorted(_MEDIA_TYPE_BY_EXT)}"
        )
    return media


def run_parser_reliability(
    *, labels_path: Path, bills_dir: Path
) -> ParserReliabilityReport:
    """Drive parse_bill_image over every labeled bill and aggregate verdicts.

    Each label.image is resolved against bills_dir; the file's bytes and an
    extension-inferred media_type are passed straight to parse_bill_image.
    BillParseError is captured per-bill (parse_failed=True, all fields MISS)
    so one bad scan can't abort the whole run.
    """
    labels = load_labels(labels_path)
    comparisons: list[BillComparison] = []

    for label in labels:
        image_path = bills_dir / label.image
        image_bytes = image_path.read_bytes()
        media_type = _media_type_for(image_path)
        try:
            result = parse_bill_image(image_bytes, media_type)
            bill: Bill | None = result.bill
        except BillParseError:
            bill = None
        comparisons.append(score_bill(bill=bill, label=label))

    return ParserReliabilityReport(comparisons=comparisons)


# ---------------------------------------------------------------------------
# Console report — HR-6 redaction applied at the output boundary too
# ---------------------------------------------------------------------------


def _format_field_value(field: FieldComparison) -> str:
    if field.name in _REDACTED_FIELDS:
        return _REDACTION_MARKER
    if field.verdict == FieldVerdict.MATCH:
        if field.parsed is not None:
            return f"({field.parsed!r})"
        return ""
    if field.verdict == FieldVerdict.MISREAD:
        return f"(expected {field.expected!r}, got {field.parsed!r})"
    if field.verdict == FieldVerdict.MISS:
        return f"(expected {field.expected!r}, got nothing)"
    if field.verdict == FieldVerdict.INVENTION:
        return f"(label null, got {field.parsed!r})"
    return ""


def _aggregate_counts(report: ParserReliabilityReport) -> dict[FieldVerdict, int]:
    counts: dict[FieldVerdict, int] = {v: 0 for v in FieldVerdict}
    for cmp in report.comparisons:
        for f in cmp.fields:
            counts[f.verdict] += 1
    return counts


def format_report(report: ParserReliabilityReport) -> str:
    """Format the report for console output.

    installation_number always renders as the redaction marker, regardless of
    verdict (so an expected/parsed value can never leak through this path).
    """
    lines: list[str] = []
    for cmp in report.comparisons:
        lines.append(f"== {cmp.image} ==")
        if cmp.parse_failed:
            lines.append("  PARSE FAILED — every field counts as MISS")
        for f in cmp.fields:
            value_part = _format_field_value(f)
            lines.append(f"  {f.name:<24}{f.verdict.value:<12}{value_part}")
        lines.append("")

    counts = _aggregate_counts(report)
    total_fields = sum(counts.values())
    parse_failures = sum(1 for c in report.comparisons if c.parse_failed)
    lines.append(
        f"Overall: {counts[FieldVerdict.MATCH]} MATCH / "
        f"{counts[FieldVerdict.MISREAD]} MISREAD / "
        f"{counts[FieldVerdict.MISS]} MISS / "
        f"{counts[FieldVerdict.INVENTION]} INVENTION "
        f"across {total_fields} fields, {parse_failures} parse failures"
    )
    return "\n".join(lines)
