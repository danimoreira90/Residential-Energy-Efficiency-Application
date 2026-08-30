"""Offline Tarifa Branca simulation tool for the reviewed Enel RJ snapshot."""
from __future__ import annotations

import json
import unicodedata
from decimal import Decimal
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool
from energia.tariff.branca import BrancaProfileError, simulate_tarifa_branca
from energia.tariff.snapshot import TariffSnapshot, load_snapshot


def _message(content: str, tool_call_id: str) -> Command[Any]:
    return Command(update={"messages": [ToolMessage(content=content, tool_call_id=tool_call_id)]})


def _normalize(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return without_accents.casefold().strip()


def _matches_enel_rj(distributor: str, snapshot: TariffSnapshot) -> bool:
    return any(
        _normalize(distributor) == _normalize(candidate)
        for candidate in (snapshot.distributor, *snapshot.aliases)
    )


def _out_of_scope_message() -> str:
    return (
        "Ainda não tenho uma comparação revisada para essa distribuidora. "
        "Não vou estimar valores."
    )


def _invalid_profile_message() -> str:
    return (
        "Preciso de um perfil de consumo válido, sem valores negativos e com "
        "consumo total positivo. Não vou estimar valores."
    )


@tool("simulate_tarifa_branca")
def simulate_tarifa_branca_tool(
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    distributor: str,
    ponta_kwh: Decimal,
    intermediaria_kwh: Decimal,
    fora_ponta_kwh: Decimal,
) -> Command[Any]:
    """Compara Tarifa Convencional e Tarifa Branca para a Enel RJ.

    Use quando o usuário fornecer o consumo em kWh de ponta, intermediária e
    fora de ponta e quiser avaliar a Tarifa Branca. A comparação usa somente
    TUSD+TE do recorte regulatório revisado; exclui impostos, COSIP e Bandeira.

    Args:
      distributor: distribuidora do usuário. A comparação revisada só cobre a Enel RJ.
      ponta_kwh: consumo mensal no horário de ponta, em kWh.
      intermediaria_kwh: consumo mensal no horário intermediário, em kWh.
      fora_ponta_kwh: consumo mensal fora de ponta, em kWh.
    """
    del state
    snapshot = load_snapshot("enel_rj")
    if not _matches_enel_rj(distributor, snapshot):
        return _message(_out_of_scope_message(), tool_call_id)

    try:
        comparison = simulate_tarifa_branca(ponta_kwh, intermediaria_kwh, fora_ponta_kwh)
    except BrancaProfileError:
        return _message(_invalid_profile_message(), tool_call_id)

    header = (
        "Comparação revisada de Tarifa Convencional e Tarifa Branca (TUSD + TE). "
        "Exclui impostos, COSIP e Bandeira Tarifária.\n"
    )
    return _message(
        header + json.dumps(comparison.model_dump(mode="json"), ensure_ascii=False),
        tool_call_id,
    )


register_tool(simulate_tarifa_branca_tool)  # type: ignore[arg-type]
