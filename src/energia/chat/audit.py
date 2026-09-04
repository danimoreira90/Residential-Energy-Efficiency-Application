"""DuckDBAuditCallback — logs every tool call to tool_calls table (HR-5).

HR-6: PII patterns are redacted from inputs before storage.
HR-5: every tool invocation creates a synthetic assistant message + tool_call row.
"""
import json
import logging
import re
import unicodedata
from collections.abc import Mapping
from decimal import Decimal, DecimalException
from typing import Any, cast
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler

from energia.db import connect
from energia.solar.payback import decimal_within_model_bounds, is_identity_shaped_numeric

logger = logging.getLogger(__name__)

_SOLAR_PAYBACK_INPUT_FIELDS = (
    "monthly_consumption_kwh",
    "monthly_generation_kwh",
    "system_cost_brl",
    "distributor",
    "connection_year",
    "connection_type",
    "real_tariff_inflation_rate",
    "annual_generation_degradation_rate",
)
_ENEL_RJ_DISTRIBUTORS = {
    "enel distribuicao rio": "Enel Distribuição Rio",
    "enel rio": "Enel Rio",
    "enel brasil": "Enel Brasil",
    "enel rj": "Enel RJ",
}
_DISTRIBUTOR_REDACTED = "[DISTRIBUTOR-REDACTED]"
_SOLAR_PAYBACK_INPUT_REDACTED = "[SOLAR-PAYBACK-INPUT-REDACTED]"
_SOLAR_PAYBACK_ERROR = (
    "Não consegui calcular o retorno solar com as premissas fornecidas. "
    "Revise os dados e tente novamente."
)
_SOLAR_PAYBACK_CONNECTION_TYPES = {
    "monofasica_ou_bifasica_2_condutores",
    "bifasica_3_condutores",
    "trifasica",
}


def _normalize_distributor(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return without_accents.casefold().strip()


def _sanitize_solar_payback_input(
    input_str: str,
    inputs: Mapping[str, object] | None = None,
) -> str:
    """Allowlist model inputs before the pre-validation audit write."""
    def validated_decimal(value: object) -> Decimal | None:
        if (
            isinstance(value, bool)
            or is_identity_shaped_numeric(value)
            or not isinstance(value, Decimal | int | float | str)
        ):
            return None
        try:
            number = Decimal(str(value))
        except (DecimalException, ValueError):
            return None
        return number if decimal_within_model_bounds(number) else None

    if isinstance(inputs, Mapping):
        payload = inputs
    else:
        try:
            parsed: object = json.loads(input_str)
        except (TypeError, ValueError):
            return _SOLAR_PAYBACK_INPUT_REDACTED
        if not isinstance(parsed, dict):
            return _SOLAR_PAYBACK_INPUT_REDACTED
        payload = cast(dict[str, object], parsed)

    if any(field not in payload for field in _SOLAR_PAYBACK_INPUT_FIELDS[:6]):
        return _SOLAR_PAYBACK_INPUT_REDACTED

    consumption = validated_decimal(payload["monthly_consumption_kwh"])
    system_cost = validated_decimal(payload["system_cost_brl"])
    generation_input = payload["monthly_generation_kwh"]
    distributor = payload["distributor"]
    connection_year = payload["connection_year"]
    connection_type = payload["connection_type"]
    if not isinstance(generation_input, list):
        return _SOLAR_PAYBACK_INPUT_REDACTED
    generation_values = cast(list[object], generation_input)
    if (
        consumption is None
        or consumption <= 0
        or system_cost is None
        or system_cost <= 0
        or len(generation_values) != 12
        or not isinstance(distributor, str)
        or not distributor.strip()
        or len(distributor.strip()) > 100
        or is_identity_shaped_numeric(connection_year)
        or type(connection_year) is not int
        or connection_year < 2023
        or not isinstance(connection_type, str)
        or connection_type not in _SOLAR_PAYBACK_CONNECTION_TYPES
    ):
        return _SOLAR_PAYBACK_INPUT_REDACTED

    generation: list[Decimal] = []
    for item in generation_values:
        number = validated_decimal(item)
        if number is None or number < 0:
            return _SOLAR_PAYBACK_INPUT_REDACTED
        generation.append(number)
    if not any(number > 0 for number in generation):
        return _SOLAR_PAYBACK_INPUT_REDACTED

    clean: dict[str, object] = {
        "monthly_consumption_kwh": str(consumption),
        "monthly_generation_kwh": [str(number) for number in generation],
        "system_cost_brl": str(system_cost),
        "distributor": _ENEL_RJ_DISTRIBUTORS.get(
            _normalize_distributor(distributor), _DISTRIBUTOR_REDACTED
        ),
        "connection_year": connection_year,
        "connection_type": connection_type,
    }
    for field in _SOLAR_PAYBACK_INPUT_FIELDS[6:]:
        if field not in payload:
            continue
        rate = validated_decimal(payload[field])
        if rate is None or not Decimal("0") <= rate < Decimal("1"):
            return _SOLAR_PAYBACK_INPUT_REDACTED
        clean[field] = str(rate)
    return json.dumps(clean, ensure_ascii=False, allow_nan=False)


class PIIScrubber:
    """Scrubs PII patterns from strings before audit storage (HR-6).

    Owns all redaction patterns and the scrub() method. Add new patterns here;
    DuckDBAuditCallback delegates to this class and stays ignorant of PII specifics.
    """

    _CPF_PATTERN: re.Pattern[str] = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")

    # AF-05: installation_number (UC) — Enel Rio bills use 6-12 digit strings.
    # Pattern A matches the JSON field value: "installation_number": "<digits>"
    # Requires quoted digits so bare integers (kWh, R$) are never matched.
    _UC_JSON_PATTERN: re.Pattern[str] = re.compile(
        r'("installation_number"\s*:\s*")\d{6,12}(")',
        re.IGNORECASE,
    )
    # Pattern B matches text-label forms: "UC: <digits>" or "instalação nº: <digits>".
    # The mandatory prefix prevents accidental hits on consumption or price values.
    _UC_LABEL_PATTERN: re.Pattern[str] = re.compile(
        r"((?:instalação(?:\s+n[oº]?)?\s*:|UC\s*:)\s*)\d{6,12}",
        re.IGNORECASE,
    )

    # AF-solar (Sprint 3 Task 3.2, spec F10): latitude/longitude can identify a
    # residence. Matches the key (quoted JSON, single-quoted Python-repr, or
    # bare key=value) followed by ":" or "=" and a numeric value (optionally
    # quoted). Only the coordinate KEYS below trigger redaction — unrelated
    # numeric fields (consumption, tilt, retry counts, ...) are left alone.
    # Numeric token: optional sign, integer/decimal or leading-dot decimal,
    # optional scientific exponent (e.g. +12.3456, .5, 1e-05, -98.7654).
    _COORDINATE_NUMBER: str = r"[+-]?(?:\d+\.\d+|\.\d+|\d+)(?:[eE][+-]?\d+)?"
    _COORDINATE_PATTERN: re.Pattern[str] = re.compile(
        r"""(?i)(["']?\b(?:latitude|longitude|lat|lon)\b["']?\s*[:=]\s*)"""
        r"""(Decimal\((["'])""" + _COORDINATE_NUMBER + r"""\3\)"""
        r"""|(["']?)""" + _COORDINATE_NUMBER + r"""\4)"""
    )

    def scrub(self, text: str) -> str:
        """Return text with all known PII patterns replaced by placeholders."""
        text = self._CPF_PATTERN.sub("[CPF-REDACTED]", text)
        text = self._UC_JSON_PATTERN.sub(r"\1[UC-REDACTED]\2", text)
        text = self._UC_LABEL_PATTERN.sub(r"\1[UC-REDACTED]", text)
        text = self._COORDINATE_PATTERN.sub(r"\1[COORDINATE-REDACTED]", text)
        return text


class DuckDBAuditCallback(BaseCallbackHandler):
    """Logs every tool call to the tool_calls DuckDB table.

    On on_tool_start a synthetic assistant message is created to satisfy the
    messages.id FK constraint, then a tool_calls row is inserted.
    on_tool_end / on_tool_error update that row with output or error text.
    """

    def __init__(self, conversation_id: str, db_path: str | None = None) -> None:
        super().__init__()
        self._conversation_id = conversation_id
        self._db_path = db_path
        self._run_to_call_id: dict[str, str] = {}
        self._solar_payback_run_ids: set[str] = set()
        self._scrubber = PIIScrubber()

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        tool_name = str(serialized.get("name", "unknown"))
        clean_input = self._scrubber.scrub(
            _sanitize_solar_payback_input(input_str, inputs)
            if tool_name == "solar_payback"
            else input_str
        )

        con = connect(self._db_path)
        try:
            msg_row = con.execute(
                "INSERT INTO messages (conversation_id, role, content) "
                "VALUES (?, 'assistant', ?) RETURNING id",
                [self._conversation_id, f"[tool: {tool_name}]"],
            ).fetchone()
            if msg_row is None:
                logger.error("Failed to insert synthetic message for tool %s", tool_name)
                return
            message_id = str(msg_row[0])

            call_row = con.execute(
                "INSERT INTO tool_calls (message_id, tool_name, input_json) "
                "VALUES (?, ?, ?) RETURNING id",
                [message_id, tool_name, clean_input],
            ).fetchone()
            if call_row is None:
                logger.error("Failed to insert tool_call row for %s", tool_name)
                return
            run_key = str(run_id)
            self._run_to_call_id[run_key] = str(call_row[0])
            if tool_name == "solar_payback":
                self._solar_payback_run_ids.add(run_key)
        finally:
            con.close()

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        call_id = self._run_to_call_id.pop(run_key, None)
        self._solar_payback_run_ids.discard(run_key)
        if call_id is None:
            return
        clean_output = self._scrubber.scrub(str(output))
        con = connect(self._db_path)
        try:
            con.execute(
                "UPDATE tool_calls SET output_json = ? WHERE id = ?",
                [clean_output, call_id],
            )
        finally:
            con.close()

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        run_key = str(run_id)
        call_id = self._run_to_call_id.pop(run_key, None)
        is_solar_payback = run_key in self._solar_payback_run_ids
        self._solar_payback_run_ids.discard(run_key)
        if call_id is None:
            return
        clean_error = (
            _SOLAR_PAYBACK_ERROR
            if is_solar_payback
            else self._scrubber.scrub(str(error))
        )
        con = connect(self._db_path)
        try:
            con.execute(
                "UPDATE tool_calls SET error = ? WHERE id = ?",
                [clean_error, call_id],
            )
        finally:
            con.close()
