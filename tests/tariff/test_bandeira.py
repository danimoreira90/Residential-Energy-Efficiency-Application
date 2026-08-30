"""Bandeira snapshot domain tests (Task 2.2, RED first)."""
from datetime import date
from decimal import Decimal

import pytest

from energia.tariff.bandeira import bandeira_history, current_bandeira


def test_current_bandeira_returns_exact_snapshot_record_and_provenance() -> None:
    record = current_bandeira(date(2025, 9, 18))

    assert record is not None
    assert record.period == date(2025, 9, 1)
    assert record.flag == "Vermelha Patamar 2"
    assert record.surcharge_brl_per_kwh == Decimal("0.07877")
    assert record.source.resource_id == "0591b8f6-fe54-437b-b72b-1aa2efd46e42"
    assert record.source.updated == date(2026, 8, 24)
    assert record.source.hash_value == "c098ee1b39e75b28b5ac646e1e9746ca"


def test_current_bandeira_returns_none_outside_reviewed_snapshot() -> None:
    assert current_bandeira(date(2026, 9, 1)) is None


def test_bandeira_history_is_chronological_and_limited_to_snapshot_window() -> None:
    records = bandeira_history(date(2026, 8, 30), months=12)

    assert [record.period for record in records] == [
        date(2025, 9, 1),
        date(2025, 10, 1),
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
        date(2026, 4, 1),
        date(2026, 5, 1),
        date(2026, 6, 1),
        date(2026, 7, 1),
        date(2026, 8, 1),
    ]
    assert [record.surcharge_brl_per_kwh for record in records] == [
        Decimal("0.07877"),
        Decimal("0.04463"),
        Decimal("0.04463"),
        Decimal("0.01885"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0.01885"),
        Decimal("0.01885"),
        Decimal("0.01885"),
        Decimal("0.01885"),
    ]


def test_bandeira_history_returns_available_prefix_for_early_snapshot_month() -> None:
    records = bandeira_history(date(2025, 11, 30), months=12)

    assert [record.period for record in records] == [
        date(2025, 9, 1),
        date(2025, 10, 1),
        date(2025, 11, 1),
    ]


def test_bandeira_history_rejects_month_count_outside_tool_contract() -> None:
    with pytest.raises(ValueError, match="between 1 and 12"):
        bandeira_history(date(2026, 8, 30), months=0)
