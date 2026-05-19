"""Tests for DuckDBAuditCallback (HR-5 + HR-6) — Task 0.5, RED first.

Uses tmp_db fixture from conftest.py — fresh DuckDB with schema + seeded user/conv.
"""
import uuid

import duckdb

from energia.chat.audit import DuckDBAuditCallback


def test_audit_callback_writes_tool_call_to_duckdb(tmp_db: dict[str, str]) -> None:
    """on_tool_start + on_tool_end insert a row in tool_calls with name, input, output."""
    run_id = uuid.uuid4()
    cb = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )

    cb.on_tool_start(
        serialized={"name": "hello_world"},
        input_str='{"name": "Daniel"}',
        run_id=run_id,
    )
    cb.on_tool_end(
        output='{"greeting": "Olá, Daniel!"}',
        run_id=run_id,
    )

    con = duckdb.connect(tmp_db["db_path"])
    rows = con.execute(
        "SELECT tool_name, input_json, output_json FROM tool_calls"
    ).fetchall()
    con.close()

    assert len(rows) == 1
    assert rows[0][0] == "hello_world"
    assert "Daniel" in str(rows[0][1])
    assert rows[0][2] is not None


def test_audit_callback_logs_tool_error(tmp_db: dict[str, str]) -> None:
    """on_tool_error populates the error column in tool_calls."""
    run_id = uuid.uuid4()
    cb = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )

    cb.on_tool_start(
        serialized={"name": "hello_world"},
        input_str='{"name": "Test"}',
        run_id=run_id,
    )
    cb.on_tool_error(
        error=ValueError("Something went wrong"),
        run_id=run_id,
    )

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT error, output_json FROM tool_calls").fetchone()
    con.close()

    assert row is not None
    assert row[0] is not None
    assert "Something went wrong" in str(row[0])
    # output_json stays None when an error occurs
    assert row[1] is None


def test_audit_callback_does_not_log_pii(tmp_db: dict[str, str]) -> None:
    """HR-6 guard: CPF in tool input is redacted before being stored in tool_calls."""
    run_id = uuid.uuid4()
    cb = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )

    cpf_value = "123.456.789-00"
    pii_input = f'{{"nome": "Test User", "cpf": "{cpf_value}", "action": "verify"}}'

    cb.on_tool_start(
        serialized={"name": "verify_identity"},
        input_str=pii_input,
        run_id=run_id,
    )

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT input_json FROM tool_calls").fetchone()
    con.close()

    assert row is not None
    stored = str(row[0])
    assert cpf_value not in stored
    assert "[CPF-REDACTED]" in stored


def test_audit_callback_silent_skip_on_tool_end_without_start(
    tmp_db: dict[str, str],
) -> None:
    """on_tool_end with an unregistered run_id silently returns — no exception, no DB write."""
    cb = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )
    cb.on_tool_end(output='{"result": "ok"}', run_id=uuid.uuid4())

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT COUNT(*) FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    assert row[0] == 0


def test_audit_callback_silent_skip_on_tool_error_without_start(
    tmp_db: dict[str, str],
) -> None:
    """on_tool_error with an unregistered run_id silently returns — no exception, no DB write."""
    cb = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )
    cb.on_tool_error(error=ValueError("unexpected error"), run_id=uuid.uuid4())

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT COUNT(*) FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    assert row[0] == 0
