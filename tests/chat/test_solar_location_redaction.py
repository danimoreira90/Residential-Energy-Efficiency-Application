"""RED contracts for coordinate redaction in the local tool audit."""
from __future__ import annotations

import uuid

import duckdb
import pytest

from energia.chat.audit import DuckDBAuditCallback, PIIScrubber

_LATITUDE = "12.3456"
_LONGITUDE = "-98.7654"
_MARKER = "[COORDINATE-REDACTED]"


@pytest.mark.parametrize(
    "payload",
    [
        '{"latitude": 12.3456, "longitude": -98.7654, '
        '"monthly_consumption_kwh": 450, "roof_tilt_deg": 20}',
        '{"lat": "12.3456", "lon": "-98.7654", '
        '"monthly_consumption_kwh": 450, "roof_tilt_deg": 20}',
        "{'latitude': 12.3456, 'lon': -98.7654, "
        "'monthly_consumption_kwh': 450, 'roof_tilt_deg': 20}",
    ],
)
def test_scrubber_redacts_coordinate_fields_only(payload: str) -> None:
    scrubbed = PIIScrubber().scrub(payload)
    assert _LATITUDE not in scrubbed and _LONGITUDE not in scrubbed
    assert _MARKER in scrubbed
    assert "monthly_consumption_kwh" in scrubbed and "450" in scrubbed
    assert "roof_tilt_deg" in scrubbed and "20" in scrubbed


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("lat=+12.3456", f"lat={_MARKER}"),
        ("longitude=.5", f"longitude={_MARKER}"),
        ('{"latitude": 1e-05}', f'{{"latitude": {_MARKER}}}'),
        ("{'longitude': Decimal('-98.7654')}", f"{{'longitude': {_MARKER}}}"),
    ],
)
def test_scrubber_redacts_complete_numeric_coordinate_tokens(
    payload: str,
    expected: str,
) -> None:
    assert PIIScrubber().scrub(payload) == expected


def _callback(tmp_db: dict[str, str]) -> DuckDBAuditCallback:
    return DuckDBAuditCallback(
        conversation_id=tmp_db["conversation_id"],
        db_path=tmp_db["db_path"],
    )


def test_tool_start_stores_redacted_coordinates_and_other_numbers(
    tmp_db: dict[str, str],
) -> None:
    callback = _callback(tmp_db)
    callback.on_tool_start(
        serialized={"name": "estimate_solar_system"},
        input_str=(
            '{"latitude": 1e-05, "longitude": +98.7654, '
            '"monthly_consumption_kwh": 450, "roof_tilt_deg": 20}'
        ),
        run_id=uuid.uuid4(),
    )
    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT input_json FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    stored = str(row[0])
    assert "e-05" not in stored and "+98.7654" not in stored
    assert _MARKER in stored and "450" in stored and "20" in stored


def test_tool_end_stores_redacted_coordinates_and_other_numbers(
    tmp_db: dict[str, str],
) -> None:
    callback = _callback(tmp_db)
    run_id = uuid.uuid4()
    callback.on_tool_start(
        serialized={"name": "estimate_solar_system"},
        input_str="{}",
        run_id=run_id,
    )
    callback.on_tool_end(
        output='{"latitude": 1e-05, "annual_generation_kwh": 1234.56}',
        run_id=run_id,
    )
    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT output_json FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    stored = str(row[0])
    assert "e-05" not in stored
    assert _MARKER in stored and "1234.56" in stored


def test_tool_error_stores_scrubbed_text_and_preserves_unrelated_number(
    tmp_db: dict[str, str],
) -> None:
    callback = _callback(tmp_db)
    run_id = uuid.uuid4()
    callback.on_tool_start(
        serialized={"name": "estimate_solar_system"},
        input_str="{}",
        run_id=run_id,
    )
    callback.on_tool_error(
        error=RuntimeError("lat=+12.3456, lon=.5, retry_count=3"),
        run_id=run_id,
    )
    con = duckdb.connect(tmp_db["db_path"])
    row = con.execute("SELECT error FROM tool_calls").fetchone()
    con.close()
    assert row is not None
    stored = str(row[0])
    assert "+12.3456" not in stored and ".5" not in stored
    assert _MARKER in stored and "retry_count=3" in stored
