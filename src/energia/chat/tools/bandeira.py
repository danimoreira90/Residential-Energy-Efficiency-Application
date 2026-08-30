"""Offline Bandeira Tarifária lookup tools backed by the reviewed snapshot."""
from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import Field

from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool
from energia.tariff.bandeira import BandeiraRecord
from energia.tariff.bandeira import bandeira_history as lookup_bandeira_history
from energia.tariff.bandeira import current_bandeira as lookup_current_bandeira

_OUTSIDE_REVIEW_MSG = (
    "Não tenho uma bandeira revisada para essa data. Não vou informar valores."
)


def _message(content: str, tool_call_id: str) -> Command[Any]:
    return Command(update={"messages": [ToolMessage(content=content, tool_call_id=tool_call_id)]})


def _payload(record: BandeiraRecord) -> dict[str, Any]:
    return record.model_dump(mode="json")


@tool("current_bandeira")
def current_bandeira_tool(
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    as_of: date,
) -> Command[Any]:
    """Retorna a bandeira tarifária de uma data no recorte revisado.

    Use quando o usuário perguntar qual bandeira está em vigor em um mês. A
    resposta contém somente os dados do recorte local revisado pela ANEEL.

    Args:
      as_of: data de referência no formato YYYY-MM-DD.
    """
    del state
    record = lookup_current_bandeira(as_of)
    if record is None:
        return _message(_OUTSIDE_REVIEW_MSG, tool_call_id)
    return _message(
        "Bandeira tarifária do recorte revisado:\n"
        + json.dumps(_payload(record), ensure_ascii=False),
        tool_call_id,
    )


@tool("bandeira_history")
def bandeira_history_tool(
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    as_of: date,
    months: Annotated[int, Field(ge=1, le=12)] = 12,
) -> Command[Any]:
    """Retorna o histórico da bandeira tarifária no recorte revisado.

    Use quando o usuário pedir a sequência recente de bandeiras. A resposta
    só cobre a janela local revisada pela ANEEL e não completa meses ausentes.

    Args:
      as_of: data final de referência no formato YYYY-MM-DD.
      months: quantidade de meses do histórico, limitada ao recorte revisado.
    """
    del state
    records = lookup_bandeira_history(as_of, months)
    if not records:
        return _message(_OUTSIDE_REVIEW_MSG, tool_call_id)
    return _message(
        "Histórico de bandeiras tarifárias do recorte revisado:\n"
        + json.dumps({"records": [_payload(record) for record in records]}, ensure_ascii=False),
        tool_call_id,
    )


register_tool(current_bandeira_tool)  # type: ignore[arg-type]
register_tool(bandeira_history_tool)  # type: ignore[arg-type]
