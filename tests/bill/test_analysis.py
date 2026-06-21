"""Pure-function tests for bill/analysis.py — compute_period_comparison (RED first).

What this file pins:
- consumption_delta_kwh / consumption_delta_pct — difference + percentage,
  zero-prior-consumption guard returns Decimal(0) (no ZeroDivision).
- cost_delta_brl / cost_delta_pct — same, zero-prior-cost guard.
- effective_rate_brl_per_kwh on each PeriodSummary = total / consumption
  (the BLENDED rate, NOT the regulated tariff — TD-018 honesty relabel).
- effective_rate_delta_brl_per_kwh on the comparison = later − earlier.
- All deltas are Decimal, never float.

No DB, no LLM, no ChatState — these are pure-function tests.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from energia.bill.analysis import (
    BillPeriodComparison,
    PeriodSummary,
    compute_period_comparison,
)
from energia.models import Bill


def _bill(period: str, kwh: str, total: str) -> Bill:
    return Bill(
        distributor="Enel Rio",
        installation_number="000000",
        period=period,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 15),
        consumption_kwh=Decimal(kwh),
        tariff_group="B1",
        modalidade="Convencional",
        bandeira="Verde",
        total_brl=Decimal(total),
        composition=None,
        confidence=0.95,
    )


def test_compute_consumption_only_delta_keeps_effective_rate_flat() -> None:
    """Same blended rate (R$/kWh) before and after; only kWh changed."""
    earlier = _bill("2026-04", "200", "200")  # rate 1.00
    later = _bill("2026-05", "300", "300")  # rate 1.00

    cmp = compute_period_comparison(earlier=earlier, later=later)

    assert isinstance(cmp, BillPeriodComparison)
    assert cmp.consumption_delta_kwh == Decimal("100")
    assert cmp.consumption_delta_pct == Decimal("50")
    assert cmp.cost_delta_brl == Decimal("100")
    assert cmp.cost_delta_pct == Decimal("50")
    assert cmp.effective_rate_delta_brl_per_kwh == Decimal("0")


def test_compute_cost_only_delta_keeps_consumption_flat() -> None:
    """Same kWh both periods; cost up → effective rate up. No causal claim."""
    earlier = _bill("2026-04", "200", "180")  # rate 0.90
    later = _bill("2026-05", "200", "240")  # rate 1.20

    cmp = compute_period_comparison(earlier=earlier, later=later)

    assert cmp.consumption_delta_kwh == Decimal("0")
    assert cmp.consumption_delta_pct == Decimal("0")
    assert cmp.cost_delta_brl == Decimal("60")
    assert cmp.effective_rate_delta_brl_per_kwh == Decimal("0.30")


def test_compute_both_consumption_and_cost_delta() -> None:
    """Both moved; deltas are independent (no decomposition, no causation)."""
    earlier = _bill("2026-04", "200", "180")  # rate 0.90
    later = _bill("2026-05", "300", "360")  # rate 1.20

    cmp = compute_period_comparison(earlier=earlier, later=later)

    assert cmp.consumption_delta_kwh == Decimal("100")
    assert cmp.consumption_delta_pct == Decimal("50")
    assert cmp.cost_delta_brl == Decimal("180")
    assert cmp.effective_rate_delta_brl_per_kwh == Decimal("0.30")


def test_compute_effective_rate_on_each_period_summary_is_total_over_kwh() -> None:
    """PeriodSummary.effective_rate_brl_per_kwh = total / consumption."""
    earlier = _bill("2026-04", "200", "180")
    later = _bill("2026-05", "300", "330")

    cmp = compute_period_comparison(earlier=earlier, later=later)

    assert isinstance(cmp.earlier, PeriodSummary)
    assert cmp.earlier.effective_rate_brl_per_kwh == Decimal("0.9")
    assert cmp.later.effective_rate_brl_per_kwh == Decimal("1.1")


def test_compute_guards_division_by_zero_on_prior_consumption() -> None:
    """earlier.consumption_kwh == 0 → consumption_delta_pct returns Decimal(0).

    No ZeroDivisionError. The function never invents a "%" out of a 0 baseline.
    """
    earlier = _bill("2026-04", "0", "0")
    later = _bill("2026-05", "300", "300")

    cmp = compute_period_comparison(earlier=earlier, later=later)

    assert cmp.consumption_delta_kwh == Decimal("300")
    assert cmp.consumption_delta_pct == Decimal("0")


def test_compute_guards_division_by_zero_on_prior_cost() -> None:
    """earlier.total_brl == 0 → cost_delta_pct returns Decimal(0). No exception."""
    earlier = _bill("2026-04", "100", "0")
    later = _bill("2026-05", "100", "120")

    cmp = compute_period_comparison(earlier=earlier, later=later)

    assert cmp.cost_delta_brl == Decimal("120")
    assert cmp.cost_delta_pct == Decimal("0")


def test_compute_returns_decimals_everywhere_no_float() -> None:
    """Every numeric field of the comparison is Decimal — never float."""
    earlier = _bill("2026-04", "200", "200")
    later = _bill("2026-05", "300", "330")

    cmp = compute_period_comparison(earlier=earlier, later=later)

    for value in (
        cmp.earlier.consumption_kwh,
        cmp.earlier.total_brl,
        cmp.earlier.effective_rate_brl_per_kwh,
        cmp.later.consumption_kwh,
        cmp.later.total_brl,
        cmp.later.effective_rate_brl_per_kwh,
        cmp.consumption_delta_kwh,
        cmp.consumption_delta_pct,
        cmp.cost_delta_brl,
        cmp.cost_delta_pct,
        cmp.effective_rate_delta_brl_per_kwh,
    ):
        assert isinstance(value, Decimal), (
            f"every numeric field must be Decimal; got {type(value).__name__}"
        )
