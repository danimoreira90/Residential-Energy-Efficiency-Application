"""DuckDBAuditCallback — logs every tool call to tool_calls table (HR-5).

HR-6: PII patterns are redacted from inputs before storage.
HR-5: every tool invocation creates a synthetic assistant message + tool_call row.
"""
import logging
import re
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler

from energia.db import connect

logger = logging.getLogger(__name__)


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

    def scrub(self, text: str) -> str:
        """Return text with all known PII patterns replaced by placeholders."""
        text = self._CPF_PATTERN.sub("[CPF-REDACTED]", text)
        text = self._UC_JSON_PATTERN.sub(r"\1[UC-REDACTED]\2", text)
        text = self._UC_LABEL_PATTERN.sub(r"\1[UC-REDACTED]", text)
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
        clean_input = self._scrubber.scrub(input_str)

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
            self._run_to_call_id[str(run_id)] = str(call_row[0])
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
        call_id = self._run_to_call_id.get(str(run_id))
        if call_id is None:
            return
        con = connect(self._db_path)
        try:
            con.execute(
                "UPDATE tool_calls SET output_json = ? WHERE id = ?",
                [str(output), call_id],
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
        call_id = self._run_to_call_id.get(str(run_id))
        if call_id is None:
            return
        con = connect(self._db_path)
        try:
            con.execute(
                "UPDATE tool_calls SET error = ? WHERE id = ?",
                [str(error), call_id],
            )
        finally:
            con.close()
