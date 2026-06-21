"""compare_bill_periods tool wrapper tests (Task 1.5, RED first).

bill_store calls are mocked at the import site
(``energia.chat.tools.compare.bill_store.find_latest_periods`` /
``.find_by_period``). No real DB writes, no real vision calls.

HR-5 enforcement is explicit in this file:
- The three not-enough-bills paths (0 bills / 1 bill / only 1 distinct
  period) return a ToolMessage with NO quantitative claim — no "kWh", no
  "R$", no "%" tokens. The tool never invents.
- The success path returns the comparison.model_dump(mode="json") body, but
  does NOT contain causal language: no "tarifa", "causou", "porque", or
  "por que" — the tool reports WHAT changed, never WHY (TD-018).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, cast

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from energia.chat.tools import ALL_TOOLS
from energia.models import Bill


def _get_compare_tool() -> Any:
    for t in ALL_TOOLS:
        if t.name == "compare_bill_periods":
            return t
    raise AssertionError("compare_bill_periods tool is not registered in ALL_TOOLS")


def _make_state() -> dict[str, Any]:
    return {
        "messages": [],
        "user_id": "u1",
        "conversation_id": "c1",
        "tokens_used": 0,
        "tokens_in": 0,
    }


def _bill(period: str, kwh: str, total: str) -> Bill:
    return Bill(
        distributor="Enel Rio",
        installation_number="000000",
        period=period,
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 15),
        consumption_kwh=Decimal(kwh),
        tariff_group="B1",
        modalidade="Convencional",
        bandeira="Verde",
        total_brl=Decimal(total),
        composition=None,
        confidence=0.95,
    )


def _invoke(
    tool: Any,
    state: dict[str, Any],
    call_id: str,
    period_a: str | None = None,
    period_b: str | None = None,
) -> Any:
    args: dict[str, Any] = {"state": state}
    if period_a is not None:
        args["period_a"] = period_a
    if period_b is not None:
        args["period_b"] = period_b
    return tool.invoke({
        "name": "compare_bill_periods",
        "args": args,
        "id": call_id,
        "type": "tool_call",
    })


_QUANT_TOKENS = ("kWh", "R$", "%")
_CAUSAL_TOKENS = ("tarifa", "causou", "porque", "por que")


def _by_period(
    bills_by_period: dict[str, Bill],
) -> Callable[..., Bill | None]:
    """Typed factory for the bill_store.find_by_period side_effect."""
    def _resolve(
        user_id: str, period: str, db_path: str | None = None
    ) -> Bill | None:
        return bills_by_period.get(period)
    return _resolve


def _content_of(result: Any) -> str:
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    msgs: list[Any] = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], ToolMessage)
    return cast(str, msgs[0].content)


def _assert_no_quantitative_claim(content: str) -> None:
    for token in _QUANT_TOKENS:
        assert token not in content, (
            f"not-enough-bills message must not contain {token!r} — HR-5 "
            f"forbids invented quantitative claims. Content was: {content!r}"
        )


def _assert_no_causal_claim(content: str) -> None:
    lower = content.lower()
    for token in _CAUSAL_TOKENS:
        assert token not in lower, (
            f"narration seed must NOT contain {token!r} — TD-018 honesty: "
            "the tool reports WHAT changed, not WHY. Causal decomposition "
            "(tariff/bandeira/tax) is deferred to a post-Sprint-2 amendment."
        )


# ---------------------------------------------------------------------------
# Registration / schema
# ---------------------------------------------------------------------------


def test_compare_tool_is_registered_in_all_tools() -> None:
    names = [t.name for t in ALL_TOOLS]
    assert "compare_bill_periods" in names


def test_compare_tool_llm_visible_schema_excludes_state_and_tool_call_id() -> None:
    tool = _get_compare_tool()
    llm_args: dict[str, Any] = tool.args  # type: ignore[no-any-return]
    assert "state" not in llm_args
    assert "tool_call_id" not in llm_args
    assert "period_a" in llm_args
    assert "period_b" in llm_args


# ---------------------------------------------------------------------------
# Not-enough-bills paths — HR-5: no synthesized numbers
# ---------------------------------------------------------------------------


def test_compare_with_no_stored_bills_returns_graceful_message(mocker: Any) -> None:
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_latest_periods",
        return_value=[],
    )
    mock_find = mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period"
    )

    tool = _get_compare_tool()
    result = _invoke(tool, _make_state(), "call_zero")

    assert isinstance(result, Command)
    mock_find.assert_not_called()
    _assert_no_quantitative_claim(_content_of(result))


def test_compare_with_one_stored_bill_returns_graceful_message(mocker: Any) -> None:
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_latest_periods",
        return_value=["2026-03"],
    )
    mock_find = mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period"
    )

    tool = _get_compare_tool()
    result = _invoke(tool, _make_state(), "call_one")

    assert isinstance(result, Command)
    mock_find.assert_not_called()
    content = _content_of(result)
    _assert_no_quantitative_claim(content)
    assert "2026-03" in content, (
        "one-bill message should reference the period the user already has"
    )


def test_compare_with_explicit_same_period_returns_graceful_message(
    mocker: Any,
) -> None:
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_latest_periods",
        return_value=["2026-03"],
    )
    mock_find = mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period"
    )

    tool = _get_compare_tool()
    result = _invoke(
        tool, _make_state(), "call_same", period_a="2026-03", period_b="2026-03"
    )

    assert isinstance(result, Command)
    mock_find.assert_not_called()
    _assert_no_quantitative_claim(_content_of(result))


def test_compare_explicit_period_missing_bill_returns_graceful_message(
    mocker: Any,
) -> None:
    """Explicit args, but bill_store has no bill for one of the periods."""
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period",
        side_effect=_by_period({"2026-04": _bill("2026-04", "300", "300")}),
    )

    tool = _get_compare_tool()
    result = _invoke(
        tool, _make_state(), "call_missing",
        period_a="2026-04", period_b="2026-05",
    )

    assert isinstance(result, Command)
    content = _content_of(result)
    _assert_no_quantitative_claim(content)
    assert "2026-05" in content, (
        "missing-period message must name which period is missing"
    )


# ---------------------------------------------------------------------------
# Success — auto-pick latest two
# ---------------------------------------------------------------------------


def test_compare_auto_picks_latest_two_distinct_periods(mocker: Any) -> None:
    earlier = _bill("2026-04", "200", "180")
    later = _bill("2026-05", "300", "330")

    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_latest_periods",
        return_value=["2026-05", "2026-04"],
    )
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period",
        side_effect=_by_period({"2026-04": earlier, "2026-05": later}),
    )

    tool = _get_compare_tool()
    result = _invoke(tool, _make_state(), "call_auto")

    assert isinstance(result, Command)
    content = _content_of(result)
    _assert_no_causal_claim(content)

    # The body contains the structured JSON dump — extract and validate shape.
    match = re.search(r"\{.*\}", content, re.DOTALL)
    assert match is not None, "success body must include a JSON object"
    payload = json.loads(match.group())

    assert payload["earlier"]["period"] == "2026-04"
    assert payload["later"]["period"] == "2026-05"
    assert "consumption_delta_kwh" in payload
    assert "cost_delta_brl" in payload
    assert "effective_rate_delta_brl_per_kwh" in payload
    assert "tariff_delta_brl_per_kwh" not in payload, (
        "field must be effective_rate_delta_brl_per_kwh, not tariff_… (TD-018)"
    )


def test_compare_explicit_periods_uses_them(mocker: Any) -> None:
    """When both periods are passed, find_latest_periods is NOT consulted."""
    earlier = _bill("2026-01", "200", "200")
    later = _bill("2026-06", "300", "330")

    mock_latest = mocker.patch(
        "energia.chat.tools.compare.bill_store.find_latest_periods"
    )
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period",
        side_effect=_by_period({"2026-01": earlier, "2026-06": later}),
    )

    tool = _get_compare_tool()
    result = _invoke(
        tool, _make_state(), "call_explicit",
        period_a="2026-06", period_b="2026-01",
    )

    mock_latest.assert_not_called()
    content = _content_of(result)
    match = re.search(r"\{.*\}", content, re.DOTALL)
    assert match is not None
    payload = json.loads(match.group())

    # Period ordering is lexicographic — earlier YYYY-MM is "earlier".
    assert payload["earlier"]["period"] == "2026-01"
    assert payload["later"]["period"] == "2026-06"


def test_compare_success_narration_describes_what_not_why(mocker: Any) -> None:
    """The PT-BR header + JSON body never contain causal tokens (TD-018)."""
    earlier = _bill("2026-04", "200", "180")
    later = _bill("2026-05", "200", "240")  # rate change, no consumption change

    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_latest_periods",
        return_value=["2026-05", "2026-04"],
    )
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period",
        side_effect=_by_period({"2026-04": earlier, "2026-05": later}),
    )

    tool = _get_compare_tool()
    result = _invoke(tool, _make_state(), "call_what_not_why")

    _assert_no_causal_claim(_content_of(result))


def test_compare_success_returns_command_clearing_no_other_channels(
    mocker: Any,
) -> None:
    """compare_bill_periods only writes messages — never touches pending_bill_image
    or current_bill. Pin the keys explicitly."""
    earlier = _bill("2026-04", "200", "200")
    later = _bill("2026-05", "300", "300")

    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_latest_periods",
        return_value=["2026-05", "2026-04"],
    )
    mocker.patch(
        "energia.chat.tools.compare.bill_store.find_by_period",
        side_effect=_by_period({"2026-04": earlier, "2026-05": later}),
    )

    tool = _get_compare_tool()
    result = _invoke(tool, _make_state(), "call_channels")

    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    assert "messages" in update
    assert "pending_bill_image" not in update
    assert "current_bill" not in update
