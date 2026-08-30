"""Tarifa Branca calculation tests (Task 2.4, RED first)."""

from decimal import Decimal

import pytest

from energia.tariff.branca import BrancaProfileError, simulate_tarifa_branca


def test_simulate_tarifa_branca_uses_reviewed_enel_rates_with_decimal_totals() -> None:
    comparison = simulate_tarifa_branca(
        ponta_kwh=Decimal("30"),
        intermediaria_kwh=Decimal("20"),
        fora_ponta_kwh=Decimal("250"),
    )

    assert comparison.total_kwh == Decimal("300")
    assert comparison.conventional_cost_brl == Decimal("318.33000")
    assert comparison.branca_cost_brl == Decimal("316.84590")
    assert comparison.savings_brl == Decimal("1.48410")
    assert comparison.savings_percent.quantize(Decimal("0.01")) == Decimal("0.47")
    assert comparison.source.resolution == "REH 3570/2026"
    assert comparison.effective_from.isoformat() == "2026-03-15"


@pytest.mark.parametrize(
    ("ponta_kwh", "intermediaria_kwh", "fora_ponta_kwh"),
    [
        (Decimal("-1"), Decimal("0"), Decimal("1")),
        (Decimal("0"), Decimal("0"), Decimal("0")),
    ],
)
def test_simulate_tarifa_branca_rejects_meaningless_profile(
    ponta_kwh: Decimal,
    intermediaria_kwh: Decimal,
    fora_ponta_kwh: Decimal,
) -> None:
    with pytest.raises(BrancaProfileError):
        simulate_tarifa_branca(ponta_kwh, intermediaria_kwh, fora_ponta_kwh)
