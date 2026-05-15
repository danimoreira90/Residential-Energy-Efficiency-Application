"""Build and export the compiled LangGraph StateGraph for the chatbot."""
from typing import Any

from langgraph.graph import END, START, StateGraph

from energia.chat.nodes import agent_node, route_after_agent, tool_node
from energia.chat.state import ChatState

_graph: Any = None


def build_graph() -> Any:
    g: StateGraph[ChatState] = StateGraph(ChatState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "end": END},
    )
    g.add_edge("tools", "agent")
    return g.compile()


def get_graph() -> Any:
    """Return the compiled graph, building it on first call."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def __getattr__(name: str) -> Any:
    """Lazy GRAPH attribute — constructed on first access, not at import time."""
    if name == "GRAPH":
        return get_graph()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
