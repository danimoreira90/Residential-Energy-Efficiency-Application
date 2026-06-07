"""Streamlit chat UI — entry point for `uv run streamlit run src/energia/ui/streamlit_app.py`."""
import uuid
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from energia.chat.audit import DuckDBAuditCallback
from energia.chat.budget import TokenBudgetCallback, TokenBudgetExceeded
from energia.chat.graph import GRAPH
from energia.chat.memory import (
    mint_conversation,
    mint_user,
    save_message,
    update_token_totals,
)
from energia.chat.state import BillImageRef
from energia.db import migrate

load_dotenv()

# Apply any pending migrations on every startup — idempotent and fast.
migrate()

# Runtime LLM signal: prefixed onto the HumanMessage sent into the graph when a
# bill image is attached on this turn. Tells the agent to call parse_bill, which
# reads pending_bill_image via InjectedState (Stage B). Does NOT mutate
# src/energia/chat/prompts.py — the global SYSTEM_PROMPT keeps HR-5 discipline
# intact and is prepended by agent_node as long as messages[0] is not a
# SystemMessage. Prefixing the HumanMessage preserves that condition.
_BILL_SIGNAL_PREFIX = (
    "[Anexo: imagem de conta de luz disponível nesta sessão. "
    "Use a ferramenta parse_bill para extrair os dados antes de responder.]\n\n"
)

# Browsers (and some OSes) send the non-standard `image/jpg` MIME for .jpg
# files. parse_bill_image only accepts `image/jpeg`, so normalize before
# constructing BillImageRef. Everything else passes through unchanged.
_MIME_OVERRIDES: dict[str, str] = {"image/jpg": "image/jpeg"}


def _normalize_media_type(mime: str) -> str:
    """Map non-standard MIMEs (e.g., image/jpg) to parser-accepted equivalents."""
    return _MIME_OVERRIDES.get(mime, mime)


def _bootstrap_session() -> None:
    """Initialise all required st.session_state keys on first page load."""
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = mint_user(str(st.session_state["session_id"]))
    if "conversation_id" not in st.session_state:
        st.session_state["conversation_id"] = mint_conversation(
            str(st.session_state["user_id"])
        )
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "budget_cb" not in st.session_state:
        st.session_state["budget_cb"] = TokenBudgetCallback()


def _render_history() -> None:
    """Render all previous messages from st.session_state."""
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def handle_message(
    user_input: str,
    user_id: str,
    conversation_id: str,
    budget_cb: TokenBudgetCallback,
    db_path: str | None = None,
    bill_image: BillImageRef | None = None,
) -> tuple[str, int, int]:
    """Invoke GRAPH and return (ai_content, tokens_used, tokens_in).

    When `bill_image` is provided, the user's HumanMessage gets the parse_bill
    signal prefix and `pending_bill_image` is set on graph_state so the
    parse_bill tool can read it via InjectedState. Returns a safe fallback
    tuple if TokenBudgetExceeded is raised.
    """
    audit_cb = DuckDBAuditCallback(conversation_id=conversation_id, db_path=db_path)
    content = (_BILL_SIGNAL_PREFIX + user_input) if bill_image is not None else user_input
    graph_state: dict[str, Any] = {
        "messages": [HumanMessage(content=content)],
        "user_id": user_id,
        "conversation_id": conversation_id,
        "tokens_used": 0,
        "tokens_in": 0,
    }
    if bill_image is not None:
        graph_state["pending_bill_image"] = bill_image
    try:
        result = GRAPH.invoke(graph_state, config={"callbacks": [audit_cb, budget_cb]})
        ai_content: str = str(result["messages"][-1].content)
        tokens_used: int = int(result["tokens_used"])
        tokens_in: int = int(result["tokens_in"])
    except TokenBudgetExceeded:
        ai_content = (
            "Desculpe, atingimos o limite de tokens desta sessão. "
            "Por favor, recarregue a página para iniciar uma nova conversa."
        )
        tokens_used = 0
        tokens_in = 0
    return ai_content, tokens_used, tokens_in


# ── Page layout and event loop ───────────────────────────────────────────────

st.set_page_config(page_title="Assistente de Energia", page_icon="⚡")
st.title("⚡ Assistente de Eficiência Energética")

_bootstrap_session()
_render_history()

# Bill image upload — populated into pending_bill_image on the next user turn.
# Streamlit's file_uploader retains the file across reruns; dedup via the
# upload's stable file_id (with name+size as fallback) so the same image is
# not re-injected on every subsequent chat turn.
uploaded_file = st.file_uploader(
    "Anexe a foto da conta de luz (JPG, PNG, GIF, WebP):",
    type=["jpg", "jpeg", "png", "gif", "webp"],
)

bill_image_to_send: BillImageRef | None = None
pending_upload_key: Any = None
if uploaded_file is not None:
    upload_key: Any = getattr(uploaded_file, "file_id", None) or (
        uploaded_file.name,
        uploaded_file.size,
    )
    if st.session_state.get("consumed_bill_upload_key") != upload_key:
        bill_image_to_send = {
            "image_bytes": uploaded_file.getvalue(),
            "media_type": _normalize_media_type(uploaded_file.type or ""),
        }
        pending_upload_key = upload_key

if user_input := st.chat_input("Olá! Como posso ajudar com sua conta de energia?"):
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    save_message(
        str(st.session_state["conversation_id"]),
        "user",
        user_input,
    )

    ai_content, tokens_used, tokens_in = handle_message(
        user_input,
        str(st.session_state["user_id"]),
        str(st.session_state["conversation_id"]),
        st.session_state["budget_cb"],
        bill_image=bill_image_to_send,
    )

    # Mark this upload consumed after handle_message returns — success or
    # budget-exceeded. The user clears or replaces the file to retry.
    if pending_upload_key is not None:
        st.session_state["consumed_bill_upload_key"] = pending_upload_key

    st.session_state["messages"].append({"role": "assistant", "content": ai_content})
    with st.chat_message("assistant"):
        st.markdown(ai_content)

    save_message(
        str(st.session_state["conversation_id"]),
        "assistant",
        ai_content,
    )
    if tokens_used > 0:
        update_token_totals(
            str(st.session_state["conversation_id"]),
            tokens_in=tokens_in,
            tokens_out=tokens_used - tokens_in,
        )
