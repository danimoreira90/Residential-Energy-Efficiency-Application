"""tariff/gd — Lei 14.300 Article 27 schedule and the reviewed Fio B snapshot.

Sprint 3 Task 3.3 (see docs/specs/sprint-3-solar-payback.md, ADR-010).

Two responsibilities, both pure read/compute — no network, no DB, no cache,
no logging:

- ``compensation_charge`` returns the exact Decimal Article 27 transition
  fraction for 2023-2028, and an explicitly non-statutory ``1.00`` planning
  fraction from 2029 onward (ADR-010). A connection year before 2023 is
  rejected.
- ``load_fio_b_snapshot`` reads the committed, allowlisted ANEEL
  ``TUSD_FioB`` component row for ENEL RJ B1 Convencional Residencial. The
  raw lexical value is parsed straight into ``Decimal`` (never through
  float). Identical complete rows deduplicate; any other row or provenance
  mismatch fails closed with ``GDDataError``.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

_SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"
_DEFAULT_FIO_B_SNAPSHOT_PATH = _SNAPSHOTS_DIR / "enel_rj_fio_b.json"

_ARTICLE_27_SCHEDULE: dict[int, Decimal] = {
    2023: Decimal("0.15"),
    2024: Decimal("0.30"),
    2025: Decimal("0.45"),
    2026: Decimal("0.60"),
    2027: Decimal("0.75"),
    2028: Decimal("0.90"),
}
_ARTICLE_27_BASIS = "article_27_transition"
_POST_2028_BASIS = "conservative_post_2028_planning_scenario"
_POST_2028_FRACTION = Decimal("1.00")

_EXPECTED_FIO_B_UNIT = "BRL_per_MWh"
_EXPECTED_FIO_B_SOURCE = {
    "resource_id": "e8717aa8-2521-453f-bf16-fbb9a16eea39",
    "resource_hash": "c4bd43306833b0583a2fad9fa0945665",
    "updated": "2026-09-03",
}
_EXPECTED_FIO_B_SOURCE_URL = (
    "https://dadosabertos.aneel.gov.br/pt_BR/dataset/componentes-tarifarias/"
    "resource/e8717aa8-2521-453f-bf16-fbb9a16eea39"
)
_EXPECTED_FIO_B_ROW = {
    "distributor": "ENEL RJ",
    "tariff_group": "B1",
    "modality": "Convencional",
    "consumer_class": "Residencial",
    "consumer_subclass": "Residencial",
    "consumer_detail": "Não se aplica",
    "tariff_period": "Não se aplica",
    "basis": "Tarifa de Aplicação",
    "component": "TUSD_FioB",
    "effective_from": "2026-03-15",
    "effective_to": "2027-03-14",
    "value": "361.02479751700002",
}
_INVALID_YEAR_MESSAGE = "Connection year is outside the supported scope"
_INVALID_FIO_B_SNAPSHOT_MESSAGE = "Fio B snapshot is unavailable or invalid"


class GDDataError(ValueError):
    """A GD compensation charge or Fio B snapshot could not be safely resolved."""


class CompensationCharge(BaseModel):
    """The Article 27 (or post-2028 planning) fraction for one calendar year."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fraction: Decimal
    regulatory_basis: str


class FioBSource(BaseModel):
    """Provenance of the committed ANEEL Componentes Tarifárias row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_id: str
    resource_hash: str
    updated: date
    url: str


class FioBSnapshot(BaseModel):
    """The single reviewed ENEL RJ B1 Convencional ``TUSD_FioB`` row.

    Only allowlisted filter dimensions, unit, effective dates, and the raw
    Decimal value are carried. The source row's ``NumCPFCNPJ`` field is never
    copied here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    distributor: str
    tariff_group: str
    modality: str
    consumer_class: str
    consumer_subclass: str
    consumer_detail: str
    tariff_period: str
    basis: str
    component: str
    unit: str
    effective_from: date
    effective_to: date
    tusd_fio_b_brl_per_mwh: Decimal
    source: FioBSource


def compensation_charge(year: int) -> CompensationCharge:
    """Return the Article 27 (or post-2028 planning) charge fraction for ``year``.

    Raises ``GDDataError`` for ``year < 2023`` (Article 26/grandfathered
    projects are out of scope). ``2029`` onward returns ``1.00`` labelled
    ``conservative_post_2028_planning_scenario`` — an application planning
    assumption, never a statement that Article 17 already sets 100% Fio B.
    """
    if isinstance(year, bool) or year < 2023:
        raise GDDataError(_INVALID_YEAR_MESSAGE)
    if year in _ARTICLE_27_SCHEDULE:
        return CompensationCharge(
            fraction=_ARTICLE_27_SCHEDULE[year], regulatory_basis=_ARTICLE_27_BASIS
        )
    return CompensationCharge(fraction=_POST_2028_FRACTION, regulatory_basis=_POST_2028_BASIS)


def load_fio_b_snapshot(path: Path | None = None) -> FioBSnapshot:
    """Load and validate the committed ``TUSD_FioB`` component snapshot.

    Defaults to the committed ``snapshots/enel_rj_fio_b.json`` next to this
    module. Rows are deduplicated only when every field (all allowlisted
    dimensions plus the exact value) matches; any remaining disagreement or
    mismatch against the reviewed row and provenance fails closed with
    ``GDDataError``.
    """
    try:
        target = path if path is not None else _DEFAULT_FIO_B_SNAPSHOT_PATH
        raw: object = json.loads(target.read_text(encoding="utf-8"), parse_float=Decimal)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE) from None

    payload = _string_dict(raw)
    if payload is None or set(payload) != {"source", "unit", "rows"}:
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE)

    unit = payload["unit"]
    source = _string_dict(payload["source"])
    rows_value = payload["rows"]
    if not isinstance(rows_value, list):
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE) from None
    rows = [_string_dict(value) for value in cast(list[object], rows_value)]

    if (
        unit != _EXPECTED_FIO_B_UNIT
        or source is None
        or set(source) != {*_EXPECTED_FIO_B_SOURCE, "url"}
        or any(source.get(key) != value for key, value in _EXPECTED_FIO_B_SOURCE.items())
        or source.get("url") != _EXPECTED_FIO_B_SOURCE_URL
        or not rows
        or any(row is None for row in rows)
    ):
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE)

    row = rows[0]
    if row is None:
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE)
    if row != _EXPECTED_FIO_B_ROW or any(candidate != row for candidate in rows[1:]):
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE)

    value = row.get("value")
    if not isinstance(value, str):
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE)
    try:
        return FioBSnapshot.model_validate(
            {
                "distributor": row["distributor"],
                "tariff_group": row["tariff_group"],
                "modality": row["modality"],
                "consumer_class": row["consumer_class"],
                "consumer_subclass": row["consumer_subclass"],
                "consumer_detail": row["consumer_detail"],
                "tariff_period": row["tariff_period"],
                "basis": row["basis"],
                "component": row["component"],
                "unit": unit,
                "effective_from": row["effective_from"],
                "effective_to": row["effective_to"],
                "tusd_fio_b_brl_per_mwh": Decimal(value),
                "source": source,
            }
        )
    except (KeyError, TypeError, ValueError):
        raise GDDataError(_INVALID_FIO_B_SNAPSHOT_MESSAGE) from None


def _string_dict(value: object) -> dict[str, object] | None:
    """Narrow decoded JSON objects without trusting ``json.loads``' ``Any`` return."""
    if not isinstance(value, dict):
        return None
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        return None
    return cast(dict[str, object], mapping)
