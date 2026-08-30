"""Tarifa Branca tool tests (Task 2.4, RED first)."""

from __future__ import annotations

import json
import re
from decimal import Decimal
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


def _invoke(call_id: str, **args: Any) -> Any:
    return _tool("simulate_tarifa_branca").invoke(
        {
            "name": "simulate_tarifa_branca",
            "args": {"state": _state(), **args},
            "id": call_id,
            "type": "tool_call",
        }
    )


def test_tarifa_branca_tool_self_registers_and_hides_runtime_arguments() -> None:
    names = [tool.name for tool in ALL_TOOLS]
    assert "simulate_tarifa_branca" in names

    args: dict[str, Any] = _tool("simulate_tarifa_branca").args  # type: ignore[no-any-return]
    assert "state" not in args
    assert "tool_call_id" not in args
    assert set(args) == {"distributor", "ponta_kwh", "intermediaria_kwh", "fora_ponta_kwh"}


def test_tarifa_branca_tool_returns_comparison_and_required_assumptions() -> None:
    content = _content(
        _invoke(
            "call_branca",
            distributor="Enel Rio",
            ponta_kwh="30",
            intermediaria_kwh="20",
            fora_ponta_kwh="250",
        )
    )

    payload = _payload(content)
    assert Decimal(payload["conventional_cost_brl"]) == Decimal("318.33000")
    assert Decimal(payload["branca_cost_brl"]) == Decimal("316.84590")
    assert Decimal(payload["savings_brl"]) == Decimal("1.48410")
    assert payload["source"]["resolution"] == "REH 3570/2026"
    assert payload["source"]["url"].startswith("https://")
    content_lower = content.lower()
    assert "impostos" in content_lower
    assert "cosip" in content_lower
    assert "bandeira" in content_lower


def test_tarifa_branca_tool_rejects_unknown_distributor_without_numbers() -> None:
    content = _content(
        _invoke(
            "call_unknown",
            distributor="Light",
            ponta_kwh="30",
            intermediaria_kwh="20",
            fora_ponta_kwh="250",
        )
    )

    assert re.search(r"\d", content) is None
    assert "R$" not in content
    assert "{" not in content


def test_tarifa_branca_tool_rejects_invalid_profile_without_numbers() -> None:
    content = _content(
        _invoke(
            "call_invalid",
            distributor="Enel RJ",
            ponta_kwh="0",
            intermediaria_kwh="0",
            fora_ponta_kwh="0",
        )
    )

    assert re.search(r"\d", content) is None
    assert "R$" not in content
    assert "{" not in content
