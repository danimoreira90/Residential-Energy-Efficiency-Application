"""Tests for the LangGraph chat spine — mocked LLM, real routing (Task 0.5 — RED first).

All tests mock _llm_with_tools in the nodes module.  No real Anthropic API calls.
"""
from typing import Any
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from energia.chat.state import ChatState


def _make_state(messages: list[Any] | None = None, tokens_used: int = 0) -> ChatState:
    return {
        "messages": messages or [],
        "user_id": "test-user",
        "conversation_id": "test-conv",
        "tokens_used": tokens_used,
    }


def test_graph_runs_single_turn_with_no_tool_calls(mocker: Any) -> None:
    """Mocked LLM returns plain AIMessage — graph ends after agent node."""
    ai_response = AIMessage(
        content="Olá! Posso ajudar.",
        usage_metadata={"input_tokens": 100, "output_tokens": 30, "total_tokens": 130},
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = ai_response
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    result = GRAPH.invoke(_make_state([HumanMessage(content="Oi")]))

    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == "Olá! Posso ajudar."
    assert result["tokens_used"] == 130


def test_graph_runs_tool_use_loop(mocker: Any) -> None:
    """Mocked LLM requests hello_world; graph routes through tool_node then back."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call_abc", "name": "hello_world", "args": {"name": "Daniel"}}],
        usage_metadata={"input_tokens": 200, "output_tokens": 50, "total_tokens": 250},
    )
    final_msg = AIMessage(
        content="Olá, Daniel!",
        usage_metadata={"input_tokens": 300, "output_tokens": 40, "total_tokens": 340},
    )
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [tool_call_msg, final_msg]
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    result = GRAPH.invoke(_make_state([HumanMessage(content="Me chama de Daniel")]))

    assert mock_llm.invoke.call_count == 2
    assert isinstance(result["messages"][-1], AIMessage)
    assert result["tokens_used"] == 590  # (200+50) + (300+40)


def test_graph_accumulates_tokens_across_turns(mocker: Any) -> None:
    """Each agent_node call adds usage_metadata delta to state.tokens_used."""
    turn = AIMessage(
        content="Turno 1",
        usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = turn
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    result = GRAPH.invoke(_make_state([HumanMessage(content="Primeira mensagem")], tokens_used=50))
    # 50 pre-existing + (100+50) from this turn
    assert result["tokens_used"] == 200


def test_graph_handles_tool_error_gracefully(mocker: Any) -> None:
    """Tool raises — ToolNode returns ToolMessage with error; graph continues."""
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call_err", "name": "hello_world", "args": {"name": "x"}}],
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    )
    narration_msg = AIMessage(
        content="Ocorreu um erro na ferramenta.",
        usage_metadata={"input_tokens": 200, "output_tokens": 30, "total_tokens": 230},
    )
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [tool_call_msg, narration_msg]
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    # Patch the underlying func field (a Pydantic field — unlike .invoke which is a method)
    from energia.chat.tools.hello import hello_world_tool

    def _always_fail(**kwargs: Any) -> Any:
        raise ValueError("Tool blew up")

    mocker.patch.object(hello_world_tool, "func", new=_always_fail)

    from energia.chat.graph import GRAPH

    result = GRAPH.invoke(_make_state([HumanMessage(content="Trigger error")]))

    # Graph must not raise — ToolNode catches the error via handle_tool_errors=True
    assert isinstance(result["messages"][-1], AIMessage)
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_msgs) >= 1
    assert mock_llm.invoke.call_count == 2
