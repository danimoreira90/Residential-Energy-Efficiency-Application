"""bill_store period-lookup tests (Task 1.5, RED first).

A separate file from tests/bill/test_store.py so the existing test file stays
untouched (HR-4 ceremony-free). Uses the root tmp_db fixture.

What this file pins:
- find_by_period misses → None.
- find_by_period hit → fully validated Bill round-trip.
- Multiplicity rule: when a period has 2 rows, find_by_period returns the
  MOST RECENT (ORDER BY created_at DESC LIMIT 1) — newest-row-is-best matches
  the user mental model after correct_bill_field improves accuracy.
- Per-user scoping (same as find_by_hash).
- find_latest_periods returns distinct periods ordered by recency, collapses
  duplicates, respects the n limit.
"""
from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

import duckdb

from energia.bill.store import find_by_period, find_latest_periods, insert
from energia.models import Bill


def _bill(
    *,
    period: str = "2026-03",
    distributor: str = "Enel Rio",
    consumption_kwh: str = "300",
    total_brl: str = "270.00",
) -> Bill:
    return Bill(
        distributor=distributor,
        installation_number="000000",
        period=period,
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 15),
        consumption_kwh=Decimal(consumption_kwh),
        tariff_group="B1",
        modalidade="Convencional",
        bandeira="Verde",
        total_brl=Decimal(total_brl),
        composition=None,
        confidence=0.95,
    )


def _hash(suffix: str) -> str:
    return ("b" * 56) + f"{abs(hash(suffix)):>08x}"[-8:]


def _make_second_user(db_path: str) -> str:
    con = duckdb.connect(db_path)
    row = con.execute(
        "INSERT INTO users (session_id) VALUES ('test-second-user') RETURNING id"
    ).fetchone()
    con.close()
    assert row is not None
    return str(row[0])


# ---------------------------------------------------------------------------
# find_by_period
# ---------------------------------------------------------------------------


def test_find_by_period_returns_none_when_not_present(tmp_db: dict[str, str]) -> None:
    result = find_by_period(
        user_id=tmp_db["user_id"],
        period="2026-03",
        db_path=tmp_db["db_path"],
    )
    assert result is None


def test_find_by_period_returns_validated_bill_round_trip(
    tmp_db: dict[str, str],
) -> None:
    original = _bill(period="2026-03", consumption_kwh="300", total_brl="270.00")
    insert(
        user_id=tmp_db["user_id"],
        bill=original,
        bill_hash=_hash("round-trip"),
        db_path=tmp_db["db_path"],
    )

    found = find_by_period(
        user_id=tmp_db["user_id"],
        period="2026-03",
        db_path=tmp_db["db_path"],
    )

    assert isinstance(found, Bill)
    assert found == original


def test_find_by_period_returns_most_recent_when_multiple_rows(
    tmp_db: dict[str, str],
) -> None:
    """Multiplicity rule: ORDER BY created_at DESC LIMIT 1.

    Two distinct images for the same period → two rows. find_by_period
    returns the second (more recent) row.
    """
    older = _bill(period="2026-03", total_brl="270.00")
    newer = _bill(period="2026-03", total_brl="299.99")

    insert(
        user_id=tmp_db["user_id"],
        bill=older,
        bill_hash=_hash("older"),
        db_path=tmp_db["db_path"],
    )
    # DuckDB's DEFAULT now() resolution is sub-second; nudge the clock so the
    # ordering is unambiguous on fast machines.
    time.sleep(0.01)
    insert(
        user_id=tmp_db["user_id"],
        bill=newer,
        bill_hash=_hash("newer"),
        db_path=tmp_db["db_path"],
    )

    found = find_by_period(
        user_id=tmp_db["user_id"],
        period="2026-03",
        db_path=tmp_db["db_path"],
    )

    assert found is not None
    assert found.total_brl == Decimal("299.99"), (
        "find_by_period must return the most recent row when a period has "
        f"multiple bills; got {found.total_brl}"
    )


def test_find_by_period_scopes_by_user_id(tmp_db: dict[str, str]) -> None:
    insert(
        user_id=tmp_db["user_id"],
        bill=_bill(period="2026-03"),
        bill_hash=_hash("scoped"),
        db_path=tmp_db["db_path"],
    )
    other = _make_second_user(tmp_db["db_path"])

    result = find_by_period(
        user_id=other,
        period="2026-03",
        db_path=tmp_db["db_path"],
    )
    assert result is None


# ---------------------------------------------------------------------------
# find_latest_periods
# ---------------------------------------------------------------------------


def test_find_latest_periods_returns_empty_list_when_no_bills(
    tmp_db: dict[str, str],
) -> None:
    result = find_latest_periods(
        user_id=tmp_db["user_id"], db_path=tmp_db["db_path"]
    )
    assert result == []


def test_find_latest_periods_returns_distinct_periods_ordered_by_recency(
    tmp_db: dict[str, str],
) -> None:
    """Three distinct periods inserted in chronological order → list ordered
    by MAX(created_at) DESC (most-recent-first).
    """
    insert(
        user_id=tmp_db["user_id"],
        bill=_bill(period="2026-01"),
        bill_hash=_hash("p1"),
        db_path=tmp_db["db_path"],
    )
    time.sleep(0.01)
    insert(
        user_id=tmp_db["user_id"],
        bill=_bill(period="2026-02"),
        bill_hash=_hash("p2"),
        db_path=tmp_db["db_path"],
    )
    time.sleep(0.01)
    insert(
        user_id=tmp_db["user_id"],
        bill=_bill(period="2026-03"),
        bill_hash=_hash("p3"),
        db_path=tmp_db["db_path"],
    )

    result = find_latest_periods(
        user_id=tmp_db["user_id"], n=2, db_path=tmp_db["db_path"]
    )

    assert result == ["2026-03", "2026-02"], (
        "find_latest_periods must return the two most-recently-touched distinct "
        f"periods, ordered most-recent-first; got {result}"
    )


def test_find_latest_periods_collapses_duplicate_periods(
    tmp_db: dict[str, str],
) -> None:
    """Two rows for the same period count as one period."""
    insert(
        user_id=tmp_db["user_id"],
        bill=_bill(period="2026-03"),
        bill_hash=_hash("dup-a"),
        db_path=tmp_db["db_path"],
    )
    insert(
        user_id=tmp_db["user_id"],
        bill=_bill(period="2026-03", total_brl="280"),
        bill_hash=_hash("dup-b"),
        db_path=tmp_db["db_path"],
    )

    result = find_latest_periods(
        user_id=tmp_db["user_id"], n=2, db_path=tmp_db["db_path"]
    )

    assert result == ["2026-03"], (
        "duplicate-period rows must collapse to one entry; "
        f"got {result}"
    )
