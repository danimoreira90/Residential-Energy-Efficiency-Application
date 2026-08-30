"""Offline Tarifa Branca comparison using the reviewed Enel RJ snapshot."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from energia.tariff.snapshot import TariffSource, load_snapshot

_MWH_PER_KWH = Decimal(1000)
_EXCLUSIONS = ("impostos", "COSIP", "Bandeira Tarifária")


class BrancaProfileError(ValueError):
    """Raised when a consumption profile cannot support a comparison."""


class BrancaComparison(BaseModel):
    """Auditable costs derived solely from a reviewed tariff snapshot."""

    distributor: str
    total_kwh: Decimal
    conventional_cost_brl: Decimal
    branca_cost_brl: Decimal
    savings_brl: Decimal
    savings_percent: Decimal
    exclusions: tuple[str, ...]
    source: TariffSource
    effective_from: date
    effective_to: date


def _rate_brl_per_kwh(tusd: Decimal, te: Decimal) -> Decimal:
    return (tusd + te) / _MWH_PER_KWH


def simulate_tarifa_branca(
    ponta_kwh: Decimal,
    intermediaria_kwh: Decimal,
    fora_ponta_kwh: Decimal,
) -> BrancaComparison:
    """Compare a supplied Enel RJ profile against conventional B1 rates.

    The calculation intentionally excludes taxes, COSIP, and Bandeira charges.
    """
    buckets = (ponta_kwh, intermediaria_kwh, fora_ponta_kwh)
    if any(not value.is_finite() or value < 0 for value in buckets):
        raise BrancaProfileError("consumption buckets must be non-negative")

    total_kwh = sum(buckets, Decimal(0))
    if total_kwh <= 0:
        raise BrancaProfileError("consumption profile must have a positive total")

    snapshot = load_snapshot("enel_rj")
    if snapshot.branca is None:
        raise RuntimeError("The reviewed Enel RJ snapshot has no Tarifa Branca rates")

    conventional_cost_brl = total_kwh * snapshot.base_tariff_brl_per_kwh("convencional")
    branca_cost_brl = (
        ponta_kwh * _rate_brl_per_kwh(snapshot.branca.ponta.tusd, snapshot.branca.ponta.te)
        + intermediaria_kwh
        * _rate_brl_per_kwh(snapshot.branca.intermediaria.tusd, snapshot.branca.intermediaria.te)
        + fora_ponta_kwh
        * _rate_brl_per_kwh(snapshot.branca.fora_ponta.tusd, snapshot.branca.fora_ponta.te)
    )
    savings_brl = conventional_cost_brl - branca_cost_brl

    return BrancaComparison(
        distributor=snapshot.distributor,
        total_kwh=total_kwh,
        conventional_cost_brl=conventional_cost_brl,
        branca_cost_brl=branca_cost_brl,
        savings_brl=savings_brl,
        savings_percent=(savings_brl / conventional_cost_brl) * Decimal(100),
        exclusions=_EXCLUSIONS,
        source=snapshot.source,
        effective_from=snapshot.effective_from,
        effective_to=snapshot.effective_to,
    )
