"""Bandeira tool wrapper tests (Task 2.2, RED first)."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from energia.chat.tools import ALL_TOOLS


def _tool(name: str) -> Any:
    for candidate in ALL_TOOLS:
        if candidate.name == name:
            return candidate
    raise AssertionError(f"{name} is not registered in ALL_TOOLS")


def _state() -> dict[str, Any]:
    return {
        "messages": [],
        "user_id": "u1",
        "conversation_id": "c1",
        "tokens_used": 0,
        "tokens_in": 0,
    }


def _content(result: Any) -> str:
    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    messages: list[Any] = update["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], ToolMessage)
    return cast(str, messages[0].content)


def _payload(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    assert match is not None, f"success body must contain JSON: {content!r}"
    return cast(dict[str, Any], json.loads(match.group()))


def _invoke(name: str, call_id: str, **args: Any) -> Any:
    return _tool(name).invoke(
        {"name": name, "args": {"state": _state(), **args}, "id": call_id, "type": "tool_call"}
    )


def test_bandeira_tools_self_register_and_hide_runtime_arguments() -> None:
    names = [tool.name for tool in ALL_TOOLS]
    assert "current_bandeira" in names
    assert "bandeira_history" in names

    for name in ("current_bandeira", "bandeira_history"):
        args: dict[str, Any] = _tool(name).args  # type: ignore[no-any-return]
        assert "state" not in args
        assert "tool_call_id" not in args
        assert "as_of" in args

    assert "months" in _tool("bandeira_history").args


def test_current_bandeira_tool_returns_only_snapshot_values_and_provenance() -> None:
    content = _content(_invoke("current_bandeira", "call_current", as_of="2026-08-30"))

    payload = _payload(content)
    assert set(payload) == {"period", "flag", "surcharge_brl_per_kwh", "source"}
    assert payload["period"] == "2026-08-01"
    assert payload["flag"] == "Amarela"
    assert payload["surcharge_brl_per_kwh"] == "0.01885"
    assert payload["source"]["updated"] == "2026-08-24"
    assert payload["source"]["hash_value"] == "c098ee1b39e75b28b5ac646e1e9746ca"


def test_bandeira_history_tool_returns_chronological_snapshot_payloads() -> None:
    content = _content(_invoke("bandeira_history", "call_history", as_of="2026-08-30", months=3))

    payload = _payload(content)
    assert set(payload) == {"records"}
    assert [record["period"] for record in payload["records"]] == [
        "2026-06-01",
        "2026-07-01",
        "2026-08-01",
    ]
    assert all(
        set(record) == {"period", "flag", "surcharge_brl_per_kwh", "source"}
        for record in payload["records"]
    )


def test_bandeira_tools_return_number_free_message_outside_snapshot() -> None:
    for name, args in (
        ("current_bandeira", {"as_of": "2026-09-01"}),
        ("bandeira_history", {"as_of": "2026-09-01", "months": 12}),
    ):
        content = _content(_invoke(name, f"call_{name}", **args))
        assert re.search(r"\d", content) is None
        assert "R$" not in content
        assert "{" not in content
