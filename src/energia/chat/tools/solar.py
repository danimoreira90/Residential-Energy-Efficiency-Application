"""estimate_solar_system — residential solar sizing LangChain tool.

Thin wrapper over the pure `energia.solar.sizing` domain module. Exposes only
the five public inputs (latitude, longitude, monthly_consumption_kwh,
roof_orientation, roof_tilt_deg); state and tool_call_id are LangGraph
injections, not model-visible arguments (F8/F9).

HR-5 honesty contract: every number in the success response comes from
`estimate_solar_system` (the domain function) — nothing is computed here.
The wrapper returns JSON only on success; sizing/generation/cost only, never
a payback claim (Task 3.4 territory).

HR-6 / F8 safety contract: expected (`SolarSizingError`) and unexpected
exceptions are both converted to ONE fixed, number-free PT-BR ToolMessage.
No exception text, and no raw or rounded coordinate, ever reaches the model
or the local audit log through this wrapper.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool
from energia.solar.sizing import SolarSizingInput, estimate_solar_system

_SAFE_ERROR_MSG = (
    "Não consegui calcular o dimensionamento solar agora. Verifique a "
    "localização, o consumo médio e os dados do telhado, e tente novamente."
)


def _msg(content: str, tool_call_id: str) -> Command[Any]:
    return Command(
        update={"messages": [ToolMessage(content=content, tool_call_id=tool_call_id)]}
    )


@tool("estimate_solar_system")
def estimate_solar_system_tool(
    state: Annotated[ChatState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    latitude: float,
    longitude: float,
    monthly_consumption_kwh: Decimal,
    roof_orientation: Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
    roof_tilt_deg: Decimal = Decimal("15"),
) -> Command[Any]:
    """Estima a potência de um sistema fotovoltaico residencial.

    Use quando o usuário quiser saber quantos kWp instalar, quanto o sistema
    geraria por mês/ano, ou uma estimativa de custo de instalação. Exemplos:
    "quantos kWp eu precisaria?", "quanto geraria de energia solar aqui?",
    "quanto custaria instalar painéis solares na minha casa?".

    Args:
      latitude: latitude em graus decimais, entre -90 e 90.
      longitude: longitude em graus decimais, entre -180 e 180.
      monthly_consumption_kwh: consumo médio mensal em kWh, maior que zero.
      roof_orientation: orientação do telhado — N, NE, E, SE, S, SW, W ou NW.
      roof_tilt_deg: inclinação do telhado em graus, entre 0 e 90. Padrão 15.

    Devolve a potência contínua recomendada (kWp), a geração mensal e anual
    estimada (kWh) e um benchmark de custo de instalação (EPE). NÃO é uma
    cotação de equipamento, não seleciona catálogo, e não calcula quanto
    tempo o sistema levaria para se pagar.
    """
    try:
        solar_input = SolarSizingInput(
            latitude=latitude,
            longitude=longitude,
            monthly_consumption_kwh=monthly_consumption_kwh,
            roof_orientation=roof_orientation,
            roof_tilt_deg=roof_tilt_deg,
        )
        estimate = estimate_solar_system(solar_input)
        body = json.dumps(estimate.model_dump(mode="json"), ensure_ascii=False)
    except Exception:
        return _msg(_SAFE_ERROR_MSG, tool_call_id)

    return _msg(body, tool_call_id)


register_tool(estimate_solar_system_tool)  # type: ignore[arg-type]
