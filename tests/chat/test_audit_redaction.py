"""Redaction guard tests for PIIScrubber and DuckDBAuditCallback (HR-6).

RED-first (TDD): UC tests were written before AF-05 added installation_number
patterns to PIIScrubber. They confirmed failure (UC value reached the scrubber
unchanged) before the implementation was added.
"""
import uuid

import duckdb

from energia.chat.audit import DuckDBAuditCallback, PIIScrubber

# ── CPF — regression guard ────────────────────────────────────────────────────


def test_scrubber_redacts_cpf() -> None:
    """CPF pattern must still be scrubbed after the PIIScrubber split (CC-05)."""
    scrubber = PIIScrubber()
    result = scrubber.scrub('{"cpf": "123.456.789-00", "action": "verify"}')
    assert "123.456.789-00" not in result
    assert "[CPF-REDACTED]" in result


# ── UC — JSON field (Pattern A) ───────────────────────────────────────────────


def test_scrubber_redacts_uc_json_field() -> None:
    """installation_number value inside a JSON tool-input string must be redacted."""
    scrubber = PIIScrubber()
    result = scrubber.scrub('{"installation_number": "1234567890", "period": "2024-01"}')
    assert "1234567890" not in result
    assert "[UC-REDACTED]" in result


# ── UC — text labels (Pattern B) ─────────────────────────────────────────────


def test_scrubber_redacts_uc_label() -> None:
    """'UC: <digits>' label used in bill text must be redacted."""
    scrubber = PIIScrubber()
    result = scrubber.scrub("UC: 1234567890")
    assert "1234567890" not in result
    assert "[UC-REDACTED]" in result


def test_scrubber_redacts_instalacao_label() -> None:
    """'instalação nº: <digits>' label found on Enel Rio bills must be redacted."""
    scrubber = PIIScrubber()
    result = scrubber.scrub("instalação nº: 0098765432")
    assert "0098765432" not in result
    assert "[UC-REDACTED]" in result


# ── Over-match guards ─────────────────────────────────────────────────────────


def test_scrubber_does_not_redact_consumption_kwh() -> None:
    """Realistic consumption_kwh JSON value must pass through the scrubber unchanged."""
    scrubber = PIIScrubber()
    payload = '{"consumption_kwh": 312, "period": "2024-05"}'
    assert scrubber.scrub(payload) == payload


def test_scrubber_does_not_redact_total_brl() -> None:
    """Realistic total_brl JSON value must pass through the scrubber unchanged."""
    scrubber = PIIScrubber()
    payload = '{"total_brl": "198.50", "due_date": "2024-06-10"}'
    assert scrubber.scrub(payload) == payload


# ── Integration: DuckDBAuditCallback ─────────────────────────────────────────


def test_audit_callback_redacts_uc_before_db_write(tmp_db: dict[str, str]) -> None:
    """installation_number in tool input must not reach the tool_calls table."""
    run_id = uuid.uuid4()
    cb = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )
    uc_value = "9876543210"
    cb.on_tool_start(
        serialized={"name": "analyze_bill"},
        input_str=f'{{"installation_number": "{uc_value}", "period": "2024-05"}}',
        run_id=run_id,
    )

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT input_json FROM tool_calls").fetchone()
    con.close()

    assert row is not None
    stored = str(row[0])
    assert uc_value not in stored
    assert "[UC-REDACTED]" in stored
