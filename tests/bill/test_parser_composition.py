"""Optional / structural composition behaviour in parse_bill_image (RED-first).

Grupo B1 residential solar sizing uses only header fields (consumption_kwh,
total_brl, distributor, period). The TUSD/TE/ICMS fiscal table is a Grupo A
concern and is the part that intermittently breaks parses. This file pins
the structural degradation contract introduced on
`quality/optional-bill-composition`:

    composition is all-or-nothing.
    If absent, null, partial, or otherwise invalid → composition = None.
    Header fields remain required (unreadable headers still raise BillParseError).
    HR-5: dropping an unreadable reading is not inventing values.

All Anthropic SDK calls are mocked. No real API traffic, no DuckDB writes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from energia.bill.parser import parse_bill_image
from energia.models import BillComposition, ParseResult

_FIXTURES = Path(__file__).parent / "fixtures"
_FIXTURE_PNG: bytes = (_FIXTURES / "enel_rj.png").read_bytes()


def _make_api_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


def _bill_payload(
    *,
    composition: Any = "FULL",  # sentinel: "FULL" → include the canonical block
    confidence: float = 0.95,
    drop_composition_key: bool = False,
) -> dict[str, Any]:
    """Build the JSON payload the vision model would normally produce."""
    payload: dict[str, Any] = {
        "distributor": "Enel Rio",
        "installation_number": "987654",
        "period": "2026-03",
        "issue_date": "2026-03-10",
        "due_date": "2026-03-20",
        "consumption_kwh": "312.50",
        "tariff_group": "B1",
        "modalidade": "Convencional",
        "bandeira": "Verde",
        "total_brl": "287.40",
        "confidence": confidence,
    }
    if drop_composition_key:
        return payload
    if composition == "FULL":
        payload["composition"] = {
            "tusd": "120.00",
            "te": "100.00",
            "icms": "55.00",
        }
    else:
        payload["composition"] = composition
    return payload


def _patch_api(mocker: Any, payload: dict[str, Any]) -> None:
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.return_value = _make_api_response(json.dumps(payload))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parser_returns_bill_with_null_composition_when_fiscal_table_unreadable(
    mocker: Any,
) -> None:
    """API returned explicit `"composition": null` → header fields parse, composition is None."""
    _patch_api(mocker, _bill_payload(composition=None))

    result = parse_bill_image(_FIXTURE_PNG, "image/png")

    assert isinstance(result, ParseResult)
    assert result.bill.composition is None
    # Header fields populated as usual.
    assert result.bill.distributor == "Enel Rio"
    assert result.bill.period == "2026-03"
    assert str(result.bill.total_brl) == "287.40"
    assert str(result.bill.consumption_kwh) == "312.50"


def test_parser_keeps_full_composition_when_fiscal_table_legible(mocker: Any) -> None:
    """Regression guard: a complete composition block round-trips through the parser."""
    _patch_api(mocker, _bill_payload())

    result = parse_bill_image(_FIXTURE_PNG, "image/png")

    assert isinstance(result.bill.composition, BillComposition)
    assert str(result.bill.composition.tusd) == "120.00"
    assert str(result.bill.composition.te) == "100.00"
    assert str(result.bill.composition.icms) == "55.00"


def test_null_composition_alone_does_not_force_needs_user_confirmation(
    mocker: Any,
) -> None:
    """A missing composition is NOT a low-confidence signal by itself.

    needs_user_confirmation must continue to depend solely on bill.confidence,
    not on whether the fiscal table was legible. A header-only Grupo B1 bill
    with confidence 0.95 still flows through without forcing user confirmation.
    """
    _patch_api(mocker, _bill_payload(composition=None, confidence=0.95))

    result = parse_bill_image(_FIXTURE_PNG, "image/png")

    assert result.bill.composition is None
    assert result.needs_user_confirmation is False


def test_parser_accepts_omitted_composition_key_entirely(mocker: Any) -> None:
    """Defensive: a model output with no `composition` key at all still parses.

    The model default (composition=None) carries the contract — the parser does
    not need to inject a key just because the vision model omitted one.
    """
    _patch_api(mocker, _bill_payload(drop_composition_key=True))

    result = parse_bill_image(_FIXTURE_PNG, "image/png")

    assert result.bill.composition is None
    assert result.bill.distributor == "Enel Rio"


def test_parser_degrades_partial_composition_to_none(mocker: Any) -> None:
    """Partial composition (e.g. tusd present, te/icms missing) → composition None.

    HR-5 / structural degradation: a partial fiscal table is structurally
    unreadable; the parser drops it to None rather than inventing the missing
    components. The bill still parses successfully on header fields alone —
    BillParseError must NOT be raised in this case.
    """
    _patch_api(mocker, _bill_payload(composition={"tusd": "120.00"}))

    result = parse_bill_image(_FIXTURE_PNG, "image/png")

    assert isinstance(result, ParseResult)
    assert result.bill.composition is None, (
        "partial composition (tusd alone) must degrade to None, not be retained "
        "with invented te/icms (HR-5) and not raise BillParseError"
    )
    # Header fields untouched.
    assert result.bill.distributor == "Enel Rio"
    assert str(result.bill.total_brl) == "287.40"
