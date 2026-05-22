"""Tests for src/energia/bill/parser.py — Stage A.

All Anthropic SDK calls are mocked. No DuckDB, no real API calls, no bill_store.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import anthropic
import pytest

from energia.bill.parser import BillParseError, parse_bill_image
from energia.models import Bill, ParseResult

_FIXTURES = Path(__file__).parent / "fixtures"
_FIXTURE_PNG: bytes = (_FIXTURES / "enel_rj.png").read_bytes()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


def _valid_bill_json(confidence: float = 0.95) -> str:
    return json.dumps({
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
        "composition": {
            "tusd": "120.00",
            "te": "100.00",
            "icms": "55.00",
        },
        "confidence": confidence,
    })


def _bill_json_with_pii() -> str:
    """Bill JSON where installation_number matches the CPF regex — tests it doesn't leak to logs."""
    data = json.loads(_valid_bill_json())
    data["installation_number"] = "123.456.789-00"
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_bill_returns_parse_result_with_bill_on_success(mocker: Any) -> None:
    """Parser returns a ParseResult containing a fully validated Bill on a clean API response."""
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.return_value = _make_api_response(_valid_bill_json())

    result = parse_bill_image(_FIXTURE_PNG, "image/png")

    assert isinstance(result, ParseResult)
    assert isinstance(result.bill, Bill)
    assert result.bill.distributor == "Enel Rio"
    assert result.bill.period == "2026-03"


def test_parse_bill_calls_vision_api_exactly_once_on_success(mocker: Any) -> None:
    """_client.messages.create is called exactly once on a clean response."""
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.return_value = _make_api_response(_valid_bill_json())

    parse_bill_image(_FIXTURE_PNG, "image/png")

    mock_client.messages.create.assert_called_once()


def test_parse_bill_raises_on_malformed_json_response(mocker: Any) -> None:
    """BillParseError raised when the API response contains no valid JSON object."""
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.return_value = _make_api_response(
        "Não consigo ler esta imagem."
    )

    with pytest.raises(BillParseError):
        parse_bill_image(_FIXTURE_PNG, "image/png")


def test_parse_bill_sets_needs_confirmation_when_low_confidence(mocker: Any) -> None:
    """ParseResult.needs_user_confirmation is True when bill.confidence < 0.85."""
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.return_value = _make_api_response(
        _valid_bill_json(confidence=0.70)
    )

    result = parse_bill_image(_FIXTURE_PNG, "image/png")

    assert result.needs_user_confirmation is True


def test_parse_bill_raises_on_validation_error_no_partial_data(mocker: Any) -> None:
    """BillParseError raised (not partial ParseResult) when JSON is valid but Bill schema fails."""
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.return_value = _make_api_response(
        json.dumps({"distributor": "Enel Rio"})  # missing required fields
    )

    with pytest.raises(BillParseError):
        parse_bill_image(_FIXTURE_PNG, "image/png")


def test_parse_bill_retries_once_on_5xx_raises_if_retry_also_fails(mocker: Any) -> None:
    """_client.messages.create is called exactly twice; BillParseError raised after second 5xx."""
    mock_http_response = MagicMock()
    mock_http_response.status_code = 503
    err_503 = anthropic.APIStatusError(
        "Service Unavailable",
        response=mock_http_response,
        body={},
    )
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.side_effect = [err_503, err_503]

    with pytest.raises(BillParseError):
        parse_bill_image(_FIXTURE_PNG, "image/png")

    assert mock_client.messages.create.call_count == 2


def test_parse_bill_does_not_log_image_bytes_or_pii(
    mocker: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """caplog.text contains no CPF pattern and no base64-like string >= 50 chars (HR-6)."""
    mock_client = mocker.patch("energia.bill.parser._client")
    mock_client.messages.create.return_value = _make_api_response(_bill_json_with_pii())

    with caplog.at_level(logging.DEBUG, logger="energia.bill.parser"):
        parse_bill_image(_FIXTURE_PNG, "image/png")

    assert not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", caplog.text), (
        "CPF pattern found in logs — PII leak"
    )
    assert not re.search(r"[A-Za-z0-9+/]{50,}", caplog.text), (
        "Long base64-like string found in logs — possible image bytes leak"
    )


def test_parse_bill_raises_on_unusable_image() -> None:
    """BillParseError raised for empty bytes and unsupported media_type — no API call made (TE-07).

    Note: valid MIME with corrupt image content (e.g. b"not-a-png" with media_type="image/png")
    is NOT caught by pre-flight validation. It is handled implicitly: the Anthropic API returns
    an APIError (caught by _call_with_one_retry -> BillParseError) or returns unparseable text
    (caught by _parse_response -> BillParseError). This is a known documented gap in pre-flight
    coverage; the BillParseError contract still holds on that path.
    """
    with pytest.raises(BillParseError):
        parse_bill_image(b"", "image/png")

    with pytest.raises(BillParseError):
        parse_bill_image(b"\x89PNG\r\n", "image/tiff")
