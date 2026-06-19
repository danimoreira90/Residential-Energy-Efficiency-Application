"""parse_bill — wraps energia.bill.parser.parse_bill_image as a LangChain tool.

Design (Option A — InjectedState):
- The LLM sees zero args. Image bytes and media type are read from
  ChatState.pending_bill_image (populated by the Streamlit uploader — Stage C).
- The tool returns a Command that, on every consumed-attachment exit path,
  clears pending_bill_image via update={"pending_bill_image": None}.
- The structural guarantee (HR-6) is that the LLM cannot synthesize bill bytes
  in a tool-call JSON arg — they never appear in the LLM-visible schema.
"""
from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from energia.bill.parser import BillParseError, parse_bill_image
from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool

_NO_ATTACHMENT_MSG = (
    "Nenhuma imagem de conta anexada nesta sessão. "
    "Peça ao usuário para anexar a foto da conta de luz pelo uploader antes de tentar novamente."
)


@tool("parse_bill")
def parse_bill_tool(
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command[Any]:
    """Lê a imagem da conta de luz anexada pelo usuário e extrai os dados estruturados.

    Sem argumentos visíveis para o modelo: a imagem é lida do estado da conversa,
    populado quando o usuário anexa o arquivo pelo uploader. Retorna a conta
    interpretada (distribuidora, UC, período, consumo, total) ou uma mensagem
    pedindo upload se nenhuma imagem está anexada.
    """
    pending = state.get("pending_bill_image")
    if not pending:
        return Command(
            update={
                "messages": [
                    ToolMessage(content=_NO_ATTACHMENT_MSG, tool_call_id=tool_call_id),
                ],
            }
        )

    try:
        result = parse_bill_image(pending["image_bytes"], pending["media_type"])
    except BillParseError as exc:
        err_msg = ToolMessage(
            content=(
                f"Falha ao interpretar a conta: {exc}. "
                "Peça nova foto, melhor iluminada e enquadrada."
            ),
            tool_call_id=tool_call_id,
        )
        return Command(update={"messages": [err_msg], "pending_bill_image": None})

    bill = result.bill
    confirm_note = (
        " (confirme os dados com o usuário antes de prosseguir)"
        if result.needs_user_confirmation
        else ""
    )
    narration = (
        f"Conta interpretada: distribuidora {bill.distributor}, "
        f"UC {bill.installation_number}, período {bill.period}, "
        f"consumo {bill.consumption_kwh} kWh, total R$ {bill.total_brl}{confirm_note}."
    )
    msg = ToolMessage(content=narration, tool_call_id=tool_call_id)
    return Command(
        update={
            "messages": [msg],
            "pending_bill_image": None,
            # Stored as JSON-primitive dict — never a Bill instance — so the
            # MemorySaver checkpoint stays serializer-safe. Consumers
            # rehydrate via Bill.model_validate(...).
            "current_bill": bill.model_dump(mode="json"),
        }
    )


register_tool(parse_bill_tool)  # type: ignore[arg-type]
