"""tariff/snapshot — reader for versioned local ANEEL tariff snapshots.

Option B (ADR-004): the authoritative runtime tariff source is a
versioned local JSON snapshot committed under ``snapshots/<slug>.json``, not a
live ANEEL API client or HTTP cache. This module is the *reader* for that file
— pure read + parse + compute. No network, no cache, no LLM, no ChatState,
no DB.

HR-5 honesty contract:
- Money (``tusd`` / ``te``) is published in R$/MWh and is parsed straight into
  ``Decimal`` via ``json.loads(..., parse_float=Decimal)`` so values never
  round-trip through binary float before reaching Pydantic.
- ``base_tariff_brl_per_kwh`` is the REGULATED base tariff (TUSD + TE) in
  R$/kWh. It is deliberately NOT named "effective" or "consumption" rate —
  contrast ``bill/analysis.py``'s blended ``effective_rate_brl_per_kwh``
  (total paid / kWh). This number is a regulated price, not a blended one.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

_SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"
_MWH_PER_KWH = Decimal(1000)


class TariffSource(BaseModel):
    """Provenance of a snapshot — the ANEEL resolution it was transcribed from."""

    resolution: str
    published: date
    url: str


class SubclassTariff(BaseModel):
    """One B1 subclass's regulated components, published in R$/MWh.

    ``v1_supported`` / ``note`` only carry meaning for subsidized subclasses
    (e.g. ``baixa_renda``); they default to a fully-supported, unannotated
    subclass so ``convencional`` parses without extra keys.
    """

    tusd: Decimal
    te: Decimal
    v1_supported: bool = True
    note: str | None = None


class TariffSnapshot(BaseModel):
    """A versioned tariff snapshot for a single distributor."""

    distributor: str
    aliases: list[str]
    tariff_group: str
    unit: str
    source: TariffSource
    effective_from: date
    effective_to: date
    subclasses: dict[str, SubclassTariff]

    def base_tariff_brl_per_kwh(self, subclass: str) -> Decimal:
        """Regulated base tariff (TUSD + TE) for ``subclass``, in R$/kWh.

        This is the regulated price, NOT a blended effective/consumption rate.
        Components are stored in R$/MWh, so we divide by 1000.

        Raises ``KeyError`` if ``subclass`` is not in this snapshot.
        """
        tariff = self.subclasses[subclass]
        return (tariff.tusd + tariff.te) / _MWH_PER_KWH


def load_snapshot(distributor_slug: str = "enel_rj") -> TariffSnapshot:
    """Load and parse the tariff snapshot for ``distributor_slug``.

    Reads ``snapshots/<slug>.json`` relative to THIS module's location (not the
    CWD), so the reader works regardless of where the process was started.
    Money is parsed via ``parse_float=Decimal`` so R$/MWh values keep exact
    decimal precision.

    Raises ``FileNotFoundError`` with a clear message when the slug has no
    committed snapshot.
    """
    path = _SNAPSHOTS_DIR / f"{distributor_slug}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"No tariff snapshot for slug {distributor_slug!r}: "
            f"expected a file at {path}"
        )
    raw = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return TariffSnapshot.model_validate(raw)
