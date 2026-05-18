"""LangGraph nodes: agent_node, tool_node, and route_after_agent."""
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.prebuilt import ToolNode

from energia.chat.prompts import SYSTEM_PROMPT
from energia.chat.state import ChatState
from energia.chat.tools import ALL_TOOLS
from energia.config import settings

# Lazily initialised on first agent_node call — not at import time.
# This prevents ANTHROPIC_API_KEY from being required before load_dotenv()
# has run (CC-01 / AF-01).  Tests patch _llm_with_tools directly; the getter
# returns the patched value unchanged when it is non-None.
_llm: ChatAnthropic | None = None
_llm_with_tools: Any = None

tool_node = ToolNode(ALL_TOOLS, handle_tool_errors=True)


def _get_llm_with_tools() -> Any:
    global _llm, _llm_with_tools
    if _llm_with_tools is None:
        # langchain-anthropic 1.4.3 stubs declare timeout/stop as required args;
        # both have runtime defaults — ignore is legitimate until upstream stubs are fixed.
        _llm = ChatAnthropic(model_name=settings.anthropic_model, max_tokens_to_sample=4096)  # type: ignore[call-arg]
        _llm_with_tools = _llm.bind_tools(ALL_TOOLS)
    return _llm_with_tools


def agent_node(state: ChatState) -> dict[str, Any]:
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
    response = _get_llm_with_tools().invoke(messages)
    input_delta = 0
    usage_delta = 0
    if isinstance(response, AIMessage) and response.usage_metadata is not None:  # type: ignore[reportUnnecessaryIsInstance]
        input_delta = response.usage_metadata["input_tokens"]
        usage_delta = input_delta + response.usage_metadata["output_tokens"]
    return {
        "messages": [response],
        "tokens_used": state["tokens_used"] + usage_delta,
        "tokens_in": state.get("tokens_in", 0) + input_delta,
    }


def route_after_agent(state: ChatState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"
