"""Reviewed, local ANEEL Bandeira Tarifária snapshot reader.

The v1 reader is deliberately offline: it only returns records within the
committed review window and never substitutes a newer or older flag.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

_SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "bandeira.json"


class BandeiraSource(BaseModel):
    """Provenance for the reviewed ANEEL activation dataset slice."""

    resource_id: str
    url: str
    updated: date
    hash_value: str


class BandeiraRecord(BaseModel):
    """A single monthly Bandeira Tarifária activation."""

    period: date
    flag: str
    surcharge_brl_per_kwh: Decimal
    source: BandeiraSource


def _records() -> list[BandeiraRecord]:
    """Read the reviewed snapshot relative to this module, preserving Decimal."""
    raw = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"), parse_float=Decimal)
    source = BandeiraSource.model_validate(raw["source"])
    return [BandeiraRecord(source=source, **record) for record in raw["records"]]


def _period(value: date) -> date:
    return value.replace(day=1)


def current_bandeira(as_of: date) -> BandeiraRecord | None:
    """Return the exact reviewed month, or ``None`` when it is not reviewed."""
    period = _period(as_of)
    return next((record for record in _records() if record.period == period), None)


def bandeira_history(as_of: date, months: int = 12) -> list[BandeiraRecord]:
    """Return chronological reviewed records ending in ``as_of``'s month."""
    if not 1 <= months <= 12:
        raise ValueError("months must be between 1 and 12")

    period = _period(as_of)
    records = _records()
    if not any(record.period == period for record in records):
        return []
    return [record for record in records if record.period <= period][-months:]
