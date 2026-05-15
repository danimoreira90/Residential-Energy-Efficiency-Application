"""DuckDB connection management and forward-only migration runner.

CAP statement: CP — local embedded DB; consistency enforced by DuckDB WAL.
See ADR-003 for trade-off rationale.

Usage:
    python -m energia.db migrate
"""

import hashlib
import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# Default migrations directory: <repo_root>/migrations/ relative to this file.
# src/energia/db.py → ../../../migrations
_MIGRATIONS_DEFAULT = Path(__file__).parent.parent.parent / "migrations"


class MigrationIntegrityError(Exception):
    """Raised when a previously-applied migration file has been modified (HR-3)."""


@contextmanager
def connection(path: str | None = None) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Context manager that opens a DuckDB connection and closes it on exit."""
    con = connect(path)
    try:
        yield con
    finally:
        con.close()


def connect(path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection.

    Args:
        path: Filesystem path to the DuckDB file.  Pass None (or omit) to use
              the path from Settings (``settings.duckdb_path``).

    Returns:
        An open DuckDB connection.
    """
    from energia.config import settings

    db_path = path if path is not None else settings.duckdb_path
    return duckdb.connect(db_path)


def _sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ensure_schema_migrations(con: duckdb.DuckDBPyConnection) -> None:
    """Create the schema_migrations bookkeeping table if it does not exist."""
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name        TEXT        PRIMARY KEY,
            sha256      TEXT        NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def migrate(
    db_path: str | None = None,
    migrations_dir: str | Path | None = None,
) -> None:
    """Apply pending *.sql migrations in lexicographic order.

    For each migration file:
    - Already recorded: verifies the stored SHA-256 matches the file (HR-3).
    - Not yet recorded: applies the SQL in a transaction then records it.

    Idempotent: safe to call on every application startup.

    Args:
        db_path: Path to DuckDB file.  Defaults to ``settings.duckdb_path``.
        migrations_dir: Directory containing *.sql files.
                        Defaults to ``<repo_root>/migrations/``.

    Raises:
        MigrationIntegrityError: A recorded migration's file content has changed.
    """
    mdir = Path(migrations_dir) if migrations_dir is not None else _MIGRATIONS_DEFAULT

    if not mdir.exists():
        logger.warning("Migrations directory %s does not exist — nothing to apply.", mdir)
        return

    sql_files = sorted(mdir.glob("*.sql"))

    con = connect(db_path)
    try:
        _ensure_schema_migrations(con)

        applied_names: list[str] = []
        for sql_file in sql_files:
            name = sql_file.stem
            sha = _sha256_file(sql_file)

            row = con.execute(
                "SELECT sha256 FROM schema_migrations WHERE name = ?", [name]
            ).fetchone()

            if row is not None:
                stored_sha: str = str(row[0])
                if stored_sha != sha:
                    raise MigrationIntegrityError(
                        f"Migration '{name}' was modified after being applied. "
                        f"stored={stored_sha[:16]}… got={sha[:16]}… — HR-3 violation."
                    )
                continue  # already applied and hash matches

            # New migration — apply atomically in an explicit transaction.
            content = sql_file.read_text(encoding="utf-8")
            con.begin()
            try:
                con.execute(content)
                con.execute(
                    "INSERT INTO schema_migrations (name, sha256) VALUES (?, ?)",
                    [name, sha],
                )
                con.commit()
            except Exception:
                con.rollback()
                raise

            applied_names.append(name)
            logger.info("Applied migration: %s", name)

        if applied_names:
            count = len(applied_names)
            suffix = "s" if count != 1 else ""
            names_str = ", ".join(applied_names)
            print(f"Applied {count} migration{suffix}: {names_str}")
        else:
            logger.debug("No new migrations to apply.")
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "migrate":
        migrate()
    else:
        print("Usage: python -m energia.db migrate", file=sys.stderr)
        sys.exit(1)
