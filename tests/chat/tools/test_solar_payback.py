"""RED contracts for the registered residential solar-payback tool."""
from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from energia.chat.state import ChatState
from energia.chat.tools import ALL_TOOLS
from energia.tariff.gd import FioBSnapshot, load_fio_b_snapshot
from energia.tariff.snapshot import TariffSnapshot, load_snapshot

_SAFE = (
    "Não consegui calcular o retorno solar com as premissas fornecidas. "
    "Revise os dados e tente novamente."
)
_ARGS: dict[str, object] = {
    "monthly_consumption_kwh": "100",
    "monthly_generation_kwh": ["100"] * 12,
    "system_cost_brl": "1000",
    "distributor": "Enel Rio",
    "connection_year": 2026,
    "connection_type": "trifasica",
    "real_tariff_inflation_rate": "0.05",
    "annual_generation_degradation_rate": "0.005",
}


def _tool() -> Any:
    for candidate in ALL_TOOLS:
        if candidate.name == "solar_payback":
            return candidate
    raise AssertionError("solar_payback is not registered")


def _invoke(args: dict[str, object], call_id: str = "payback-call") -> ToolMessage:
    result = _tool().invoke(
        {"name": "solar_payback", "args": args, "id": call_id, "type": "tool_call"}
    )
    assert isinstance(result, Command)
    update: dict[str, Any] = result.update  # type: ignore[assignment]
    messages: list[Any] = update["messages"]
    assert len(messages) == 1 and isinstance(messages[0], ToolMessage)
    return messages[0]


def _invoke_through_graph(args: dict[str, object], call_id: str) -> ToolMessage:
    builder = StateGraph(ChatState)
    builder.add_node("tools", ToolNode([_tool()]))
    builder.add_edge(START, "tools")
    result = builder.compile().invoke(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "solar_payback",
                            "args": args,
                            "id": call_id,
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "user_id": "synthetic-user",
            "conversation_id": "synthetic-conversation",
            "tokens_used": 0,
        }
    )
    message = result["messages"][-1]
    assert isinstance(message, ToolMessage)
    return message


def test_tool_registers_exactly_eight_model_visible_inputs() -> None:
    tool = _tool()
    assert set(tool.args) == {
        "monthly_consumption_kwh",
        "monthly_generation_kwh",
        "system_cost_brl",
        "distributor",
        "connection_year",
        "connection_type",
        "real_tariff_inflation_rate",
        "annual_generation_degradation_rate",
    }
    assert callable(tool.handle_validation_error)


def test_enel_alias_resolves_local_rates_and_success_is_json(monkeypatch: Any) -> None:
    captured: list[Any] = []

    class FakeEstimate:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return {"payback_year": 2, "irr_annual_percent": "12.34"}

    def fake_calculate(value: Any) -> FakeEstimate:
        captured.append(value)
        return FakeEstimate()

    monkeypatch.setattr("energia.chat.tools.solar.calculate_solar_payback", fake_calculate)
    message = _invoke(dict(_ARGS))

    assert message.tool_call_id == "payback-call"
    assert json.loads(cast(str, message.content))["payback_year"] == 2
    assert len(captured) == 1
    assert captured[0].base_tariff_brl_per_kwh == Decimal("1.0611")
    assert str(captured[0].tusd_fio_b_brl_per_mwh) == "361.02479751700002"


def test_all_post_validation_failures_use_one_number_free_message(monkeypatch: Any) -> None:
    from energia.solar.payback import SolarPaybackError

    def fail(exc: Exception) -> None:
        def raise_failure(_value: Any) -> None:
            raise exc

        monkeypatch.setattr("energia.chat.tools.solar.calculate_solar_payback", raise_failure)

    outputs: list[str] = []
    fail(SolarPaybackError("synthetic failure 42 R$"))
    outputs.append(cast(str, _invoke(dict(_ARGS), "expected").content))
    fail(RuntimeError("synthetic failure 99 R$"))
    outputs.append(cast(str, _invoke(dict(_ARGS), "unexpected").content))
    unmatched = dict(_ARGS, distributor="Unknown synthetic distributor 123")
    outputs.append(cast(str, _invoke(unmatched, "unmatched").content))

    assert outputs == [_SAFE, _SAFE, _SAFE]
    assert re.search(r"\d|R\$|synthetic|Unknown", "".join(outputs), re.IGNORECASE) is None


@pytest.mark.parametrize(
    ("invalid", "forbidden_marker"),
    [
        (dict(_ARGS, monthly_consumption_kwh="offending-value-987"), "987"),
        (dict(_ARGS, home_address="synthetic-home-marker"), "synthetic-home-marker"),
        (dict(_ARGS, system_cost_brl="1E+100"), "100"),
        (dict(_ARGS, monthly_consumption_kwh="99999999999"), "99999999999"),
        (dict(_ARGS, monthly_consumption_kwh=" 99999999999 "), "99999999999"),
        (
            dict(_ARGS, monthly_generation_kwh=["99999999999"] + ["100"] * 11),
            "99999999999",
        ),
        (dict(_ARGS, system_cost_brl="99999999999999"), "99999999999999"),
        (dict(_ARGS, system_cost_brl=" 99999999999999 "), "99999999999999"),
        (dict(_ARGS, connection_year=99999999999), "99999999999"),
    ],
)
def test_real_tool_node_returns_safe_validation_message(
    invalid: dict[str, object], forbidden_marker: str
) -> None:
    message = _invoke_through_graph(invalid, "invalid-payback-call")
    assert message.tool_call_id == "invalid-payback-call"
    assert message.content == _SAFE
    assert forbidden_marker not in cast(str, message.content)


@pytest.mark.parametrize("case", ["conflict", "non_overlap"])
def test_conflicting_or_non_overlapping_snapshots_fail_safely(
    monkeypatch: Any, case: str
) -> None:
    tariff = load_snapshot("enel_rj")
    fio_b = load_fio_b_snapshot()
    if case == "conflict":
        fio_b = fio_b.model_copy(update={"distributor": "SYNTHETIC OTHER"})
    else:
        fio_b = fio_b.model_copy(
            update={
                "effective_from": date(2028, 1, 1),
                "effective_to": date(2028, 12, 31),
            }
        )

    def fake_load_tariff(_slug: str) -> TariffSnapshot:
        return tariff

    def fake_load_fio_b() -> FioBSnapshot:
        return fio_b

    monkeypatch.setattr("energia.chat.tools.solar.load_snapshot", fake_load_tariff)
    monkeypatch.setattr("energia.chat.tools.solar.load_fio_b_snapshot", fake_load_fio_b)
    assert _invoke(dict(_ARGS), case).content == _SAFE
