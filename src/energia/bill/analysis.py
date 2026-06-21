"""Bill analysis primitives — period-over-period comparison.

HR-5 / TD-018 honesty contract:
- This module computes WHAT moved between two periods: consumption Δ (kWh, %),
  cost Δ (R$, %), and the BLENDED EFFECTIVE RATE Δ (R$/kWh). It does NOT
  decompose into tariff / bandeira / tax — that would require authoritative
  ANEEL tariff data from ``get_tariff`` (Sprint 2, Task 2.3) and is a planned
  follow-up amendment.
- The ``effective_rate_brl_per_kwh`` field is ``total_brl / consumption_kwh``
  — a blended view of what the user actually paid per kWh. It is NOT the
  regulated tariff (TUSD + TE). The relabel from "tariff" to "effective rate"
  is structural: we report a number we can compute, not a price we don't have.
- Pure function: no DB, no LLM, no ChatState. ``compute_period_comparison``
  takes two ``Bill`` instances and returns a ``BillPeriodComparison``.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from energia.models import Bill


class PeriodSummary(BaseModel):
    """One period's headline numbers + the blended effective rate.

    ``effective_rate_brl_per_kwh`` is ``total_brl / consumption_kwh`` — the
    blended R$/kWh the user actually paid, not the regulated tariff
    (TUSD + TE). When ``consumption_kwh == 0`` the rate is ``Decimal(0)``
    to keep the contract Decimal-only (no None / no infinity).
    """

    period: str = Field(description="YYYY-MM reference month")
    consumption_kwh: Decimal = Field(description="kWh consumed in the period")
    total_brl: Decimal = Field(description="R$ paid for the period")
    effective_rate_brl_per_kwh: Decimal = Field(
        description=(
            "Blended R$/kWh = total_brl / consumption_kwh. NOT the regulated "
            "tariff (TUSD + TE). Zero when consumption_kwh is zero."
        ),
    )


class BillPeriodComparison(BaseModel):
    """Period-over-period delta. Reports WHAT changed, not WHY.

    Causal decomposition (tariff vs bandeira vs tax vs consumption) requires
    authoritative tariff data and is deferred to a Task 1.5 amendment after
    Sprint 2's ``get_tariff`` lands. See TD-018.
    """

    earlier: PeriodSummary
    later: PeriodSummary
    consumption_delta_kwh: Decimal
    consumption_delta_pct: Decimal = Field(
        description="(later - earlier) / earlier × 100; zero when earlier is zero",
    )
    cost_delta_brl: Decimal
    cost_delta_pct: Decimal = Field(
        description="(later - earlier) / earlier × 100; zero when earlier is zero",
    )
    effective_rate_delta_brl_per_kwh: Decimal = Field(
        description="later effective rate minus earlier effective rate (R$/kWh)",
    )


def _effective_rate(total: Decimal, consumption: Decimal) -> Decimal:
    if consumption == 0:
        return Decimal(0)
    return total / consumption


def _safe_pct(later: Decimal, earlier: Decimal) -> Decimal:
    if earlier == 0:
        return Decimal(0)
    return (later - earlier) / earlier * Decimal(100)


def _summarize(bill: Bill) -> PeriodSummary:
    return PeriodSummary(
        period=bill.period,
        consumption_kwh=bill.consumption_kwh,
        total_brl=bill.total_brl,
        effective_rate_brl_per_kwh=_effective_rate(
            bill.total_brl, bill.consumption_kwh
        ),
    )


def compute_period_comparison(
    *, earlier: Bill, later: Bill
) -> BillPeriodComparison:
    """Compute the period-over-period delta. Caller orders the arguments.

    The function does not reorder; the tool wrapper sorts periods
    lexicographically (YYYY-MM strings sort same as dates) and passes the
    smaller one as ``earlier``.
    """
    earlier_summary = _summarize(earlier)
    later_summary = _summarize(later)
    return BillPeriodComparison(
        earlier=earlier_summary,
        later=later_summary,
        consumption_delta_kwh=later.consumption_kwh - earlier.consumption_kwh,
        consumption_delta_pct=_safe_pct(
            later.consumption_kwh, earlier.consumption_kwh
        ),
        cost_delta_brl=later.total_brl - earlier.total_brl,
        cost_delta_pct=_safe_pct(later.total_brl, earlier.total_brl),
        effective_rate_delta_brl_per_kwh=(
            later_summary.effective_rate_brl_per_kwh
            - earlier_summary.effective_rate_brl_per_kwh
        ),
    )
