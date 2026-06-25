"""Reader tests for tariff/snapshot.py — load_snapshot + base tariff (RED first).

What this file pins:
- load_snapshot() parses the committed enel_rj.json into a TariffSnapshot
  (distributor == "Enel Distribuição Rio").
- Money fields (tusd / te) are exact Decimal, never float — convencional
  tusd == Decimal("731.72"), te == Decimal("329.38").
- base_tariff_brl_per_kwh("convencional") = (tusd + te) / 1000 ==
  Decimal("1.06110") — the REGULATED base tariff (TUSD + TE), NOT a blended
  effective/consumption rate (contrast bill/analysis.py's effective rate).
- baixa_renda carries v1_supported == False (the subsidized subclass v1 only
  detects + disclaims).
- An unknown slug raises FileNotFoundError.
- Reading resolves relative to the module location, not the CWD — load works
  regardless of where pytest is invoked from.

No network, no cache, no LLM, no ChatState, no DB — pure read + parse + compute.
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

from energia.tariff.snapshot import TariffSnapshot, load_snapshot


def test_load_snapshot_returns_typed_snapshot() -> None:
    snap = load_snapshot("enel_rj")

    assert isinstance(snap, TariffSnapshot)
    assert snap.distributor == "Enel Distribuição Rio"
    assert snap.tariff_group == "B1"
    assert snap.unit == "BRL_per_MWh"


def test_default_slug_is_enel_rj() -> None:
    assert load_snapshot().distributor == "Enel Distribuição Rio"


def test_convencional_tusd_and_te_are_exact_decimal() -> None:
    snap = load_snapshot("enel_rj")
    convencional = snap.subclasses["convencional"]

    assert convencional.tusd == Decimal("731.72")
    assert convencional.te == Decimal("329.38")
    assert isinstance(convencional.tusd, Decimal)
    assert isinstance(convencional.te, Decimal)


def test_base_tariff_is_tusd_plus_te_over_1000() -> None:
    """Regulated base tariff (TUSD + TE) in R$/kWh — exact Decimal, not float."""
    snap = load_snapshot("enel_rj")

    expected = (Decimal("731.72") + Decimal("329.38")) / 1000
    assert expected == Decimal("1.06110")

    base = snap.base_tariff_brl_per_kwh("convencional")
    assert base == Decimal("1.06110")
    assert isinstance(base, Decimal)


def test_baixa_renda_is_not_v1_supported() -> None:
    snap = load_snapshot("enel_rj")

    assert snap.subclasses["baixa_renda"].v1_supported is False


def test_unknown_slug_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_snapshot("does_not_exist")


def test_load_is_independent_of_cwd(tmp_path: Path) -> None:
    """Snapshot resolves relative to the module, so a different CWD still loads."""
    original = Path.cwd()
    os.chdir(tmp_path)
    try:
        snap = load_snapshot("enel_rj")
    finally:
        os.chdir(original)

    assert snap.distributor == "Enel Distribuição Rio"
