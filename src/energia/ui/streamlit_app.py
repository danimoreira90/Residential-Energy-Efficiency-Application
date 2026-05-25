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
from energia.db import migrate

load_dotenv()

# Apply any pending migrations on every startup — idempotent and fast.
migrate()


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
) -> tuple[str, int, int]:
    """Invoke GRAPH and return (ai_content, tokens_used, tokens_in).

    Returns a safe fallback tuple if TokenBudgetExceeded is raised.
    """
    audit_cb = DuckDBAuditCallback(conversation_id=conversation_id, db_path=db_path)
    graph_state: dict[str, Any] = {
        "messages": [HumanMessage(content=user_input)],
        "user_id": user_id,
        "conversation_id": conversation_id,
        "tokens_used": 0,
        "tokens_in": 0,
    }
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
    )

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
