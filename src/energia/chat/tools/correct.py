"""correct_bill_field — surgical single-field correction on the cached Bill.

When the user says an extracted bill field is wrong and tells the agent the
correct value, the model calls this tool with (field, value). The tool reads
current_bill from ChatState, updates ONLY the named field, re-validates the
resulting Bill, and writes the new Bill back to current_bill. All other fields
remain byte-for-byte identical (HR-5 — never re-emit or guess unspecified
fields; never re-run vision).

PT-BR numeric normalization (consumption_kwh, total_brl only):
- Strip whitespace, leading "R$", trailing "kWh"/"kwh".
- If the value contains a comma, ALL "." are removed (thousands sep) then
  "," → ".". If no comma, "." stays as the decimal sep.
- The normalized string is fed to Bill.model_validate via Pydantic Decimal
  parsing; ValidationError → graceful ToolMessage, state unchanged.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import ValidationError

from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool
from energia.models import Bill

CorrectableField = Literal[
    "distributor",
    "installation_number",
    "period",
    "consumption_kwh",
    "total_brl",
]

_NUMERIC_FIELDS: frozenset[str] = frozenset({"consumption_kwh", "total_brl"})

_NO_BILL_MSG = (
    "Nenhuma conta carregada nesta sessão para corrigir. "
    "Peça ao usuário para anexar a foto da conta primeiro."
)


def _normalize_numeric_ptbr(raw: str) -> str:
    """Normalize a PT-BR numeric string for Decimal parsing.

    Rules:
      - strip whitespace, leading "R$"/"r$", trailing "kWh"/"kwh"
      - if comma present: drop ALL "." (thousands), then "," → "."
      - if no comma: leave "." untouched (already decimal-dot form or integer)
    """
    s = raw.strip()
    # Strip currency / unit decorations
    if s.startswith("R$") or s.startswith("r$"):
        s = s[2:].strip()
    for unit in ("kWh", "kwh"):
        if s.endswith(unit):
            s = s[: -len(unit)].strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return s


@tool("correct_bill_field")
def correct_bill_field(
    field: CorrectableField,
    value: str,
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command[Any]:
    """Corrige um único campo da conta carregada com o valor informado pelo usuário.

    Use esta ferramenta APENAS quando o usuário disser que um campo extraído da
    conta está errado e fornecer o valor correto. Um campo por chamada.

    Mapeamento das menções comuns:
      - "consumo" / "uso" / "kWh" -> consumption_kwh
      - "total" / "valor" -> total_brl
      - "distribuidora" / "concessionária" -> distributor
      - "período" / "mês de referência" -> period
      - "UC" / "instalação" / "número da instalação" -> installation_number

    NUNCA use esta ferramenta para preencher um campo ausente ou inventar dados:
    o valor SEMPRE vem do usuário. Não re-execute a visão. Não altere outros
    campos no processo.

    Args:
      field: nome do campo (um dos cinco listados acima).
      value: novo valor como string. Para campos numéricos, aceita "410,50",
        "1.416,94", "R$ 1.416,94", "312,5 kWh", "374" — a ferramenta normaliza
        a formatação brasileira antes de validar.
    """
    current_bill = state.get("current_bill")
    if current_bill is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(content=_NO_BILL_MSG, tool_call_id=tool_call_id),
                ],
            }
        )

    # current_bill is a JSON-primitive dict (see ChatState docstring) — copy and
    # overwrite the one named field, then re-validate the whole as a Bill so
    # type/regex/Decimal checks fire and HR-5 invariants stay intact.
    candidate: dict[str, Any] = dict(current_bill)
    new_value: Any = (
        _normalize_numeric_ptbr(value) if field in _NUMERIC_FIELDS else value
    )
    candidate[field] = new_value

    try:
        validated = Bill.model_validate(candidate)
    except ValidationError as exc:
        err = (
            f"Valor inválido para o campo '{field}': {value!r}. "
            f"Detalhes: {exc.errors(include_url=False)[0].get('msg', 'validação falhou')}. "
            "Peça ao usuário para confirmar o valor."
        )
        return Command(
            update={
                "messages": [ToolMessage(content=err, tool_call_id=tool_call_id)],
            }
        )

    old_display = current_bill.get(field)
    new_display = getattr(validated, field)
    confirmation = (
        f"Campo '{field}' atualizado: {old_display} -> {new_display}. "
        "Demais campos preservados."
    )
    return Command(
        update={
            "messages": [
                ToolMessage(content=confirmation, tool_call_id=tool_call_id),
            ],
            # Write back as JSON-primitive dict to match the ChatState contract.
            "current_bill": validated.model_dump(mode="json"),
        }
    )


register_tool(correct_bill_field)  # type: ignore[arg-type]
