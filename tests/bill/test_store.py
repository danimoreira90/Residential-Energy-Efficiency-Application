"""bill_store — persistence + hash-cache (Task 1.4, RED first).

Mirrors the chat/memory.py persistence pattern: each function takes an
optional ``db_path`` and uses ``connection()`` from ``energia.db``. Tests use
the ``tmp_db`` fixture from ``tests/conftest.py`` — a fresh DuckDB with the
two existing migrations applied and a seeded user.

What this file pins:
- ``insert(user_id, bill, bill_hash)`` returns a UUID; the row is queryable.
- ``find_by_hash`` returns ``None`` for misses and a fully validated ``Bill``
  for hits (rehydrated from the ``raw_extraction`` JSON column).
- The WHERE-user_id contract: a hash inserted for user A does NOT return for
  user B, even though ``bill_hash`` is globally UNIQUE at the column level.
- Insert idempotency: ``ON CONFLICT (bill_hash) DO NOTHING`` followed by a
  SELECT returns the existing row's id (PLAN.md line 663).
- ``composition`` round-trips both as ``None`` (TD-014 path) and non-None.

No real Anthropic API calls. No mocks of the DB — these are integration tests
against a tmp DuckDB.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb

from energia.bill.store import find_by_hash, insert
from energia.models import Bill, BillComposition


def _make_bill(
    *,
    distributor: str = "Enel Rio",
    installation_number: str = "987654",
    period: str = "2026-03",
    consumption_kwh: str = "312.50",
    total_brl: str = "287.40",
    composition: BillComposition | None = None,
    confidence: float = 0.95,
) -> Bill:
    return Bill(
        distributor=distributor,
        installation_number=installation_number,
        period=period,
        issue_date=date(2026, 3, 10),
        due_date=date(2026, 3, 20),
        consumption_kwh=Decimal(consumption_kwh),
        tariff_group="B1",
        modalidade="Convencional",
        bandeira="Verde",
        total_brl=Decimal(total_brl),
        composition=composition,
        confidence=confidence,
    )


def _make_composition() -> BillComposition:
    return BillComposition(
        tusd=Decimal("120.00"),
        te=Decimal("100.00"),
        icms=Decimal("55.00"),
    )


def _hash(suffix: str = "default") -> str:
    """Build a deterministic 64-hex placeholder hash for tests."""
    return ("a" * 56) + f"{abs(hash(suffix)):>08x}"[-8:]


def _make_second_user(db_path: str) -> str:
    con = duckdb.connect(db_path)
    row = con.execute(
        "INSERT INTO users (session_id) VALUES ('test-second-user') RETURNING id"
    ).fetchone()
    con.close()
    assert row is not None
    return str(row[0])


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


def test_insert_persists_bill_and_returns_id(tmp_db: dict[str, str]) -> None:
    """insert returns a non-empty UUID and the row is queryable by hash."""
    bill = _make_bill(composition=_make_composition())
    bill_hash = _hash("persist")

    bill_id = insert(
        user_id=tmp_db["user_id"],
        bill=bill,
        bill_hash=bill_hash,
        db_path=tmp_db["db_path"],
    )

    assert bill_id, "insert must return a non-empty UUID string"

    con = duckdb.connect(tmp_db["db_path"])
    try:
        row = con.execute(
            "SELECT id, bill_hash, distributor, total_brl "
            "FROM bills WHERE bill_hash = ?",
            [bill_hash],
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert str(row[0]) == bill_id
    assert row[1] == bill_hash
    assert row[2] == "Enel Rio"
    assert Decimal(str(row[3])) == Decimal("287.40")


# ---------------------------------------------------------------------------
# find_by_hash
# ---------------------------------------------------------------------------


def test_find_by_hash_returns_none_when_not_present(tmp_db: dict[str, str]) -> None:
    result = find_by_hash(
        user_id=tmp_db["user_id"],
        bill_hash=_hash("never-inserted"),
        db_path=tmp_db["db_path"],
    )
    assert result is None


def test_find_by_hash_returns_validated_bill_round_trip(
    tmp_db: dict[str, str],
) -> None:
    """raw_extraction JSON round-trips into a fully validated Bill instance."""
    original = _make_bill(composition=_make_composition())
    bill_hash = _hash("round-trip")

    insert(
        user_id=tmp_db["user_id"],
        bill=original,
        bill_hash=bill_hash,
        db_path=tmp_db["db_path"],
    )

    found = find_by_hash(
        user_id=tmp_db["user_id"],
        bill_hash=bill_hash,
        db_path=tmp_db["db_path"],
    )

    assert isinstance(found, Bill)
    assert found == original, (
        "rehydrated Bill must equal the original (raw_extraction JSON round-trip)"
    )


def test_find_by_hash_scopes_by_user_id(tmp_db: dict[str, str]) -> None:
    """Hash inserted for user A must NOT return for user B.

    bill_hash is globally UNIQUE at the column level, but the function takes
    user_id and the WHERE filter enforces the per-user contract — this pins
    that contract.
    """
    bill_hash = _hash("scoped")
    insert(
        user_id=tmp_db["user_id"],
        bill=_make_bill(),
        bill_hash=bill_hash,
        db_path=tmp_db["db_path"],
    )
    other_user_id = _make_second_user(tmp_db["db_path"])

    result = find_by_hash(
        user_id=other_user_id,
        bill_hash=bill_hash,
        db_path=tmp_db["db_path"],
    )

    assert result is None, "find_by_hash must NOT cross user boundaries"


# ---------------------------------------------------------------------------
# Idempotency — PLAN.md line 663: ON CONFLICT DO NOTHING; SELECT existing
# ---------------------------------------------------------------------------


def test_insert_idempotent_on_duplicate_hash(tmp_db: dict[str, str]) -> None:
    """Second insert with the same hash returns the existing id; no duplicate row."""
    bill_hash = _hash("dup")
    first_id = insert(
        user_id=tmp_db["user_id"],
        bill=_make_bill(),
        bill_hash=bill_hash,
        db_path=tmp_db["db_path"],
    )
    second_id = insert(
        user_id=tmp_db["user_id"],
        bill=_make_bill(total_brl="999.99"),
        bill_hash=bill_hash,
        db_path=tmp_db["db_path"],
    )

    assert first_id == second_id, "duplicate-hash insert must return the existing id"

    con = duckdb.connect(tmp_db["db_path"])
    try:
        count_row = con.execute(
            "SELECT COUNT(*) FROM bills WHERE bill_hash = ?", [bill_hash]
        ).fetchone()
    finally:
        con.close()
    assert count_row is not None
    assert count_row[0] == 1, "duplicate-hash insert must not create a second row"


# ---------------------------------------------------------------------------
# Composition round-trip — both None (TD-014) and non-None
# ---------------------------------------------------------------------------


def test_insert_round_trips_composition_none_and_non_none(
    tmp_db: dict[str, str],
) -> None:
    """composition=None and composition=BillComposition(...) both round-trip cleanly."""
    bill_none = _make_bill(composition=None)
    hash_none = _hash("comp-none")
    insert(
        user_id=tmp_db["user_id"],
        bill=bill_none,
        bill_hash=hash_none,
        db_path=tmp_db["db_path"],
    )
    found_none = find_by_hash(
        user_id=tmp_db["user_id"],
        bill_hash=hash_none,
        db_path=tmp_db["db_path"],
    )
    assert found_none is not None
    assert found_none.composition is None

    bill_full = _make_bill(composition=_make_composition())
    hash_full = _hash("comp-full")
    insert(
        user_id=tmp_db["user_id"],
        bill=bill_full,
        bill_hash=hash_full,
        db_path=tmp_db["db_path"],
    )
    found_full = find_by_hash(
        user_id=tmp_db["user_id"],
        bill_hash=hash_full,
        db_path=tmp_db["db_path"],
    )
    assert found_full is not None
    assert found_full.composition is not None
    assert found_full.composition.tusd == Decimal("120.00")
