"""Streamlit chat UI — entry point for `uv run streamlit run src/energia/ui/streamlit_app.py`."""
import uuid
from typing import Any

import streamlit as st

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

# Apply any pending migrations on every startup — idempotent and fast.
migrate()

st.set_page_config(page_title="Assistente de Energia", page_icon="⚡")
st.title("⚡ Assistente de Eficiência Energética")

# ── Session bootstrap ────────────────────────────────────────────────────────

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

# ── Render chat history ──────────────────────────────────────────────────────

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ───────────────────────────────────────────────────────────────

if user_input := st.chat_input("Olá! Como posso ajudar com sua conta de energia?"):
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    save_message(
        str(st.session_state["conversation_id"]),
        "user",
        user_input,
    )

    conversation_id: str = str(st.session_state["conversation_id"])
    budget_cb: TokenBudgetCallback = st.session_state["budget_cb"]
    audit_cb = DuckDBAuditCallback(conversation_id=conversation_id)

    from langchain_core.messages import HumanMessage

    graph_state: dict[str, Any] = {
        "messages": [HumanMessage(content=user_input)],
        "user_id": str(st.session_state["user_id"]),
        "conversation_id": conversation_id,
        "tokens_used": 0,
    }

    try:
        result = GRAPH.invoke(graph_state, config={"callbacks": [audit_cb, budget_cb]})
        ai_content: str = str(result["messages"][-1].content)
        tokens_used: int = int(result["tokens_used"])
    except TokenBudgetExceeded:
        ai_content = (
            "Desculpe, atingimos o limite de tokens desta sessão. "
            "Por favor, recarregue a página para iniciar uma nova conversa."
        )
        tokens_used = 0

    st.session_state["messages"].append({"role": "assistant", "content": ai_content})
    with st.chat_message("assistant"):
        st.markdown(ai_content)

    save_message(conversation_id, "assistant", ai_content)
    if tokens_used > 0:
        update_token_totals(conversation_id, tokens_in=0, tokens_out=tokens_used)
