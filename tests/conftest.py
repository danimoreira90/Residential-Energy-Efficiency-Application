"""Root conftest — fixtures available to all test directories."""
import shutil
from pathlib import Path

import duckdb
import pytest

from energia.db import migrate

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


@pytest.fixture
def tmp_db(tmp_path: Path) -> dict[str, str]:
    """Provide a fresh DuckDB with schema applied and a seeded user+conversation."""
    db_path = str(tmp_path / "test_chat.duckdb")
    migrations_copy = tmp_path / "migrations"
    migrations_copy.mkdir()
    for f in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        shutil.copy(f, migrations_copy / f.name)
    migrate(db_path=db_path, migrations_dir=str(migrations_copy))

    con = duckdb.connect(db_path)
    user_row = con.execute(
        "INSERT INTO users (session_id) VALUES ('test-session') RETURNING id"
    ).fetchone()
    assert user_row is not None
    user_id = str(user_row[0])

    conv_row = con.execute(
        "INSERT INTO conversations (user_id) VALUES (?) RETURNING id",
        [user_id],
    ).fetchone()
    assert conv_row is not None
    conv_id = str(conv_row[0])
    con.close()

    return {"db_path": db_path, "user_id": user_id, "conversation_id": conv_id}
