"""get_tariff — regulated tariff lookup LangChain tool.

A PURE LOOKUP: distributor + subclass in, the regulated base tariff (TUSD + TE)
or an honest disclaimer out. No DB, no ChatState bill reads, no causal language,
no distributor fallback. Decision record: ADR-005.

Scope (v1): only Enel RJ has a committed snapshot. A distributor that matches
the snapshot's canonical name or any alias (case-insensitive, accent-tolerant)
resolves to slug ``enel_rj``; anything else returns a "fora do escopo" message
that names Enel RJ as the only covered distributor — it NEVER falls back to
Enel's numbers for another distributor.

HR-5 honesty contract:
- The success path returns numbers that come ONLY from
  ``snapshot.base_tariff_brl_per_kwh`` — the regulated TUSD + TE tariff. The
  header states this is the regulated tariff, NOT the blended effective rate
  (``total_brl / consumption_kwh``, see bill/analysis.py + TD-018) and NOT a
  causal explanation of any bill change.
- The baixa_renda (subsidized) branch and the out-of-scope branch carry ZERO
  numbers — no invented or fallback tariff.

HR-6: this module never touches bills. Its logger emits only distributor /
subclass / slug strings — never a UC or any bill field.
"""
from __future__ import annotations

import json
import logging
import unicodedata
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool
from energia.tariff.snapshot import TariffSnapshot, load_snapshot

logger = logging.getLogger(__name__)

# v1 ships exactly one snapshot. Multi-distributor resolution (a slug map or a
# DistributorResolver Protocol) is deferred until a second real snapshot exists
# — see ADR-005 (honest scope) and TD-019.
_V1_SLUG = "enel_rj"
_BAIXA_RENDA = "baixa_renda"


def _normalize(name: str) -> str:
    """Casefold + strip accents so 'Enel Distribuição Rio' matches user input
    like 'enel distribuicao rio' or 'ENEL DISTRIBUIÇÃO RIO'."""
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.casefold().strip()


def _matches_v1_distributor(distributor: str, snapshot: TariffSnapshot) -> bool:
    target = _normalize(distributor)
    candidates = [snapshot.distributor, *snapshot.aliases]
    return any(_normalize(c) == target for c in candidates)


def _msg(content: str, tool_call_id: str) -> Command[Any]:
    return Command(
        update={
            "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
        }
    )


def _out_of_scope_msg(distributor: str) -> str:
    return (
        f"Por enquanto a v1 só tem a tarifa regulada da Enel RJ "
        f"(Enel Distribuição Rio). Não tenho os dados de '{distributor}', "
        f"então não vou estimar nenhum número."
    )


def _baixa_renda_msg() -> str:
    return (
        "A subclasse baixa renda é uma conta subsidiada: o desconto depende de "
        "faixas de consumo e regras específicas que a v1 ainda não calcula. "
        "Posso explicar como funciona, mas não vou estimar a tarifa com desconto."
    )


def _unknown_subclass_msg(subclass: str) -> str:
    return (
        f"Não reconheço a subclasse '{subclass}'. A v1 cobre a subclasse "
        f"convencional (residencial). Não vou estimar um número para uma "
        f"subclasse que não tenho."
    )


@tool("get_tariff")
def get_tariff(
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    distributor: str,
    subclass: str = "convencional",
) -> Command[Any]:
    """Retorna a tarifa regulada (TUSD + TE) de uma distribuidora, em R$/kWh.

    Use quando o usuário perguntar quanto custa a tarifa, qual é a tarifa da
    distribuidora, ou o preço regulado do kWh. Exemplos: "qual a tarifa da
    Enel?", "quanto é o kWh aqui em Maricá?".

    Args:
      distributor: nome da distribuidora (ex.: "Enel Rio", "Enel Distribuição
        Rio"). A v1 só cobre a Enel RJ; outras distribuidoras recebem um aviso
        de fora de escopo, sem número.
      subclass: subclasse tarifária B1. Padrão "convencional". "baixa_renda" é
        subsidiada e a v1 não calcula o desconto — devolve um aviso.

    Devolve a tarifa-base REGULADA (TUSD + TE), que NÃO é a taxa efetiva da
    conta (R$/kWh pago, que mistura tarifa + bandeira + impostos) e NÃO é uma
    explicação de por que uma conta mudou.
    """
    snapshot = load_snapshot(_V1_SLUG)

    if not _matches_v1_distributor(distributor, snapshot):
        logger.info(
            "get_tariff out-of-scope distributor=%s subclass=%s",
            distributor,
            subclass,
        )
        return _msg(_out_of_scope_msg(distributor), tool_call_id)

    tariff = snapshot.subclasses.get(subclass)

    if subclass == _BAIXA_RENDA or (tariff is not None and tariff.v1_supported is False):
        logger.info(
            "get_tariff subsidized-disclaimer distributor=%s subclass=%s slug=%s",
            distributor,
            subclass,
            _V1_SLUG,
        )
        return _msg(_baixa_renda_msg(), tool_call_id)

    if tariff is None:
        logger.info(
            "get_tariff unknown-subclass distributor=%s subclass=%s slug=%s",
            distributor,
            subclass,
            _V1_SLUG,
        )
        return _msg(_unknown_subclass_msg(subclass), tool_call_id)

    rate = snapshot.base_tariff_brl_per_kwh(subclass)
    payload: dict[str, Any] = {
        "distributor": snapshot.distributor,
        "subclass": subclass,
        "resolution": snapshot.source.resolution,
        "effective_from": snapshot.effective_from.isoformat(),
        "base_tariff_brl_per_kwh": str(rate),
    }
    header = (
        f"Tarifa regulada (TUSD + TE) da {snapshot.distributor} — subclasse "
        f"{subclass}. É a tarifa-base regulada, NÃO a taxa efetiva da conta "
        f"(R$/kWh pago) e NÃO uma explicação de variação de conta.\n"
    )
    body = json.dumps(payload, ensure_ascii=False)
    logger.info(
        "get_tariff resolved distributor=%s subclass=%s slug=%s",
        distributor,
        subclass,
        _V1_SLUG,
    )
    return _msg(header + body, tool_call_id)


register_tool(get_tariff)  # type: ignore[arg-type]
