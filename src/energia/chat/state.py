"""ChatState TypedDict — shared state threaded through every LangGraph node."""
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    tokens_used: int
    tokens_in: NotRequired[int]  # absent in legacy/test states; defaults to 0 in agent_node
