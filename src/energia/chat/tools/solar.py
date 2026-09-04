"""estimate_solar_system — residential solar sizing LangChain tool.

Thin wrapper over the pure `energia.solar.sizing` domain module. Exposes only
the five public inputs (latitude, longitude, monthly_consumption_kwh,
roof_orientation, roof_tilt_deg); state and tool_call_id are LangGraph
injections, not model-visible arguments (F8/F9).

HR-5 honesty contract: every number in the success response comes from
`estimate_solar_system` (the domain function) — nothing is computed here.
The wrapper returns JSON only on success; sizing/generation/cost only, never
a payback claim (Task 3.3 territory).

HR-6 / F8 safety contract: expected (`SolarSizingError`) and unexpected
exceptions are both converted to ONE fixed, number-free PT-BR ToolMessage.
No exception text, and no raw or rounded coordinate, ever reaches the model
or the local audit log through this wrapper.
"""

from __future__ import annotations

import json
import unicodedata
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool  # type: ignore[reportUnknownVariableType]
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, field_validator

from energia.chat.state import ChatState
from energia.chat.tools.registry import register_tool
from energia.solar.payback import (
    ConnectionType,
    FioBProvenance,
    SolarPaybackInput,
    TariffProvenance,
    calculate_solar_payback,
    decimal_within_model_bounds,
    is_identity_shaped_numeric,
)
from energia.solar.sizing import SolarSizingInput, estimate_solar_system
from energia.tariff.gd import FioBSnapshot, load_fio_b_snapshot
from energia.tariff.snapshot import TariffSnapshot, load_snapshot

_SAFE_ERROR_MSG = (
    "Não consegui calcular o dimensionamento solar agora. Verifique a "
    "localização, o consumo médio e os dados do telhado, e tente novamente."
)
_SAFE_PAYBACK_ERROR_MSG = (
    "Não consegui calcular o retorno solar com as premissas fornecidas. "
    "Revise os dados e tente novamente."
)


class SolarPaybackToolInput(BaseModel):
    """Model-visible inputs for the residential solar-payback tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    monthly_consumption_kwh: Decimal
    monthly_generation_kwh: list[Decimal]
    system_cost_brl: Decimal
    distributor: str
    connection_year: int
    connection_type: ConnectionType
    real_tariff_inflation_rate: Decimal = Decimal("0.05")
    annual_generation_degradation_rate: Decimal = Decimal("0.005")
    tool_call_id: Annotated[str, InjectedToolCallId] = ""

    @field_validator(
        "monthly_consumption_kwh",
        "system_cost_brl",
        "real_tariff_inflation_rate",
        "annual_generation_degradation_rate",
        mode="before",
    )
    @classmethod
    def _reject_unsafe_number(cls, value: object) -> object:
        if isinstance(value, bool) or is_identity_shaped_numeric(value):
            raise ValueError("invalid numeric value")
        return value

    @field_validator("monthly_generation_kwh", mode="before")
    @classmethod
    def _validate_generation_container(cls, value: object) -> object:
        if not isinstance(value, list):
            raise ValueError("monthly generation must be a list of numbers")
        values = cast(list[object], value)
        if any(isinstance(item, bool) or is_identity_shaped_numeric(item) for item in values):
            raise ValueError("monthly generation must be a list of numbers")
        return values

    @field_validator("monthly_consumption_kwh", "system_cost_brl")
    @classmethod
    def _validate_positive_decimal(cls, value: Decimal) -> Decimal:
        if not decimal_within_model_bounds(value) or value <= 0:
            raise ValueError("value must be finite, positive, and within model bounds")
        return value

    @field_validator("monthly_generation_kwh")
    @classmethod
    def _validate_generation(cls, values: list[Decimal]) -> list[Decimal]:
        if len(values) != 12:
            raise ValueError("monthly generation must contain twelve values")
        if any(not decimal_within_model_bounds(value) or value < 0 for value in values):
            raise ValueError("monthly generation must be finite, non-negative, and bounded")
        if not any(value > 0 for value in values):
            raise ValueError("monthly generation must contain a positive value")
        return values

    @field_validator("distributor")
    @classmethod
    def _validate_distributor(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("distributor must be between one and one hundred characters")
        return value

    @field_validator("connection_year", mode="before")
    @classmethod
    def _validate_connection_year_type(cls, value: object) -> object:
        if is_identity_shaped_numeric(value) or type(value) is not int:
            raise ValueError("connection year must be an integer")
        return value

    @field_validator("connection_year")
    @classmethod
    def _validate_connection_year(cls, value: int) -> int:
        if value < 2023:
            raise ValueError("connection year is outside the supported scope")
        return value

    @field_validator("real_tariff_inflation_rate", "annual_generation_degradation_rate")
    @classmethod
    def _validate_rate(cls, value: Decimal) -> Decimal:
        if (
            not decimal_within_model_bounds(value)
            or not Decimal("0") <= value < Decimal("1")
        ):
            raise ValueError("rate must be finite and in the supported range")
        return value


def _msg(content: str, tool_call_id: str) -> Command[Any]:
    return Command(update={"messages": [ToolMessage(content=content, tool_call_id=tool_call_id)]})


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return (
        "".join(char for char in decomposed if not unicodedata.combining(char)).casefold().strip()
    )


def _resolve_payback_input(
    public: SolarPaybackToolInput,
    tariff: TariffSnapshot,
    fio_b: FioBSnapshot,
) -> SolarPaybackInput:
    tariff_names = (tariff.distributor, *tariff.aliases)
    if (
        not any(_normalize(public.distributor) == _normalize(name) for name in tariff_names)
        or tariff.tariff_group != "B1"
        or tariff.unit != "BRL_per_MWh"
        or "convencional" not in tariff.subclasses
        or not tariff.subclasses["convencional"].v1_supported
        or fio_b.tariff_group != "B1"
        or fio_b.modality != "Convencional"
        or fio_b.consumer_class != "Residencial"
        or fio_b.consumer_subclass != "Residencial"
        or fio_b.unit != "BRL_per_MWh"
        or not any(_normalize(fio_b.distributor) == _normalize(name) for name in tariff_names)
        or max(tariff.effective_from, fio_b.effective_from)
        > min(tariff.effective_to, fio_b.effective_to)
    ):
        raise ValueError("unsupported or conflicting tariff snapshots")

    return SolarPaybackInput(
        monthly_consumption_kwh=public.monthly_consumption_kwh,
        monthly_generation_kwh=public.monthly_generation_kwh,
        system_cost_brl=public.system_cost_brl,
        distributor=tariff.distributor,
        connection_year=public.connection_year,
        connection_type=public.connection_type,
        base_tariff_brl_per_kwh=tariff.base_tariff_brl_per_kwh("convencional"),
        tusd_fio_b_brl_per_mwh=fio_b.tusd_fio_b_brl_per_mwh,
        real_tariff_inflation_rate=public.real_tariff_inflation_rate,
        annual_generation_degradation_rate=public.annual_generation_degradation_rate,
        tariff_provenance=TariffProvenance(
            url=tariff.source.url,
            effective_from=tariff.effective_from,
            effective_to=tariff.effective_to,
        ),
        fio_b_provenance=FioBProvenance(
            url=fio_b.source.url,
            resource_id=fio_b.source.resource_id,
            resource_hash=fio_b.source.resource_hash,
            effective_from=fio_b.effective_from,
            effective_to=fio_b.effective_to,
        ),
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


@tool("solar_payback", args_schema=SolarPaybackToolInput)
def solar_payback_tool(
    monthly_consumption_kwh: Decimal,
    monthly_generation_kwh: list[Decimal],
    system_cost_brl: Decimal,
    distributor: str,
    connection_year: int,
    connection_type: ConnectionType,
    real_tariff_inflation_rate: Decimal = Decimal("0.05"),
    annual_generation_degradation_rate: Decimal = Decimal("0.005"),
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> Command[Any]:
    """Calcula o retorno de um sistema solar residencial B1 da Enel RJ.

    Use somente quando consumo, geração mensal, custo do sistema,
    distribuidora, ano e tipo de ligação estiverem disponíveis. A projeção
    usa tarifas locais versionadas e devolve o fluxo de caixa em JSON.
    """
    try:
        public = SolarPaybackToolInput(
            monthly_consumption_kwh=monthly_consumption_kwh,
            monthly_generation_kwh=monthly_generation_kwh,
            system_cost_brl=system_cost_brl,
            distributor=distributor,
            connection_year=connection_year,
            connection_type=connection_type,
            real_tariff_inflation_rate=real_tariff_inflation_rate,
            annual_generation_degradation_rate=annual_generation_degradation_rate,
            tool_call_id=tool_call_id,
        )
        payback_input = _resolve_payback_input(
            public,
            load_snapshot("enel_rj"),
            load_fio_b_snapshot(),
        )
        estimate = calculate_solar_payback(payback_input)
        body = json.dumps(estimate.model_dump(mode="json"), ensure_ascii=False)
    except Exception:
        return _msg(_SAFE_PAYBACK_ERROR_MSG, tool_call_id)

    return _msg(body, tool_call_id)


def _safe_payback_validation_error(_error: Exception) -> str:
    return _SAFE_PAYBACK_ERROR_MSG


solar_payback_tool.handle_validation_error = _safe_payback_validation_error
register_tool(solar_payback_tool)  # type: ignore[arg-type]
