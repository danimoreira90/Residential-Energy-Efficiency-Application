"""Tests for energia.chat.memory — all four persistence functions."""
from unittest.mock import MagicMock, patch

import duckdb
import pytest

from energia.chat.memory import (
    mint_conversation,
    mint_user,
    save_message,
    update_token_totals,
)


def _mock_connection(mock_con: MagicMock) -> MagicMock:
    """Return a mock for energia.db.connection that yields mock_con as the context value."""
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_con
    mock_ctx.__exit__.return_value = False
    mock_fn = MagicMock(return_value=mock_ctx)
    return mock_fn


# ── mint_user ────────────────────────────────────────────────────────────────


def test_mint_user_creates_new_user_and_returns_uuid(tmp_db: dict[str, str]) -> None:
    user_id = mint_user("brand-new-session", db_path=tmp_db["db_path"])
    assert len(user_id) == 36


def test_mint_user_is_idempotent_for_same_session_id(tmp_db: dict[str, str]) -> None:
    first = mint_user("repeated-session", db_path=tmp_db["db_path"])
    second = mint_user("repeated-session", db_path=tmp_db["db_path"])
    assert first == second


def test_mint_user_raises_when_insert_returns_no_row() -> None:
    mock_con = MagicMock()
    # SELECT → None (user absent); INSERT RETURNING → None (simulated DB failure)
    mock_con.execute.return_value.fetchone.side_effect = [None, None]
    with patch("energia.chat.memory.connection", _mock_connection(mock_con)):
        with pytest.raises(RuntimeError, match="Failed to create user"):
            mint_user("ghost-session")


# ── mint_conversation ────────────────────────────────────────────────────────


def test_mint_conversation_creates_row_and_returns_uuid(tmp_db: dict[str, str]) -> None:
    conv_id = mint_conversation(tmp_db["user_id"], db_path=tmp_db["db_path"])
    assert len(conv_id) == 36


def test_mint_conversation_raises_when_insert_returns_no_row() -> None:
    mock_con = MagicMock()
    mock_con.execute.return_value.fetchone.return_value = None
    with patch("energia.chat.memory.connection", _mock_connection(mock_con)):
        with pytest.raises(RuntimeError, match="Failed to create conversation"):
            mint_conversation("ghost-user-id")


# ── save_message ─────────────────────────────────────────────────────────────


def test_save_message_returns_uuid(tmp_db: dict[str, str]) -> None:
    msg_id = save_message(
        tmp_db["conversation_id"],
        "user",
        "Qual minha conta de energia?",
        db_path=tmp_db["db_path"],
    )
    assert len(msg_id) == 36


def test_save_message_stores_correct_content(tmp_db: dict[str, str]) -> None:
    content = "Minha conta foi de R$ 320,00."
    msg_id = save_message(
        tmp_db["conversation_id"],
        "assistant",
        content,
        db_path=tmp_db["db_path"],
    )
    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT content FROM messages WHERE id = ?", [msg_id]).fetchone()
    con.close()
    assert row is not None
    assert row[0] == content


def test_save_message_raises_when_insert_returns_no_row() -> None:
    mock_con = MagicMock()
    mock_con.execute.return_value.fetchone.return_value = None
    with patch("energia.chat.memory.connection", _mock_connection(mock_con)):
        with pytest.raises(RuntimeError, match="Failed to insert message"):
            save_message("ghost-conv-id", "user", "hello")


# ── update_token_totals ──────────────────────────────────────────────────────


def test_update_token_totals_stores_real_tokens_in(tmp_db: dict[str, str]) -> None:
    """total_tokens_in must reflect the value passed — not hardcoded zero (AF-08 guard)."""
    update_token_totals(
        tmp_db["conversation_id"],
        tokens_in=150,
        tokens_out=80,
        db_path=tmp_db["db_path"],
    )
    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute(
        "SELECT total_tokens_in, total_tokens_out FROM conversations WHERE id = ?",
        [tmp_db["conversation_id"]],
    ).fetchone()
    con.close()
    assert row is not None
    assert row[0] == 150
    assert row[1] == 80


def test_update_token_totals_accumulates_across_calls(tmp_db: dict[str, str]) -> None:
    update_token_totals(
        tmp_db["conversation_id"], tokens_in=100, tokens_out=50,
        db_path=tmp_db["db_path"],
    )
    update_token_totals(
        tmp_db["conversation_id"], tokens_in=200, tokens_out=75,
        db_path=tmp_db["db_path"],
    )
    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute(
        "SELECT total_tokens_in, total_tokens_out FROM conversations WHERE id = ?",
        [tmp_db["conversation_id"]],
    ).fetchone()
    con.close()
    assert row is not None
    assert row[0] == 300
    assert row[1] == 125
