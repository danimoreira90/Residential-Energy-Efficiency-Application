"""Tests for Task 1.2 — Bill and BillComposition Pydantic models (TDD — written RED-first)."""
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from energia.models import Bill, BillComposition, ParseResult


# dict[str, Any]: test builders mix field types; Any avoids 13-field typed overloads.
def _valid_composition(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "tusd": Decimal("150.00"),
        "te": Decimal("100.00"),
        "icms": Decimal("37.40"),
    }
    base.update(overrides)
    return base


def _valid_bill(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "distributor": "Enel Rio",
        "installation_number": "3001234567",
        "period": "2026-05",
        "issue_date": date(2026, 5, 10),
        "due_date": date(2026, 5, 20),
        "consumption_kwh": Decimal("312.00"),
        "tariff_group": "B1",
        "modalidade": "Convencional",
        "total_brl": Decimal("287.40"),
        "composition": BillComposition(**_valid_composition()),
        "confidence": 0.95,
    }
    base.update(overrides)
    return base


class TestBill:
    def test_bill_requires_distributor(self) -> None:
        data = _valid_bill()
        del data["distributor"]
        with pytest.raises(ValidationError):
            Bill(**data)

    def test_bill_rejects_composition_missing_required_field(self) -> None:
        comp_data = _valid_composition()
        del comp_data["tusd"]
        with pytest.raises(ValidationError):
            BillComposition(**comp_data)

    def test_bill_stores_amounts_as_decimal(self) -> None:
        bill = Bill(**_valid_bill())
        assert isinstance(bill.total_brl, Decimal)
        assert isinstance(bill.consumption_kwh, Decimal)
        assert bill.composition is not None
        assert isinstance(bill.composition.other, Decimal)
        assert bill.composition.other == Decimal("0")

    def test_bill_period_accepts_valid_yyyy_mm(self) -> None:
        bill = Bill(**_valid_bill(period="2026-05"))
        assert bill.period == "2026-05"

    def test_bill_period_rejects_unpadded_month(self) -> None:
        with pytest.raises(ValidationError):
            Bill(**_valid_bill(period="2026-5"))

    def test_bill_period_rejects_wrong_separator(self) -> None:
        with pytest.raises(ValidationError):
            Bill(**_valid_bill(period="2026/05"))

    def test_bill_period_rejects_invalid_month(self) -> None:
        with pytest.raises(ValidationError):
            Bill(**_valid_bill(period="2026-13"))

    def test_bill_rejects_confidence_above_one(self) -> None:
        with pytest.raises(ValidationError):
            Bill(**_valid_bill(confidence=1.5))

    def test_bill_rejects_confidence_below_zero(self) -> None:
        with pytest.raises(ValidationError):
            Bill(**_valid_bill(confidence=-0.1))

    def test_bill_no_longer_has_needs_user_confirmation(self) -> None:
        bill = Bill(**_valid_bill())
        assert not hasattr(bill, "needs_user_confirmation")


class TestParseResult:
    def test_parse_result_requires_bill(self) -> None:
        with pytest.raises(ValidationError):
            ParseResult(needs_user_confirmation=False)  # type: ignore[call-arg]

    def test_parse_result_requires_needs_user_confirmation(self) -> None:
        with pytest.raises(ValidationError):
            ParseResult(bill=Bill(**_valid_bill()))  # type: ignore[call-arg]

    def test_parse_result_stores_flag_true(self) -> None:
        result = ParseResult(bill=Bill(**_valid_bill()), needs_user_confirmation=True)
        assert result.needs_user_confirmation is True
        assert result.bill.distributor == "Enel Rio"

    def test_parse_result_stores_flag_false(self) -> None:
        result = ParseResult(bill=Bill(**_valid_bill()), needs_user_confirmation=False)
        assert result.needs_user_confirmation is False
