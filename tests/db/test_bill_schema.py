"""Tests for Task 1.1 — bill schema migration (TDD — written RED-first).

Uses the same tmp_path-scoped DuckDB + isolated migrations pattern as
test_migrations.py so tests never touch data/energia.duckdb.
"""
import shutil
import uuid
from pathlib import Path

import duckdb
import pytest

from energia.db import migrate

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"

# New columns that 20260511_0001_bill_schema.sql should add to the bills table.
# Keys: column name  →  expected data_type string from information_schema.columns.
EXPECTED_NEW_COLUMNS: dict[str, str] = {
    # DuckDB stores TEXT as VARCHAR in information_schema.columns — both are aliases.
    "installation_number": "VARCHAR",
    "issue_date": "DATE",
    "due_date": "DATE",
    "tariff_group": "VARCHAR",
    "modalidade": "VARCHAR",
    "composition_json": "JSON",
    "confidence": "DOUBLE",
    "needs_user_confirmation": "BOOLEAN",
    "confirmed_at": "TIMESTAMP WITH TIME ZONE",
}


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """Fresh DuckDB file + isolated copy of all migrations for one test run."""
    db_path = str(tmp_path / "test_energia.duckdb")
    migrations_copy = tmp_path / "migrations"
    migrations_copy.mkdir()
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        shutil.copy(f, migrations_copy / f.name)
    return {"db_path": db_path, "migrations_dir": str(migrations_copy)}


def test_bill_schema_adds_all_new_columns(env: dict[str, str]) -> None:
    """After both migrations, bills has all 9 new columns with correct types."""
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])

    con = duckdb.connect(env["db_path"])
    rows = con.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'bills'
        """
    ).fetchall()
    con.close()

    actual: dict[str, str] = {str(r[0]): str(r[1]) for r in rows}

    for col_name, expected_type in EXPECTED_NEW_COLUMNS.items():
        assert col_name in actual, f"Column '{col_name}' missing from bills table"
        assert actual[col_name] == expected_type, (
            f"Column '{col_name}': expected type '{expected_type}', "
            f"got '{actual[col_name]}'"
        )


def test_bill_schema_defaults_are_applied(env: dict[str, str]) -> None:
    """Rows inserted without the new columns get correct default values."""
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])

    con = duckdb.connect(env["db_path"])

    # Seed a user so the FK on bills.user_id is satisfied.
    con.execute("INSERT INTO users (session_id) VALUES ('test-session')")
    user_row = con.execute(
        "SELECT id FROM users WHERE session_id = 'test-session'"
    ).fetchone()
    assert user_row is not None
    user_id: str = str(user_row[0])

    # Insert a bill using only the original (Sprint 0) columns.
    bill_id = str(uuid.uuid4())
    con.execute(
        """
        INSERT INTO bills
            (id, user_id, bill_hash, period, distributor,
             consumption_kwh, total_brl, raw_extraction)
        VALUES
            (?, ?, 'hash-abc', '2025-01', 'Enel Rio', 312.0, 287.40, '{}')
        """,
        [bill_id, user_id],
    )

    row = con.execute(
        """
        SELECT needs_user_confirmation, confidence, composition_json
        FROM bills
        WHERE id = ?
        """,
        [bill_id],
    ).fetchone()
    con.close()

    assert row is not None
    needs_confirmation, confidence, composition_json = row

    assert needs_confirmation is False, (
        f"needs_user_confirmation should default to FALSE, got {needs_confirmation!r}"
    )
    assert confidence == 1.0, (
        f"confidence should default to 1.0, got {confidence!r}"
    )
    # DuckDB JSON columns may return a dict or string depending on version.
    assert composition_json is not None, "composition_json must not be NULL"
    assert composition_json in ({}, "{}"), (
        f"composition_json should default to empty object, got {composition_json!r}"
    )


def test_bill_schema_creates_distributor_period_index(env: dict[str, str]) -> None:
    """Migration creates idx_bills_distributor_period on bills(distributor, period)."""
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])

    con = duckdb.connect(env["db_path"])
    rows = con.execute(
        "SELECT index_name FROM duckdb_indexes WHERE table_name = 'bills'"
    ).fetchall()
    con.close()

    index_names = {str(r[0]) for r in rows}
    assert "idx_bills_distributor_period" in index_names, (
        f"Expected 'idx_bills_distributor_period' in bill indexes, "
        f"found: {index_names}"
    )
