"""Tests for correct_bill_field tool (Task 1.8 Part B — RED first).

Surgical single-field bill correction.

- LLM-visible args: field (Literal of 5) + value (str).
- Reads current_bill from InjectedState (ChatState).
- For numeric fields (consumption_kwh, total_brl), normalizes PT-BR formatting:
  if value contains a comma, ALL "." are removed (thousands sep) then "," → ".".
  If no comma, "." stays. Trailing "kWh" and leading "R$" are stripped.
- Re-validates the resulting Bill — ValidationError → graceful ToolMessage,
  state unchanged.
- Success → Command update with a new Bill in current_bill and ONE field changed,
  all others byte-identical to the original (HR-5).
- Never re-parses; never re-emits other fields; never invents data.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from energia.chat.tools import ALL_TOOLS
from energia.models import Bill, BillComposition


def _get_correct_tool() -> Any:
    for t in ALL_TOOLS:
        if t.name == "correct_bill_field":
            return t
    raise AssertionError("correct_bill_field tool is not registered in ALL_TOOLS")


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


def _make_state(current_bill: Bill | None) -> dict[str, Any]:
    """current_bill lives in the checkpoint as a JSON-primitive dict.

    Producers (parse_bill, correct_bill_field) write model_dump(mode="json").
    Consumers rehydrate via Bill.model_validate(...). This helper mirrors that
    contract — tests inject the dict form, not the Bill object.
    """
    state: dict[str, Any] = {
        "messages": [],
        "user_id": "u1",
        "conversation_id": "c1",
        "tokens_used": 0,
        "tokens_in": 0,
    }
    if current_bill is not None:
        state["current_bill"] = current_bill.model_dump(mode="json")
    return state


def _invoke(
    tool: Any, state: dict[str, Any], field: str, value: str, call_id: str
) -> Any:
    return tool.invoke({
        "name": "correct_bill_field",
        "args": {"field": field, "value": value, "state": state},
        "id": call_id,
        "type": "tool_call",
    })


# ---------------------------------------------------------------------------
# Registration / schema
# ---------------------------------------------------------------------------


def test_correct_tool_is_registered_in_all_tools() -> None:
    """correct_bill_field self-registers when energia.chat.tools is imported."""
    names = [t.name for t in ALL_TOOLS]
    assert "correct_bill_field" in names


def test_correct_tool_llm_visible_schema_is_field_and_value_only() -> None:
    """LLM sees field + value only; state and tool_call_id are injected."""
    tool = _get_correct_tool()
    llm_args: dict[str, Any] = tool.args  # type: ignore[no-any-return]
    assert "field" in llm_args
    assert "value" in llm_args
    assert "state" not in llm_args
    assert "tool_call_id" not in llm_args
    assert "current_bill" not in llm_args


# ---------------------------------------------------------------------------
# No-bill path
# ---------------------------------------------------------------------------


def test_correct_with_no_current_bill_returns_graceful_message() -> None:
    """No current_bill → ToolMessage asking user to upload a bill; no state change."""
    tool = _get_correct_tool()
    state = _make_state(current_bill=None)

    result = _invoke(tool, state, field="total_brl", value="410,50", call_id="c-none")

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert "current_bill" not in update, (
        "no-bill path must NOT write current_bill — there is nothing to overwrite"
    )
    msgs: list[Any] = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    assert msgs[0].tool_call_id == "c-none"
    content = cast(str, msgs[0].content)
    assert isinstance(content, str) and content


# ---------------------------------------------------------------------------
# Single-field surgical update — HR-5
# ---------------------------------------------------------------------------


def test_correct_distributor_changes_only_that_field() -> None:
    """All non-target fields byte-identical to the original Bill (HR-5).

    Both sides compared as JSON-primitive dicts to match the in-checkpoint form.
    """
    tool = _get_correct_tool()
    bill = _make_bill()
    state = _make_state(current_bill=bill)

    result = _invoke(
        tool, state, field="distributor", value="Light SA", call_id="c-dist"
    )

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    stored: Any = update["current_bill"]
    assert isinstance(stored, dict)
    new_bill = Bill.model_validate(stored)
    assert new_bill.distributor == "Light SA"

    original: dict[str, Any] = bill.model_dump(mode="json")
    updated: dict[str, Any] = dict(cast(dict[str, Any], stored))
    original.pop("distributor")
    updated.pop("distributor")
    assert original == updated, (
        "correct_bill_field must change ONLY the named field; "
        "all other fields must be byte-identical to the original"
    )


def test_correct_installation_number_is_a_string_not_normalized() -> None:
    """UC is a string; no numeric normalization applied; other fields unchanged."""
    tool = _get_correct_tool()
    bill = _make_bill()
    state = _make_state(current_bill=bill)

    result = _invoke(
        tool, state, field="installation_number", value="123456789", call_id="c-uc"
    )

    update: dict[str, Any] = result.update  # type: ignore[assignment]
    stored: Any = update["current_bill"]
    assert isinstance(stored, dict)
    new_bill = Bill.model_validate(stored)
    assert new_bill.installation_number == "123456789"
    assert new_bill.distributor == bill.distributor
    assert new_bill.consumption_kwh == bill.consumption_kwh
    assert new_bill.total_brl == bill.total_brl


def test_correct_period_to_valid_format_succeeds() -> None:
    """period='2026-04' is valid YYYY-MM → succeeds and updates only period."""
    tool = _get_correct_tool()
    bill = _make_bill()
    state = _make_state(current_bill=bill)

    result = _invoke(tool, state, field="period", value="2026-04", call_id="c-p-ok")

    update: dict[str, Any] = result.update  # type: ignore[assignment]
    stored: Any = update["current_bill"]
    assert isinstance(stored, dict)
    new_bill = Bill.model_validate(stored)
    assert new_bill.period == "2026-04"


# ---------------------------------------------------------------------------
# PT-BR numeric normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.416,94", Decimal("1416.94")),
        ("416,94", Decimal("416.94")),
        ("416.94", Decimal("416.94")),
        ("374", Decimal("374")),
        ("R$ 1.416,94", Decimal("1416.94")),
        ("R$1.416,94", Decimal("1416.94")),
    ],
)
def test_correct_total_brl_normalizes_pt_br_formatting(
    raw: str, expected: Decimal
) -> None:
    """When value contains a comma, "." is thousands sep and gets stripped; then "," → ".".

    Without a comma, "." stays as the decimal sep. Leading R$ is also stripped.
    """
    tool = _get_correct_tool()
    state = _make_state(current_bill=_make_bill())

    result = _invoke(
        tool, state, field="total_brl", value=raw, call_id="c-norm-total"
    )

    update: dict[str, Any] = result.update  # type: ignore[assignment]
    stored: Any = update["current_bill"]
    assert isinstance(stored, dict)
    new_bill = Bill.model_validate(stored)
    assert new_bill.total_brl == expected, (
        f"PT-BR normalization failed for {raw!r}: "
        f"got {new_bill.total_brl!r}, expected {expected!r}"
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("312,5", Decimal("312.5")),
        ("312,5 kWh", Decimal("312.5")),
        ("312.5", Decimal("312.5")),
        ("1.234,56", Decimal("1234.56")),
    ],
)
def test_correct_consumption_kwh_strips_unit_and_normalizes(
    raw: str, expected: Decimal
) -> None:
    """Same normalization rule as total_brl; "kWh" suffix is also stripped."""
    tool = _get_correct_tool()
    state = _make_state(current_bill=_make_bill())

    result = _invoke(
        tool, state, field="consumption_kwh", value=raw, call_id="c-norm-kwh"
    )

    update: dict[str, Any] = result.update  # type: ignore[assignment]
    stored: Any = update["current_bill"]
    assert isinstance(stored, dict)
    new_bill = Bill.model_validate(stored)
    assert new_bill.consumption_kwh == expected


# ---------------------------------------------------------------------------
# Validation-error path — state unchanged
# ---------------------------------------------------------------------------


def test_correct_with_invalid_numeric_value_returns_validation_message() -> None:
    """consumption_kwh='abc' → ToolMessage, current_bill not written."""
    tool = _get_correct_tool()
    state = _make_state(current_bill=_make_bill())

    result = _invoke(
        tool, state, field="consumption_kwh", value="abc", call_id="c-bad-num"
    )

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert "current_bill" not in update, (
        "invalid value must NOT mutate current_bill — the existing valid bill stays"
    )
    msgs: list[Any] = update["messages"]
    assert isinstance(msgs[0], ToolMessage)
    content = cast(str, msgs[0].content)
    assert isinstance(content, str) and content


def test_correct_with_invalid_period_returns_validation_message() -> None:
    """period='2026-13' fails the YYYY-MM regex → ToolMessage, state unchanged."""
    tool = _get_correct_tool()
    state = _make_state(current_bill=_make_bill())

    result = _invoke(
        tool, state, field="period", value="2026-13", call_id="c-bad-p"
    )

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert "current_bill" not in update
    msgs: list[Any] = update["messages"]
    assert isinstance(msgs[0], ToolMessage)
