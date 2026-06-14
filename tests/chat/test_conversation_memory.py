"""Conversation memory tests — in-process MemorySaver wiring (RED-first).

All tests mock _llm_with_tools in the nodes module. No real Anthropic API calls.
Each test uses its own UUID-suffixed thread_id so the shared MemorySaver instance
behind the cached compiled graph cannot leak state between tests.

RED status today:
- test_memory_accumulates_history_across_turns_with_same_thread_id — RED
  (no checkpointer → no restoration → second LLM call sees only [System, Human2])
- test_memory_isolates_history_between_different_thread_ids — RED
  (A's continuation has no history without a checkpointer)
- test_pending_bill_image_does_not_persist_into_next_turn — RED
  (GRAPH.get_state requires a configured checkpointer; raises today)
- test_eval_runner_passes_unique_thread_id_per_invocation — RED
  (runner.run_example calls GRAPH.invoke(state) with no config today)
- test_per_turn_token_counters_reset_with_input_zero — regression guard
  (passes today AND after; pins the no-reducer last-write-wins contract for
  tokens_used / tokens_in)
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command


def _make_state(
    messages: list[Any] | None = None, tokens_used: int = 0
) -> dict[str, Any]:
    return {
        "messages": messages or [],
        "user_id": "test-user",
        "conversation_id": "test-conv",
        "tokens_used": tokens_used,
        "tokens_in": 0,
    }


def _ai(content: str = "ok", input_t: int = 10, output_t: int = 5) -> AIMessage:
    return AIMessage(
        content=content,
        usage_metadata={
            "input_tokens": input_t,
            "output_tokens": output_t,
            "total_tokens": input_t + output_t,
        },
    )


def test_memory_accumulates_history_across_turns_with_same_thread_id(
    mocker: Any,
) -> None:
    """Two invokes with the same thread_id: turn 2's LLM sees turn 1's exchange."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [_ai("turn 1 reply"), _ai("turn 2 reply")]
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    config: dict[str, Any] = {
        "configurable": {"thread_id": f"test-mem-acc-{uuid.uuid4()}"}
    }

    GRAPH.invoke(
        _make_state([HumanMessage(content="primeira mensagem")]), config=config
    )
    GRAPH.invoke(
        _make_state([HumanMessage(content="segunda mensagem")]), config=config
    )

    assert mock_llm.invoke.call_count == 2
    second_call_messages = mock_llm.invoke.call_args_list[1].args[0]
    # agent_node always prepends SystemMessage. Restored history = [Human1, AI1],
    # plus the new Human2 = 3 conversational messages; plus System = 4 total.
    assert len(second_call_messages) == 4, (
        "checkpointer must restore turn 1's history into turn 2's input; "
        f"got {len(second_call_messages)} messages: "
        f"{[type(m).__name__ for m in second_call_messages]}"
    )
    assert isinstance(second_call_messages[0], SystemMessage)
    assert isinstance(second_call_messages[1], HumanMessage)
    assert second_call_messages[1].content == "primeira mensagem"
    assert isinstance(second_call_messages[2], AIMessage)
    assert second_call_messages[2].content == "turn 1 reply"
    assert isinstance(second_call_messages[3], HumanMessage)
    assert second_call_messages[3].content == "segunda mensagem"


def test_memory_isolates_history_between_different_thread_ids(mocker: Any) -> None:
    """thread_id A's history must not bleed into thread_id B.

    Sequence: A.invoke(H1) → A.invoke(H2) → B.invoke(H3).
    - A's 2nd LLM call must see [System, H1, AI1, H2] (A's history restored).
    - B's only LLM call must see [System, H3] (clean, no A leakage).
    """
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [_ai("A reply 1"), _ai("A reply 2"), _ai("B reply")]
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    thread_a = f"test-mem-iso-A-{uuid.uuid4()}"
    thread_b = f"test-mem-iso-B-{uuid.uuid4()}"

    GRAPH.invoke(
        _make_state([HumanMessage(content="A primeira")]),
        config={"configurable": {"thread_id": thread_a}},
    )
    GRAPH.invoke(
        _make_state([HumanMessage(content="A segunda")]),
        config={"configurable": {"thread_id": thread_a}},
    )
    GRAPH.invoke(
        _make_state([HumanMessage(content="B primeira")]),
        config={"configurable": {"thread_id": thread_b}},
    )

    assert mock_llm.invoke.call_count == 3

    a_second_msgs = mock_llm.invoke.call_args_list[1].args[0]
    assert len(a_second_msgs) == 4, (
        "thread A's second invoke must restore A's prior turn; "
        f"got {len(a_second_msgs)} messages"
    )
    a_second_humans: list[Any] = [
        m.content for m in a_second_msgs if isinstance(m, HumanMessage)
    ]
    assert "A primeira" in a_second_humans
    assert "A segunda" in a_second_humans

    b_msgs = mock_llm.invoke.call_args_list[2].args[0]
    assert len(b_msgs) == 2, (
        "thread B must start clean — no A history leakage; "
        f"got {len(b_msgs)} messages: "
        f"{[getattr(m, 'content', None) for m in b_msgs]}"
    )
    assert isinstance(b_msgs[0], SystemMessage)
    assert isinstance(b_msgs[1], HumanMessage)
    assert b_msgs[1].content == "B primeira"
    for m in b_msgs:
        if isinstance(m, HumanMessage):
            assert "A primeira" not in m.content
            assert "A segunda" not in m.content


def test_per_turn_token_counters_reset_with_input_zero(mocker: Any) -> None:
    """tokens_used / tokens_in have no reducer — input replaces checkpointed value.

    Pins the per-turn token reset contract: each turn's input dict carries
    tokens_used=0, tokens_in=0, so the checkpointed accumulated value is
    overwritten by 0 before agent_node adds the new delta. The Streamlit caller
    relies on this to report per-turn usage rather than session totals.

    Regression guard against accidentally annotating tokens_used with an
    accumulating reducer once the checkpointer is in place.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        _ai("turn 1", input_t=100, output_t=30),
        _ai("turn 2", input_t=200, output_t=50),
    ]
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    config: dict[str, Any] = {
        "configurable": {"thread_id": f"test-mem-tok-{uuid.uuid4()}"}
    }

    r1 = GRAPH.invoke(_make_state([HumanMessage(content="t1")]), config=config)
    r2 = GRAPH.invoke(_make_state([HumanMessage(content="t2")]), config=config)

    assert r1["tokens_used"] == 130
    assert r1["tokens_in"] == 100
    assert r2["tokens_used"] == 250, (
        "turn 2 token count must reset (input 0 replaces checkpointed value); "
        f"got {r2['tokens_used']}"
    )
    assert r2["tokens_in"] == 200


def test_pending_bill_image_does_not_persist_into_next_turn(mocker: Any) -> None:
    """HR-6: parse_bill's Command-based clear survives in the checkpoint.

    Turn 1 enters with pending_bill_image bytes attached; the LLM is mocked to
    issue a parse_bill tool call; parse_bill's underlying func is patched to a
    Command that mirrors the real exit contract (clear + ToolMessage). After
    turn 1 settles, get_state on the thread_id must report
    pending_bill_image=None — image bytes never linger into a second turn.

    Today: GRAPH.get_state raises without a configured checkpointer.
    """
    from energia.chat.tools.bill import parse_bill_tool

    def _fake_parse_bill(**kwargs: Any) -> Any:
        tool_call_id = kwargs.get("tool_call_id", "tc-bill")
        return Command(
            update={
                "messages": [
                    ToolMessage(content="conta interpretada", tool_call_id=tool_call_id)
                ],
                "pending_bill_image": None,
            }
        )

    mocker.patch.object(parse_bill_tool, "func", new=_fake_parse_bill)

    tool_call_ai = AIMessage(
        content="",
        tool_calls=[{"id": "tc-bill", "name": "parse_bill", "args": {}}],
        usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
    )
    final_ai = _ai("Pronto, dados extraídos.", input_t=80, output_t=20)
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [tool_call_ai, final_ai]
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    config: dict[str, Any] = {
        "configurable": {"thread_id": f"test-mem-bill-{uuid.uuid4()}"}
    }

    state_with_image: dict[str, Any] = _make_state(
        [HumanMessage(content="analise a conta anexa")]
    )
    state_with_image["pending_bill_image"] = {
        "image_bytes": b"\x89PNG\r\n",
        "media_type": "image/png",
    }

    GRAPH.invoke(state_with_image, config=config)

    snap = GRAPH.get_state(config)
    assert snap.values.get("pending_bill_image") is None, (
        "parse_bill cleared the channel via Command, so the checkpoint must hold "
        f"None — got {snap.values.get('pending_bill_image')!r}"
    )


def test_eval_runner_passes_unique_thread_id_per_invocation(mocker: Any) -> None:
    """run_example must thread a unique thread_id through every GRAPH.invoke.

    pass@3 runs the same EvalExample three times. Without unique thread_ids the
    second and third attempts would replay the prior attempt's checkpointed
    history, contaminating scoring. Today the runner passes no config at all.
    """
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [HumanMessage(content="x"), AIMessage(content="ok")],
        "tokens_used": 10,
    }
    mocker.patch("energia.chat.graph.GRAPH", mock_graph)

    from energia.evals.runner import EvalExample, MessageInput, run_example

    example = EvalExample(
        name="t1",
        input_messages=[MessageInput(role="user", content="oi")],
    )
    run_example(example)
    run_example(example)

    assert mock_graph.invoke.call_count == 2
    thread_ids: list[str] = []
    for call in mock_graph.invoke.call_args_list:
        cfg: dict[str, Any] | None = call.kwargs.get("config")
        if cfg is None and len(call.args) > 1:
            cfg = call.args[1]
        assert cfg is not None, (
            "run_example must pass a config — configurable.thread_id is required "
            "now that the graph is compiled with a checkpointer"
        )
        configurable: dict[str, Any] = cfg.get("configurable") or {}
        tid: Any = configurable.get("thread_id")
        assert tid, "run_example must set configurable.thread_id on every invoke"
        thread_ids.append(str(tid))

    assert thread_ids[0] != thread_ids[1], (
        "two invocations on the same example must use distinct thread_ids "
        "(otherwise pass@3 attempts contaminate each other through restored history)"
    )
