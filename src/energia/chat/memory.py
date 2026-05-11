"""Conversation persistence helpers — thin wrappers around DuckDB operations.

Each function opens and closes its own connection so callers don't need to
manage connection lifecycle. All use RETURNING id for atomic insert+fetch.
"""
from energia.db import connect


def mint_user(session_id: str, db_path: str | None = None) -> str:
    """Return the UUID of the user for session_id, creating a row if needed."""
    con = connect(db_path)
    try:
        row = con.execute(
            "SELECT id FROM users WHERE session_id = ?", [session_id]
        ).fetchone()
        if row is not None:
            return str(row[0])
        new_row = con.execute(
            "INSERT INTO users (session_id) VALUES (?) RETURNING id",
            [session_id],
        ).fetchone()
        if new_row is None:
            raise RuntimeError(f"Failed to create user for session_id={session_id!r}")
        return str(new_row[0])
    finally:
        con.close()


def mint_conversation(user_id: str, db_path: str | None = None) -> str:
    """Create a new conversation row and return its UUID."""
    con = connect(db_path)
    try:
        row = con.execute(
            "INSERT INTO conversations (user_id) VALUES (?) RETURNING id",
            [user_id],
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to create conversation for user_id={user_id!r}")
        return str(row[0])
    finally:
        con.close()


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    db_path: str | None = None,
) -> str:
    """Insert a message row and return its UUID."""
    con = connect(db_path)
    try:
        row = con.execute(
            "INSERT INTO messages (conversation_id, role, content) "
            "VALUES (?, ?, ?) RETURNING id",
            [conversation_id, role, content],
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to insert message")
        return str(row[0])
    finally:
        con.close()


def update_token_totals(
    conversation_id: str,
    tokens_in: int,
    tokens_out: int,
    db_path: str | None = None,
) -> None:
    """Increment total_tokens_in and total_tokens_out for a conversation."""
    con = connect(db_path)
    try:
        con.execute(
            "UPDATE conversations "
            "SET total_tokens_in  = total_tokens_in  + ?, "
            "    total_tokens_out = total_tokens_out + ? "
            "WHERE id = ?",
            [tokens_in, tokens_out, conversation_id],
        )
    finally:
        con.close()
