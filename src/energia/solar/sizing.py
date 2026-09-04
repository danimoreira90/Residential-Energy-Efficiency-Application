"""energia.solar.sizing — pure PV feasibility sizing for residential v1.

Turns a validated location, average consumption, and roof geometry into a
continuous PV capacity, a 12-month generation profile, and an EPE planning
cost benchmark. Sprint 3 Task 3.2 (see docs/specs/sprint-3-solar-sizing.md,
ADR-009).

Pure domain module: no LangChain, no ChatState, no logging. Coordinates are
rounded to 0.1 degree before the single 2025 NASA POWER weather fetch and are
never placed in any returned value — see F1 in the spec. Catalog selection,
payback, and UI concerns are explicitly out of scope for this task.
"""
from __future__ import annotations

import math
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Literal, cast

import pandas as pd
import pvlib
from pydantic import BaseModel, ConfigDict, field_validator

from energia.solar.irradiance import get_hourly_weather

_YEAR = 2025
_MONTHS_PER_YEAR = 12
_TARGET_MARGIN = Decimal("1.10")
_CAPACITY_STEP = Decimal("0.01")
_MAX_CAPACITY_KWP = Decimal("75")
_COST_PER_KWP_BRL = Decimal("3150")
_CENTS = Decimal("0.01")
_COORDINATE_STEP = Decimal("0.1")

_PDC0_REF_W = 1000
_GAMMA_PDC = -0.004
_DC_AC_RATIO = 1.2
_INVERTER_ETA = 0.96
_EXPECTED_HOURS_2025 = 8760

_AZIMUTH_BY_ORIENTATION: dict[str, int] = {
    "N": 0,
    "NE": 45,
    "E": 90,
    "SE": 135,
    "S": 180,
    "SW": 225,
    "W": 270,
    "NW": 315,
}

_COST_SOURCE_URL = (
    "https://www.epe.gov.br/sites-pt/publicacoes-dados-abertos/publicacoes/"
    "PublicacoesArquivos/publicacao-305/topico-730/Apresentac%CC%A7o%CC%83es_"
    "Workshop%20da%20Previsa%CC%A3o%20de%20Carga%20-%201RQC%20PLAN%202025-2029.pdf"
)

_UNUSABLE_YIELD_MSG = (
    "Não foi possível calcular uma geração solar válida com os dados "
    "disponíveis. Tente novamente mais tarde."
)
_SCOPE_MSG = (
    "A capacidade estimada ultrapassa o limite de microgeração residencial "
    "atendido pela aplicação. Não vou estimar um sistema fora desse escopo."
)


class SolarSizingError(ValueError):
    """A solar sizing estimate could not be safely produced."""


def _reject_bool(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("value must be a number, not a boolean")
    return value


class SolarSizingInput(BaseModel):
    """Validated public input for :func:`estimate_solar_system`."""

    model_config = ConfigDict(frozen=True)

    latitude: float
    longitude: float
    monthly_consumption_kwh: Decimal
    roof_orientation: Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    roof_tilt_deg: Decimal = Decimal("15")

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _reject_boolean_coordinate(cls, value: object) -> object:
        return _reject_bool(value)

    @field_validator("latitude")
    @classmethod
    def _validate_latitude(cls, value: float) -> float:
        if not math.isfinite(value) or not -90 <= value <= 90:
            raise ValueError("latitude must be a finite value between -90 and 90")
        return value

    @field_validator("longitude")
    @classmethod
    def _validate_longitude(cls, value: float) -> float:
        if not math.isfinite(value) or not -180 <= value <= 180:
            raise ValueError("longitude must be a finite value between -180 and 180")
        return value

    @field_validator("monthly_consumption_kwh")
    @classmethod
    def _validate_consumption(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("monthly_consumption_kwh must be a finite positive value")
        return value

    @field_validator("roof_tilt_deg")
    @classmethod
    def _validate_tilt(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or not Decimal("0") <= value <= Decimal("90"):
            raise ValueError("roof_tilt_deg must be a finite value between 0 and 90")
        return value


class SolarSizingEstimate(BaseModel):
    """Public result of :func:`estimate_solar_system`."""

    model_config = ConfigDict(frozen=True)

    recommended_kwp: Decimal
    monthly_generation_kwh: list[Decimal]
    annual_generation_kwh: Decimal
    estimated_cost_brl: Decimal
    assumptions: dict[str, object]


def _round_coordinate(value: float) -> float:
    """Round a validated coordinate to 0.1 degree before it reaches NASA POWER."""
    return float(Decimal(str(value)).quantize(_COORDINATE_STEP, rounding=ROUND_HALF_UP))


def _assumptions() -> dict[str, object]:
    return {
        "model": (
            "pvlib PVWatts chain: interval-midpoint solar position, Erbs GHI "
            "decomposition, isotropic fixed-plane transposition, SAPM "
            "close_mount_glass_glass cell temperature, PVWatts DC "
            "(gamma_pdc=-0.004) with default PVWatts system losses, and the "
            "PVWatts inverter (eta_inv_nom=0.96, DC/AC ratio 1.2)."
        ),
        "reference_year": _YEAR,
        "weather_source": (
            "NASA POWER hourly point data is the external recipient of the "
            "requested coordinates, rounded to 0.1 degree precision before the "
            "single request for the fixed 2025 UTC reference year."
        ),
        "cost_source": (
            f"EPE 2025 residential PV cost benchmark ({_COST_SOURCE_URL}); a "
            "planning benchmark, not a vendor quotation."
        ),
        "limitations": (
            "Feasibility estimate from one historical reference year with "
            "generic PVWatts assumptions. Not a production forecast, an "
            "engineering design, or an equipment quote. Catalog equipment "
            "quantization is not applied."
        ),
        "catalog_applied": False,
    }


def estimate_solar_system(solar_input: SolarSizingInput) -> SolarSizingEstimate:
    """Estimate continuous PV capacity, monthly/annual generation, and cost.

    Implements the locked model in docs/specs/sprint-3-solar-sizing.md (F1-F7):
    a single rounded-coordinate 2025 NASA POWER fetch, interval-midpoint solar
    position, Erbs decomposition, isotropic transposition, SAPM
    close_mount_glass_glass cell temperature, and the exact per-kWp PVWatts
    chain (default losses before inverter clipping, DC/AC ratio 1.2).
    """
    rounded_latitude = _round_coordinate(solar_input.latitude)
    rounded_longitude = _round_coordinate(solar_input.longitude)
    weather = get_hourly_weather(rounded_latitude, rounded_longitude, _YEAR)

    midpoint_times = weather.index + pd.Timedelta(minutes=30)
    midpoint_weather = weather.copy()
    midpoint_weather.index = midpoint_times
    solar_position = pvlib.solarposition.get_solarposition(
        midpoint_times,
        latitude=solar_input.latitude,
        longitude=solar_input.longitude,
    )
    erbs_result = cast(
        pd.DataFrame,
        pvlib.irradiance.erbs(
            midpoint_weather["ghi"], solar_position["zenith"], midpoint_times
        ),
    )

    tilt = float(solar_input.roof_tilt_deg)
    azimuth = _AZIMUTH_BY_ORIENTATION[solar_input.roof_orientation]
    transposed = cast(
        pd.DataFrame,
        pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=azimuth,
            solar_zenith=solar_position["apparent_zenith"],
            solar_azimuth=solar_position["azimuth"],
            dni=erbs_result["dni"],
            ghi=midpoint_weather["ghi"],
            dhi=erbs_result["dhi"],
            model="isotropic",
        ),
    )
    poa_global = cast(pd.Series, transposed["poa_global"])

    temperature_params = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"][
        "close_mount_glass_glass"
    ]
    cell_temperature = cast(
        pd.Series,
        pvlib.temperature.sapm_cell(
            poa_global,
            midpoint_weather["temp_air"],
            midpoint_weather["wind_speed"],
            **temperature_params,
        ),
    )

    dc_power = cast(
        pd.Series,
        pvlib.pvsystem.pvwatts_dc(
            poa_global,
            cell_temperature,
            pdc0=_PDC0_REF_W,
            gamma_pdc=_GAMMA_PDC,
        ),
    )
    losses_pct = pvlib.pvsystem.pvwatts_losses()
    dc_after_losses = cast(pd.Series, dc_power * (1 - losses_pct / 100))

    inverter_pdc0 = (_PDC0_REF_W / _DC_AC_RATIO) / _INVERTER_ETA
    ac_power = pvlib.inverter.pvwatts(
        dc_after_losses, pdc0=inverter_pdc0, eta_inv_nom=_INVERTER_ETA
    )

    ac_values = [float(value) for value in ac_power]
    if len(ac_values) != _EXPECTED_HOURS_2025:
        raise SolarSizingError(_UNUSABLE_YIELD_MSG)
    if not all(math.isfinite(value) and value >= 0 for value in ac_values):
        raise SolarSizingError(_UNUSABLE_YIELD_MSG)
    if sum(ac_values) <= 0:
        raise SolarSizingError(_UNUSABLE_YIELD_MSG)

    monthly_yield_per_kwp_wh = ac_power.groupby(ac_power.index.month).sum()
    annual_yield_per_kwp_kwh = Decimal(str(float(ac_power.sum()))) / Decimal(1000)

    max_in_scope_monthly_consumption_kwh = (
        annual_yield_per_kwp_kwh * _MAX_CAPACITY_KWP / _MONTHS_PER_YEAR / _TARGET_MARGIN
    )
    if solar_input.monthly_consumption_kwh > max_in_scope_monthly_consumption_kwh:
        raise SolarSizingError(_SCOPE_MSG)

    target_kwh = solar_input.monthly_consumption_kwh * _MONTHS_PER_YEAR * _TARGET_MARGIN
    capacity_unrounded = target_kwh / annual_yield_per_kwp_kwh

    if capacity_unrounded > _MAX_CAPACITY_KWP:
        raise SolarSizingError(_SCOPE_MSG)

    recommended_kwp = capacity_unrounded.quantize(_CAPACITY_STEP, rounding=ROUND_CEILING)

    monthly_generation_kwh: list[Decimal] = []
    for month in range(1, 13):
        month_wh_per_kwp = Decimal(str(float(monthly_yield_per_kwp_wh.loc[month])))
        month_kwh = (month_wh_per_kwp * recommended_kwp) / Decimal(1000)
        monthly_generation_kwh.append(month_kwh.quantize(_CENTS, rounding=ROUND_HALF_UP))

    annual_generation_kwh = sum(monthly_generation_kwh, Decimal("0"))
    estimated_cost_brl = (recommended_kwp * _COST_PER_KWP_BRL).quantize(
        _CENTS, rounding=ROUND_HALF_UP
    )

    return SolarSizingEstimate(
        recommended_kwp=recommended_kwp,
        monthly_generation_kwh=monthly_generation_kwh,
        annual_generation_kwh=annual_generation_kwh,
        estimated_cost_brl=estimated_cost_brl,
        assumptions=_assumptions(),
    )
