"""RED tests for the parse_bill LangChain tool — Task 1.3 Stage B.

Design (Option A — InjectedState):
- @tool("parse_bill") wraps a function whose only LLM-visible arg is nothing.
- The function reads state["pending_bill_image"] (an InjectedState[ChatState]).
- pending_bill_image is a dict {"image_bytes": bytes, "media_type": str} or absent.
- On success: Command(update={"messages": [ToolMessage(<narration>)],
                              "pending_bill_image": None}).
- On missing attachment: Command with ToolMessage telling the user to upload first.
- On BillParseError: Command with ToolMessage error narration — no exception leaks
  out to the graph.

All Anthropic SDK / parse_bill_image calls are mocked. No real API traffic.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

from langchain_core.messages import ToolMessage
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
    }
    if pending is not None:
        state["pending_bill_image"] = pending
    return state


def _make_parse_result(confidence: float = 0.95) -> ParseResult:
    return ParseResult(
        bill=Bill(
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
            confidence=confidence,
        ),
        needs_user_confirmation=confidence < 0.85,
    )


def _invoke(tool: Any, state: dict[str, Any], tool_call_id: str) -> Any:
    return tool.invoke({
        "name": "parse_bill",
        "args": {"state": state},
        "id": tool_call_id,
        "type": "tool_call",
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_bill_tool_is_registered_in_all_tools() -> None:
    """parse_bill tool self-registers when energia.chat.tools is imported."""
    names = [t.name for t in ALL_TOOLS]
    assert "parse_bill" in names


def test_parse_bill_tool_llm_visible_schema_excludes_bytes() -> None:
    """LLM-visible args must NOT include image_bytes / media_type — HR-6 / Option A.

    These come from InjectedState; the model cannot synthesize bill bytes. This is
    the structural guarantee, not a policy promise.
    """
    tool = _get_parse_bill_tool()
    llm_args: dict[str, Any] = tool.args  # type: ignore[no-any-return]
    assert "image_bytes" not in llm_args
    assert "media_type" not in llm_args
    assert "state" not in llm_args
    assert "tool_call_id" not in llm_args


def test_parse_bill_tool_dispatches_and_clears_pending_image_on_success(mocker: Any) -> None:
    """Tool reads state.pending_bill_image, calls parse_bill_image with its bytes,
    returns Command that clears the field and appends a ToolMessage."""
    parse_result = _make_parse_result(confidence=0.95)
    mocker.patch(
        "energia.chat.tools.bill.bill_store.find_by_hash",
        return_value=None,
    )
    mocker.patch(
        "energia.chat.tools.bill.bill_store.insert",
        return_value="fake-bill-uuid",
    )
    mock_parse = mocker.patch(
        "energia.chat.tools.bill.parse_bill_image",
        return_value=parse_result,
    )

    tool = _get_parse_bill_tool()
    state = _make_state(pending={"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"})

    result = _invoke(tool, state, "call_xyz")

    mock_parse.assert_called_once_with(b"\x89PNG\r\n", "image/png")
    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert isinstance(update, dict)
    assert update["pending_bill_image"] is None, (
        "tool must clear pending_bill_image via Command(update=...) after a successful parse"
    )
    msgs: list[Any] = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert msgs[0].tool_call_id == "call_xyz"


def test_parse_bill_tool_returns_toolmessage_when_no_pending_image() -> None:
    """When state has no pending_bill_image, tool returns a Command with a ToolMessage
    telling the user to upload the bill first — without calling parse_bill_image."""
    tool = _get_parse_bill_tool()
    state = _make_state(pending=None)

    result = _invoke(tool, state, "call_none")

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert isinstance(update, dict)
    msgs: list[Any] = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert msgs[0].tool_call_id == "call_none"
    content = cast(str, msgs[0].content)
    assert isinstance(content, str) and content, "ToolMessage must carry a non-empty string"


def test_parse_bill_tool_catches_billparseerror_and_returns_toolmessage(mocker: Any) -> None:
    """When parse_bill_image raises BillParseError, the tool catches it and returns a
    Command with a ToolMessage describing the failure — no exception leaks to the graph."""
    mocker.patch(
        "energia.chat.tools.bill.bill_store.find_by_hash",
        return_value=None,
    )
    mocker.patch(
        "energia.chat.tools.bill.parse_bill_image",
        side_effect=BillParseError("bill validation failed: missing fields"),
    )

    tool = _get_parse_bill_tool()
    state = _make_state(pending={"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"})

    result = _invoke(tool, state, "call_err")

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert isinstance(update, dict)
    msgs: list[Any] = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert msgs[0].tool_call_id == "call_err"


def test_parse_bill_tool_cache_hit_skips_vision_call_and_emits_marker(
    mocker: Any,
) -> None:
    """Cache hit: bill_store.find_by_hash returns a Bill, so parse_bill_image is
    never called and bill_store.insert is never called either. The Command update
    carries the cached Bill (via model_dump(mode="json")) and the narration includes
    the "memória local" marker so the audit trail is unambiguous."""
    cached = ParseResult(
        bill=Bill(
            distributor="Cached Distribuidora",
            installation_number="111222",
            period="2026-02",
            issue_date=date(2026, 2, 5),
            due_date=date(2026, 2, 15),
            consumption_kwh=Decimal("250.00"),
            tariff_group="B1",
            modalidade="Convencional",
            bandeira="Verde",
            total_brl=Decimal("210.00"),
            composition=BillComposition(
                tusd=Decimal("90.00"),
                te=Decimal("80.00"),
                icms=Decimal("40.00"),
            ),
            confidence=0.95,
        ),
        needs_user_confirmation=False,
    ).bill

    mock_find = mocker.patch(
        "energia.chat.tools.bill.bill_store.find_by_hash",
        return_value=cached,
    )
    mock_parse = mocker.patch("energia.chat.tools.bill.parse_bill_image")
    mock_insert = mocker.patch("energia.chat.tools.bill.bill_store.insert")

    tool = _get_parse_bill_tool()
    state = _make_state(pending={"image_bytes": b"\x89PNG\r\n", "media_type": "image/png"})

    result = _invoke(tool, state, "call_cache_hit")

    mock_find.assert_called_once()
    mock_parse.assert_not_called()
    mock_insert.assert_not_called()

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    stored: Any = update["current_bill"]
    assert isinstance(stored, dict), (
        "cache hit must write current_bill as JSON-primitive dict (TD-015 contract)"
    )
    rehydrated = Bill.model_validate(stored)
    assert rehydrated == cached

    msgs: list[Any] = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert msgs[0].tool_call_id == "call_cache_hit"
    content = cast(str, msgs[0].content)
    assert "memória local" in content, (
        "cache hit narration must mark the source so the audit trail is unambiguous"
    )
