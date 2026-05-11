"""Tests for ChatState TypedDict and add_messages reducer (Task 0.5 — RED first)."""
from typing import cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages

from energia.chat.state import ChatState


def test_chat_state_messages_append_via_add_messages() -> None:
    """add_messages reducer appends to the list; does not replace it."""
    initial: ChatState = {
        "messages": [HumanMessage(content="Oi")],
        "user_id": "u1",
        "conversation_id": "c1",
        "tokens_used": 0,
    }
    new_msg = AIMessage(content="Olá!")
    # add_messages takes Any sequences; cast ensures pyright knows the result type
    merged = cast(list[BaseMessage], add_messages(initial["messages"], [new_msg]))  # type: ignore[arg-type]
    assert len(merged) == 2
    last = merged[-1]
    assert isinstance(last, AIMessage)
    assert last.content == "Olá!"


def test_chat_state_token_count_accumulates() -> None:
    """tokens_used is a plain int accumulated across turns."""
    state: ChatState = {
        "messages": [],
        "user_id": "u1",
        "conversation_id": "c1",
        "tokens_used": 150,
    }
    state["tokens_used"] += 75
    assert state["tokens_used"] == 225
