"""LGPD regression for pre-validation solar-payback audit input."""
from __future__ import annotations

import uuid

import duckdb
import pytest

from energia.chat.audit import DuckDBAuditCallback

_SAFE_ERROR = (
    "Não consegui calcular o retorno solar com as premissas fornecidas. "
    "Revise os dados e tente novamente."
)


def _valid_payload() -> dict[str, object]:
    return {
        "monthly_consumption_kwh": "100",
        "monthly_generation_kwh": ["100"] * 12,
        "system_cost_brl": "1000",
        "distributor": "Enel Rio",
        "connection_year": 2026,
        "connection_type": "trifasica",
        "real_tariff_inflation_rate": "0.05",
        "annual_generation_degradation_rate": "0.005",
    }


def test_solar_payback_audit_drops_unknown_and_sensitive_input(
    tmp_db: dict[str, str],
) -> None:
    callback = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )
    payload = {
        **_valid_payload(),
        "distributor": "synthetic-unsupported-distributor",
        "address": "synthetic-home-address-marker",
        "cpf": "00000000000",
        "cnpj": "00000000000000",
    }

    callback.on_tool_start(
        serialized={"name": "solar_payback"},
        input_str=str(payload),
        run_id=uuid.uuid4(),
        inputs=payload,
    )

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT input_json FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    stored = str(row[0])
    assert "monthly_consumption_kwh" in stored and "100" in stored
    assert "synthetic-home-address-marker" not in stored
    assert "00000000000" not in stored
    assert "00000000000000" not in stored
    assert "synthetic-unsupported-distributor" not in stored
    assert "[DISTRIBUTOR-REDACTED]" in stored


def test_solar_payback_audit_rejects_sensitive_values_in_allowlisted_fields(
    tmp_db: dict[str, str],
) -> None:
    callback = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )
    payload: dict[str, object] = {
        "monthly_consumption_kwh": "00000000000",
        "monthly_generation_kwh": ["synthetic-home-address-marker"] * 12,
        "system_cost_brl": "00000000000000",
        "distributor": "Enel Rio",
        "connection_year": 2026,
        "connection_type": "trifasica",
        "real_tariff_inflation_rate": "0.05",
        "annual_generation_degradation_rate": "0.005",
    }

    callback.on_tool_start(
        serialized={"name": "solar_payback"},
        input_str=str(payload),
        run_id=uuid.uuid4(),
        inputs=payload,
    )

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT input_json FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    assert str(row[0]) == "[SOLAR-PAYBACK-INPUT-REDACTED]"


@pytest.mark.parametrize(
    "changes",
    [
        {"monthly_consumption_kwh": "99999999999"},
        {"monthly_consumption_kwh": " 99999999999 "},
        {"monthly_generation_kwh": ["99999999999"] + ["100"] * 11},
        {"system_cost_brl": "99999999999999"},
        {"system_cost_brl": " 99999999999999 "},
        {"connection_year": 99999999999},
    ],
)
def test_solar_payback_audit_rejects_identity_shaped_numeric_values(
    tmp_db: dict[str, str], changes: dict[str, object]
) -> None:
    callback = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )
    payload = {**_valid_payload(), **changes}

    callback.on_tool_start(
        serialized={"name": "solar_payback"},
        input_str=str(payload),
        run_id=uuid.uuid4(),
        inputs=payload,
    )

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT input_json FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    assert str(row[0]) == "[SOLAR-PAYBACK-INPUT-REDACTED]"


def test_solar_payback_audit_never_stores_framework_exception_text(
    tmp_db: dict[str, str],
) -> None:
    callback = DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )
    payload = _valid_payload()
    run_id = uuid.uuid4()
    callback.on_tool_start(
        serialized={"name": "solar_payback"},
        input_str=str(payload),
        run_id=run_id,
        inputs=payload,
    )
    callback.on_tool_error(
        error=RuntimeError("synthetic-sensitive-framework-error-987"),
        run_id=run_id,
    )

    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT error FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    assert row[0] == _SAFE_ERROR
