"""Tests for current_bill state persistence (Task 1.8 Part A — RED first).

These verify:
1. parse_bill's success path adds current_bill: Bill to the Command update.
2. parse_bill's BillParseError and no-attachment paths do NOT touch current_bill.
3. current_bill survives a MemorySaver checkpoint round-trip as a Bill instance
   (guards the LangGraph JsonPlusSerializer's Pydantic round-trip; if this goes
   RED after GREEN, the fallback is to store model_dump() dict and rehydrate
   in correct_bill_field — Daniel approved that fallback explicitly).

All Anthropic SDK / parse_bill_image / LLM calls are mocked. No real API traffic.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from energia.bill.parser import BillParseError
from energia.chat.tools import ALL_TOOLS
from energia.models import Bill, BillComposition, ParseResult


def _get_parse_bill_tool() -> Any:
    for t in ALL_TOOLS:
        if t.name == "parse_bill":
            return t
    raise AssertionError("parse_bill tool is not registered in ALL_TOOLS")


def _make_state(pending: dict[str, Any] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "messages": [],
        "user_id": "u1",
        "conversation_id": "c1",
        "tokens_used": 0,
        "tokens_in": 0,
    }
    if pending is not None:
        state["pending_bill_image"] = pending
    return state


def _make_bill() -> Bill:
    return Bill(
        distributor="Enel Rio",
        installation_number="987654",
        period="2026-03",
        issue_date=date(2026, 3, 10),
        due_date=date(2026, 3, 20),
        consumption_kwh=Decimal("312.50"),
        tariff_group="B1",
        modalidade="Convencional",
        bandeira="Verde",
        total_brl=Decimal("287.40"),
        composition=BillComposition(
            tusd=Decimal("120.00"),
            te=Decimal("100.00"),
            icms=Decimal("55.00"),
        ),
        confidence=0.95,
    )


def _invoke_parse_bill(tool: Any, state: dict[str, Any], call_id: str) -> Any:
    return tool.invoke({
        "name": "parse_bill",
        "args": {"state": state},
        "id": call_id,
        "type": "tool_call",
    })


def test_parse_bill_success_populates_current_bill_in_state(mocker: Any) -> None:
    """Success path: Command update carries the parsed Bill as a JSON-primitive dict.

    The checkpoint stores model_dump(mode="json") so no Decimal/date objects
    cross the serialization boundary (kills the LangChain unregistered-type
    deprecation). The contract is "the recoverable value", asserted via
    Bill.model_validate round-trip — not in-channel object identity.
    """
    bill = _make_bill()
    parse_result = ParseResult(bill=bill, needs_user_confirmation=False)
    mocker.patch(
        "energia.chat.tools.bill.bill_store.find_by_hash",
        return_value=None,
    )
    mocker.patch(
        "energia.chat.tools.bill.bill_store.insert",
        return_value="fake-bill-uuid",
    )
    mocker.patch(
        "energia.chat.tools.bill.parse_bill_image",
        return_value=parse_result,
    )

    tool = _get_parse_bill_tool()
    state = _make_state(
        pending={"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"}
    )

    result = _invoke_parse_bill(tool, state, "call_persist")

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert isinstance(update, dict)
    assert "current_bill" in update, (
        "parse_bill success path must add current_bill to its Command update "
        "so the bill survives across turns (Task 1.8 Part A)"
    )
    stored: Any = update["current_bill"]
    assert isinstance(stored, dict), (
        "current_bill must be stored as a JSON-primitive dict — NOT a Bill "
        f"instance — to keep the checkpoint serializer-safe; got {type(stored).__name__}"
    )
    rehydrated = Bill.model_validate(stored)
    assert rehydrated == bill, (
        "the stored dict must round-trip to the same Bill via Bill.model_validate"
    )


def test_parse_bill_failure_does_not_populate_current_bill(mocker: Any) -> None:
    """BillParseError path: current_bill is NOT written to the Command update.

    Rationale: a stale current_bill (if one exists from a prior turn) must
    remain valid. A new failed parse must not clobber it with nothing.
    """
    mocker.patch(
        "energia.chat.tools.bill.bill_store.find_by_hash",
        return_value=None,
    )
    mocker.patch(
        "energia.chat.tools.bill.parse_bill_image",
        side_effect=BillParseError("bill validation failed"),
    )

    tool = _get_parse_bill_tool()
    state = _make_state(
        pending={"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"}
    )

    result = _invoke_parse_bill(tool, state, "call_fail")

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert "current_bill" not in update, (
        "BillParseError path must NOT write current_bill — failure must not "
        "overwrite a previously-good bill with anything"
    )


def test_parse_bill_no_attachment_does_not_populate_current_bill() -> None:
    """No-attachment path: current_bill is NOT touched in the Command update."""
    tool = _get_parse_bill_tool()
    state = _make_state(pending=None)

    result = _invoke_parse_bill(tool, state, "call_no_attach")

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert "current_bill" not in update, (
        "no-attachment path must NOT write current_bill — same reason as failure"
    )


def test_current_bill_survives_checkpoint_round_trip(mocker: Any) -> None:
    """MemorySaver round-trip preserves the Bill as a JSON-primitive dict.

    The contract is "asserts the recoverable value via Bill.model_validate" — not
    the checkpoint's internal type. Storing model_dump(mode="json") instead of a
    Bill instance keeps the checkpoint primitive-only and avoids LangChain's
    unregistered-type deprecation warning.
    """
    bill = _make_bill()
    parse_result = ParseResult(bill=bill, needs_user_confirmation=False)
    mocker.patch(
        "energia.chat.tools.bill.bill_store.find_by_hash",
        return_value=None,
    )
    mocker.patch(
        "energia.chat.tools.bill.bill_store.insert",
        return_value="fake-bill-uuid",
    )
    mocker.patch(
        "energia.chat.tools.bill.parse_bill_image",
        return_value=parse_result,
    )

    tool_call_ai = AIMessage(
        content="",
        tool_calls=[{"id": "tc-persist", "name": "parse_bill", "args": {}}],
        usage_metadata={
            "input_tokens": 50,
            "output_tokens": 10,
            "total_tokens": 60,
        },
    )
    final_ai = AIMessage(
        content="Conta lida.",
        usage_metadata={
            "input_tokens": 80,
            "output_tokens": 20,
            "total_tokens": 100,
        },
    )
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [tool_call_ai, final_ai]
    mocker.patch("energia.chat.nodes._llm_with_tools", mock_llm)

    from energia.chat.graph import GRAPH

    config: dict[str, Any] = {
        "configurable": {"thread_id": f"test-bill-persist-{uuid.uuid4()}"}
    }

    initial = _make_state(
        pending={"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"}
    )
    initial["messages"] = [HumanMessage(content="analise a conta")]

    GRAPH.invoke(initial, config=config)

    snap = GRAPH.get_state(config)
    stored: Any = snap.values.get("current_bill")
    assert stored is not None, (
        "current_bill must be persisted to the checkpoint after parse_bill success"
    )
    assert isinstance(stored, dict), (
        "current_bill must round-trip as a JSON-primitive dict (no Decimal/date "
        f"objects across the serializer boundary); got {type(stored).__name__}"
    )
    rehydrated = Bill.model_validate(stored)
    assert rehydrated == bill, "round-tripped dict must rehydrate to the same Bill"
    assert rehydrated.distributor == "Enel Rio"
    assert rehydrated.consumption_kwh == Decimal("312.50")
