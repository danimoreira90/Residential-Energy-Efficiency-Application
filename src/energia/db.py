"""DuckDB connection management.

Provides a single-call connection helper used across the application.
The full forward-only migration runner (Task 0.4) and schema (Task 0.4)
are added in the next task on branch data/initial-schema.

CAP statement: CP — local embedded DB; consistency enforced by DuckDB WAL.
See ADR-003 for trade-off rationale.
"""

import duckdb


def connect(path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection.

    Args:
        path: Filesystem path to the DuckDB file.  Pass None (or omit) for
              an in-memory connection suitable for isolated tests.

    Returns:
        An open DuckDB connection.
    """
    from energia.config import settings

    db_path = path if path is not None else settings.duckdb_path
    return duckdb.connect(db_path)
