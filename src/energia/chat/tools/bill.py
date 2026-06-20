"""parse_bill — wraps energia.bill.parser.parse_bill_image as a LangChain tool.

Design (Option A — InjectedState):
- The LLM sees zero args. Image bytes and media type are read from
  ChatState.pending_bill_image (populated by the Streamlit uploader — Stage C).
- The tool returns a Command that, on every consumed-attachment exit path,
  clears pending_bill_image via update={"pending_bill_image": None}.
- The structural guarantee (HR-6) is that the LLM cannot synthesize bill bytes
  in a tool-call JSON arg — they never appear in the LLM-visible schema.

Hash-cache (Task 1.4):
- Before calling the vision API, we hash the image bytes with SHA-256 and
  consult ``bill_store.find_by_hash`` for the (user_id, hash) pair. A hit
  returns the previously-parsed Bill, skipping the API call entirely. A miss
  falls through to parse_bill_image then ``bill_store.insert``. Insert
  failures do not break the response — the parse already succeeded and the
  user should still see their bill; the cache is a perf/cost optimization,
  not a correctness gate. Logs from this module are PII-free (hash prefix /
  generic status only — never bill fields or UC).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from energia.bill import store as bill_store
from energia.bill.parser import BillParseError, parse_bill_image
from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool

logger = logging.getLogger(__name__)

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

    user_id = state["user_id"]
    bill_hash = hashlib.sha256(pending["image_bytes"]).hexdigest()

    cached = bill_store.find_by_hash(user_id=user_id, bill_hash=bill_hash)
    if cached is not None:
        cache_marker = " (lido da memória local — sem nova consulta de visão)"
        needs_confirmation = cached.confidence < 0.85
        confirm_note = (
            " (confirme os dados com o usuário antes de prosseguir)"
            if needs_confirmation
            else ""
        )
        narration = (
            f"Conta interpretada: distribuidora {cached.distributor}, "
            f"UC {cached.installation_number}, período {cached.period}, "
            f"consumo {cached.consumption_kwh} kWh, "
            f"total R$ {cached.total_brl}{cache_marker}{confirm_note}."
        )
        msg = ToolMessage(content=narration, tool_call_id=tool_call_id)
        return Command(
            update={
                "messages": [msg],
                "pending_bill_image": None,
                "current_bill": cached.model_dump(mode="json"),
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
    # Cache for future repeat uploads. Insert failures must NOT surface as
    # parse errors — the user's bill is already valid; the cache is an
    # optimization. Logged PII-free: hash prefix only, never bill fields.
    try:
        bill_store.insert(user_id=user_id, bill=bill, bill_hash=bill_hash)
    except Exception:
        logger.warning(
            "bill_store.insert failed for hash prefix=%s… — continuing without cache",
            bill_hash[:8],
        )

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
