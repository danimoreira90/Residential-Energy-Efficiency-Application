"""RED contracts for the registered solar-sizing tool."""
from __future__ import annotations

import json
import re
from typing import Any, cast

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from energia.chat.tools import ALL_TOOLS


def _tool() -> Any:
    for candidate in ALL_TOOLS:
        if candidate.name == "estimate_solar_system":
            return candidate
    raise AssertionError("estimate_solar_system is not registered")


def _invoke(call_id: str = "solar-call") -> str:
    result = _tool().invoke(
        {
            "name": "estimate_solar_system",
            "args": {
                "state": {
                    "messages": [],
                    "user_id": "synthetic-user",
                    "conversation_id": "synthetic-conversation",
                    "tokens_used": 0,
                    "tokens_in": 0,
                },
                "latitude": 10.04,
                "longitude": 20.06,
                "monthly_consumption_kwh": "100",
                "roof_orientation": "N",
                "roof_tilt_deg": "15",
            },
            "id": call_id,
            "type": "tool_call",
        }
    )
    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    messages: list[Any] = update["messages"]
    assert len(messages) == 1 and isinstance(messages[0], ToolMessage)
    return cast(str, messages[0].content)


def test_tool_registers_only_the_five_public_inputs() -> None:
    tool = _tool()
    args: dict[str, Any] = tool.args  # type: ignore[no-any-return]
    assert set(args) == {
        "latitude",
        "longitude",
        "monthly_consumption_kwh",
        "roof_orientation",
        "roof_tilt_deg",
    }
    description = tool.description.casefold()
    assert "payback" not in description and "retorno" not in description


def test_tool_success_is_coordinate_free_json(monkeypatch: Any) -> None:
    class FakeEstimate:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return {
                "recommended_kwp": "1.51",
                "monthly_generation_kwh": ["100.00"] * 12,
                "annual_generation_kwh": "1200.00",
                "estimated_cost_brl": "4756.50",
                "assumptions": {"source": "NASA POWER"},
            }

    def fake_estimate(*_args: object, **_kwargs: object) -> FakeEstimate:
        return FakeEstimate()

    monkeypatch.setattr(
        "energia.chat.tools.solar.estimate_solar_system",
        fake_estimate,
    )
    content = _invoke()
    assert json.loads(content)["recommended_kwp"] == "1.51"
    assert all(value not in content for value in ("10.04", "20.06", "10.0", "20.1"))


def test_tool_uses_same_safe_message_for_expected_and_unexpected_errors(
    monkeypatch: Any,
) -> None:
    from energia.solar.sizing import SolarSizingError

    def raise_expected(*_args: object, **_kwargs: object) -> None:
        raise SolarSizingError("synthetic 10.04 20.06 failure 42")

    def raise_unexpected(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic 10.04 20.06 failure 42")

    monkeypatch.setattr(
        "energia.chat.tools.solar.estimate_solar_system",
        raise_expected,
    )
    expected = _invoke("expected-error")
    monkeypatch.setattr(
        "energia.chat.tools.solar.estimate_solar_system",
        raise_unexpected,
    )
    unexpected = _invoke("unexpected-error")

    assert expected == unexpected
    assert re.search(r"\d", expected) is None
    assert "{" not in expected and "R$" not in expected
    assert "synthetic" not in expected.casefold()
