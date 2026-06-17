"""ChatState TypedDict — shared state threaded through every LangGraph node."""
from typing import Annotated, NotRequired

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# typing_extensions.TypedDict is required (not typing.TypedDict) on Python < 3.12
# because Pydantic introspects ChatState via the parse_bill tool's InjectedState
# annotation and rejects the stdlib variant before 3.12.
from typing_extensions import TypedDict

from energia.models import Bill


class BillImageRef(TypedDict):
    """A pending bill image attached by the user via the Streamlit uploader.

    Populated by the UI layer (Stage C); consumed and cleared by the parse_bill tool.
    Lives in state — never in the LLM's tool-call args — so the model cannot
    synthesize bill bytes (HR-6 / Option A).
    """

    image_bytes: bytes
    media_type: str


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str
    tokens_used: int
    tokens_in: NotRequired[int]  # absent in legacy/test states; defaults to 0 in agent_node
    pending_bill_image: NotRequired[BillImageRef | None]  # set by UI; cleared by parse_bill tool
    # Set by parse_bill success; consumed by correct_bill_field. Lives only in
    # the in-process MemorySaver checkpoint (HR-2/HR-6 — never persisted to disk).
    current_bill: NotRequired[Bill | None]
