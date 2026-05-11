"""LangGraph nodes: agent_node, tool_node, and route_after_agent."""
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.prebuilt import ToolNode

from energia.chat.prompts import SYSTEM_PROMPT
from energia.chat.state import ChatState
from energia.chat.tools import ALL_TOOLS
from energia.config import settings

_llm = ChatAnthropic(model_name=settings.anthropic_model, max_tokens_to_sample=4096)  # type: ignore[call-arg]
_llm_with_tools = _llm.bind_tools(ALL_TOOLS)

tool_node = ToolNode(ALL_TOOLS, handle_tool_errors=True)


def agent_node(state: ChatState) -> dict[str, Any]:
    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
    response = _llm_with_tools.invoke(messages)
    usage_delta = 0
    if isinstance(response, AIMessage) and response.usage_metadata is not None:  # type: ignore[reportUnnecessaryIsInstance]
        usage_delta = (
            response.usage_metadata["input_tokens"]
            + response.usage_metadata["output_tokens"]
        )
    return {"messages": [response], "tokens_used": state["tokens_used"] + usage_delta}


def route_after_agent(state: ChatState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"
