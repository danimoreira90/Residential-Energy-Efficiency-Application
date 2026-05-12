"""Migration runner tests for Task 0.4 (TDD — written RED-first).

Each test uses a fresh tmp_path-scoped DuckDB and an isolated copy of
migrations/*.sql so tests never touch data/energia.duckdb and never
interfere with each other.
"""

import hashlib
import shutil
from pathlib import Path

import duckdb
import pytest

from energia.db import MigrationIntegrityError, migrate

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """Return fresh db_path + isolated migrations_dir for one test run."""
    db_path = str(tmp_path / "test_energia.duckdb")
    migrations_copy = tmp_path / "migrations"
    migrations_copy.mkdir()
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        shutil.copy(f, migrations_copy / f.name)
    return {"db_path": db_path, "migrations_dir": str(migrations_copy)}


def test_migrate_creates_tables(env: dict[str, str]) -> None:
    """After migrate(), all 6 expected tables exist in information_schema."""
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])

    con = duckdb.connect(env["db_path"])
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    con.close()

    table_names = {str(r[0]) for r in rows}
    expected = {"users", "conversations", "messages", "tool_calls", "bills", "schema_migrations"}
    assert table_names == expected


def test_migrate_is_idempotent(env: dict[str, str]) -> None:
    """Calling migrate() twice produces no duplicates and does not raise."""
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])

    con = duckdb.connect(env["db_path"])
    count: int = con.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]  # type: ignore[index]
    con.close()

    n_migrations = len(sorted(Path(env["migrations_dir"]).glob("*.sql")))
    assert count == n_migrations


def test_migrate_records_applied_migration(env: dict[str, str]) -> None:
    """schema_migrations records the initial migration with correct sha256."""
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])

    con = duckdb.connect(env["db_path"])
    rows = con.execute("SELECT name, sha256 FROM schema_migrations").fetchall()
    con.close()

    migration_map = {str(r[0]): str(r[1]) for r in rows}
    assert "20260510_0001_initial_schema" in migration_map
    stored_sha: str = migration_map["20260510_0001_initial_schema"]

    sql_file = Path(env["migrations_dir"]) / "20260510_0001_initial_schema.sql"
    expected_sha = hashlib.sha256(sql_file.read_bytes()).hexdigest()
    assert stored_sha == expected_sha


def test_migrate_rejects_modified_applied_migration(env: dict[str, str]) -> None:
    """If a migration file changes after being applied, migrate() raises MigrationIntegrityError."""
    migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])

    # Tamper: append a comment to the migration file in our isolated copy.
    sql_file = Path(env["migrations_dir"]) / "20260510_0001_initial_schema.sql"
    original = sql_file.read_bytes()
    sql_file.write_bytes(original + b"\n-- tampered after apply")

    with pytest.raises(MigrationIntegrityError):
        migrate(db_path=env["db_path"], migrations_dir=env["migrations_dir"])
