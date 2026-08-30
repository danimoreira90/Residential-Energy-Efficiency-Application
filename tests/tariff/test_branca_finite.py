"""Finite-value validation regression test for Tarifa Branca."""

from decimal import Decimal

import pytest

from energia.tariff.branca import BrancaProfileError, simulate_tarifa_branca


def test_simulate_tarifa_branca_rejects_non_finite_consumption() -> None:
    with pytest.raises(BrancaProfileError):
        simulate_tarifa_branca(Decimal("NaN"), Decimal("0"), Decimal("1"))
