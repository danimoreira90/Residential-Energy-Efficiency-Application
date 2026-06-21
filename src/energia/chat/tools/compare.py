"""compare_bill_periods — period-over-period comparison LangChain tool.

Reports WHAT moved (consumption Δ, cost Δ, blended effective-rate Δ) between
two stored bills. Does NOT report WHY — causal decomposition into tariff /
bandeira / tax requires authoritative ANEEL data (Sprint 2, Task 2.3) and is
deferred to a Task 1.5 amendment (TD-018).

Auto-pick: when both ``period_a`` and ``period_b`` are omitted, the tool uses
the two most-recently-touched distinct periods from ``bill_store``. Explicit:
when both are passed, the tool fetches those specific periods. Mixed input
(one given, one None) is treated as a usage error and returns a graceful
ToolMessage asking for both.

HR-5: every not-enough-bills branch returns a ToolMessage with NO synthesized
numbers — no kWh, no R$, no %. The function never invents a comparison.

HR-6: this module's logger emits period strings only — never UC, consumption,
or total. The bill payload returned in the ToolMessage already lives in the
local checkpoint via the existing parse_bill flow; sending it back out via a
LangChain message is consistent with how parse_bill itself returns parsed
fields for narration.
"""
from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from energia.bill import store as bill_store
from energia.bill.analysis import compute_period_comparison
from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool

logger = logging.getLogger(__name__)


_NO_BILLS_MSG = (
    "Você ainda não tem nenhuma conta cadastrada. "
    "Anexe pelo menos duas contas de períodos diferentes para eu poder comparar."
)


def _only_one_period_msg(period: str) -> str:
    return (
        f"Só tem uma conta cadastrada (período {period}). "
        "Anexe pelo menos uma conta de outro período para eu poder comparar."
    )


def _same_period_msg(period: str) -> str:
    return (
        f"Os dois períodos pedidos são iguais ({period}). "
        "Escolha dois períodos diferentes para comparar."
    )


def _missing_period_msg(period: str) -> str:
    return (
        f"Não tenho conta cadastrada para o período {period}. "
        "Anexe essa conta antes de pedir a comparação."
    )


def _explicit_args_incomplete_msg() -> str:
    return (
        "Para uma comparação explícita preciso de DOIS períodos "
        "(YYYY-MM cada). Ou omita os dois para eu comparar as duas contas "
        "mais recentes."
    )


@tool("compare_bill_periods")
def compare_bill_periods(
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    period_a: str | None = None,
    period_b: str | None = None,
) -> Command[Any]:
    """Compara duas contas de energia pelo período (formato YYYY-MM).

    Use quando o usuário quiser ver como o consumo, o custo ou a taxa
    efetiva (R$/kWh blended) mudaram entre dois meses. Exemplos de quando
    chamar: "compara minha conta de abril com a de maio", "minha conta
    subiu, dá pra ver?".

    Args:
      period_a: primeiro período (YYYY-MM) OU None para escolher automaticamente
        as duas contas mais recentes.
      period_b: segundo período (YYYY-MM) OU None (junto com period_a None) para
        a comparação automática.

    A ferramenta SÓ reporta o que mudou (Δ consumo, Δ custo, Δ taxa efetiva),
    NUNCA o porquê — decomposição causal (tarifa vs bandeira vs imposto) exige
    dados de tarifa ANEEL que não temos em v1.
    """
    user_id = state["user_id"]

    if (period_a is None) != (period_b is None):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=_explicit_args_incomplete_msg(),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    if period_a is None and period_b is None:
        latest = bill_store.find_latest_periods(user_id=user_id, n=2)
        if len(latest) == 0:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=_NO_BILLS_MSG, tool_call_id=tool_call_id
                        )
                    ],
                }
            )
        if len(latest) == 1:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=_only_one_period_msg(latest[0]),
                            tool_call_id=tool_call_id,
                        )
                    ],
                }
            )
        period_a, period_b = latest[0], latest[1]
        logger.info("auto-comparison picked periods a=%s b=%s", period_a, period_b)

    assert period_a is not None and period_b is not None
    if period_a == period_b:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=_same_period_msg(period_a),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    earlier_period, later_period = sorted([period_a, period_b])
    earlier_bill = bill_store.find_by_period(user_id=user_id, period=earlier_period)
    later_bill = bill_store.find_by_period(user_id=user_id, period=later_period)

    if earlier_bill is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=_missing_period_msg(earlier_period),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    if later_bill is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=_missing_period_msg(later_period),
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    comparison = compute_period_comparison(
        earlier=earlier_bill, later=later_bill
    )
    header = f"Comparação {earlier_period} → {later_period}:\n"
    body = json.dumps(comparison.model_dump(mode="json"), ensure_ascii=False)
    logger.info(
        "comparison emitted for periods a=%s b=%s", earlier_period, later_period
    )
    return Command(
        update={
            "messages": [
                ToolMessage(content=header + body, tool_call_id=tool_call_id)
            ],
        }
    )


register_tool(compare_bill_periods)  # type: ignore[arg-type]
