"""Pure 25-year residential solar payback calculation.

The model follows the bounded Task 3.3 contract: 300 monthly billing cycles,
60-month FIFO credits, Group B availability floors, and the versioned
Lei 14.300 compensation schedule. It performs no I/O and uses ``Decimal`` for
all energy, tariff, money, and IRR arithmetic.
"""
from __future__ import annotations

from collections import deque
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, DecimalException, localcontext
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from energia.tariff.gd import compensation_charge

ConnectionType = Literal[
    "monofasica_ou_bifasica_2_condutores",
    "bifasica_3_condutores",
    "trifasica",
]

_YEARS = 25
_MONTHS_PER_YEAR = 12
_HORIZON_MONTHS = _YEARS * _MONTHS_PER_YEAR
_CREDIT_LIFETIME_MONTHS = 60
_MWH_PER_KWH = Decimal("1000")
_CENTS = Decimal("0.01")
_KWH_STEP = Decimal("0.01")
_PERCENT_STEP = Decimal("0.01")
_IRR_LOW = Decimal("-0.999999")
_IRR_HIGH = Decimal("1")
_IRR_TOLERANCE = Decimal("0.00000001")
_WORKING_PRECISION = 50
_MAX_DECIMAL_DIGITS = 28
_MIN_DECIMAL_ADJUSTED = -18
_MAX_DECIMAL_ADJUSTED = 18

_AVAILABILITY_KWH: dict[ConnectionType, Decimal] = {
    "monofasica_ou_bifasica_2_condutores": Decimal("30"),
    "bifasica_3_condutores": Decimal("50"),
    "trifasica": Decimal("100"),
}

_LEI_14300_URL = "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14300.htm"
_ANEEL_GD_URL = "https://www.gov.br/aneel/pt-br/assuntos/geracao-distribuida"
_ANEEL_REN_1000_URL = "https://www2.aneel.gov.br/cedoc/ren20211000.pdf"
_ARTICLE_17_RULEMAKING_URL = (
    "https://www.gov.br/fazenda/pt-br/composicao/orgaos/"
    "secretaria-de-reformas-economicas/manifestacoes-em-consultas-publicas-de-"
    "orgaos-reguladores/2026/agencia-nacional-de-energia-eletrica-aneel/"
    "sei_58000857_nota_tecnica_958-1-_260325_090518.pdf/view"
)


def is_identity_shaped_numeric(value: object) -> bool:
    """Return whether a raw numeric input has a CPF/CNPJ-shaped digit count."""
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        return False
    raw = str(value).strip()
    return len(raw) in (11, 14) and raw.isascii() and raw.isdigit()


class SolarPaybackError(ValueError):
    """The validated inputs produced an invalid payback model result."""


class TariffProvenance(BaseModel):
    """Source and validity window for the regulated base tariff."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(min_length=1)
    effective_from: date
    effective_to: date

    @model_validator(mode="after")
    def _validate_window(self) -> TariffProvenance:
        if self.effective_to < self.effective_from:
            raise ValueError("tariff provenance validity window is reversed")
        return self


class FioBProvenance(BaseModel):
    """Source and validity window for the reviewed ANEEL Fio B component."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    resource_hash: str = Field(min_length=1)
    effective_from: date
    effective_to: date

    @model_validator(mode="after")
    def _validate_window(self) -> FioBProvenance:
        if self.effective_to < self.effective_from:
            raise ValueError("Fio B provenance validity window is reversed")
        return self


class SolarPaybackInput(BaseModel):
    """Validated inputs for :func:`calculate_solar_payback`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    monthly_consumption_kwh: Decimal
    monthly_generation_kwh: list[Decimal]
    system_cost_brl: Decimal
    distributor: str
    connection_year: int
    connection_type: ConnectionType
    base_tariff_brl_per_kwh: Decimal
    tusd_fio_b_brl_per_mwh: Decimal
    real_tariff_inflation_rate: Decimal = Decimal("0.05")
    annual_generation_degradation_rate: Decimal = Decimal("0.005")
    tariff_provenance: TariffProvenance
    fio_b_provenance: FioBProvenance

    @field_validator(
        "monthly_consumption_kwh",
        "system_cost_brl",
        "base_tariff_brl_per_kwh",
        "tusd_fio_b_brl_per_mwh",
        "real_tariff_inflation_rate",
        "annual_generation_degradation_rate",
        mode="before",
    )
    @classmethod
    def _reject_unsafe_number(cls, value: object) -> object:
        if isinstance(value, bool) or is_identity_shaped_numeric(value):
            raise ValueError("invalid numeric value")
        return value

    @field_validator("connection_year", mode="before")
    @classmethod
    def _validate_connection_year_type(cls, value: object) -> object:
        if is_identity_shaped_numeric(value) or type(value) is not int:
            raise ValueError("connection_year must be an integer")
        return value

    @field_validator("monthly_generation_kwh", mode="before")
    @classmethod
    def _reject_invalid_generation_container(cls, value: object) -> object:
        if not isinstance(value, list):
            raise ValueError("monthly_generation_kwh must be a list")
        values = cast(list[object], value)
        if any(isinstance(item, bool) or is_identity_shaped_numeric(item) for item in values):
            raise ValueError("invalid generation value")
        return values

    @field_validator(
        "monthly_consumption_kwh",
        "system_cost_brl",
        "base_tariff_brl_per_kwh",
        "tusd_fio_b_brl_per_mwh",
    )
    @classmethod
    def _validate_positive_decimal(cls, value: Decimal) -> Decimal:
        if not decimal_within_model_bounds(value) or value <= 0:
            raise ValueError("value must be finite, positive, and within model bounds")
        return value

    @field_validator("system_cost_brl")
    @classmethod
    def _validate_system_cost_cent(cls, value: Decimal) -> Decimal:
        if value.quantize(_CENTS, rounding=ROUND_HALF_UP) == Decimal("0.00"):
            raise ValueError("system_cost_brl must round to at least one cent")
        return value

    @field_validator("monthly_generation_kwh")
    @classmethod
    def _validate_generation(cls, values: list[Decimal]) -> list[Decimal]:
        if len(values) != _MONTHS_PER_YEAR:
            raise ValueError("monthly_generation_kwh must contain exactly twelve values")
        if any(not decimal_within_model_bounds(value) or value < 0 for value in values):
            raise ValueError("generation values must be finite, non-negative, and bounded")
        if not any(value > 0 for value in values):
            raise ValueError("at least one generation value must be positive")
        return values

    @field_validator("real_tariff_inflation_rate", "annual_generation_degradation_rate")
    @classmethod
    def _validate_rate(cls, value: Decimal) -> Decimal:
        if (
            not decimal_within_model_bounds(value)
            or not Decimal("0") <= value < Decimal("1")
        ):
            raise ValueError("rate must be finite and in [0, 1)")
        return value

    @field_validator("connection_year")
    @classmethod
    def _validate_connection_year(cls, value: int) -> int:
        if value < 2023:
            raise ValueError("connection_year must be at least 2023")
        return value

    @field_validator("distributor")
    @classmethod
    def _validate_distributor(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("distributor must be between one and one hundred characters")
        return value

    @model_validator(mode="after")
    def _validate_fio_b_component(self) -> SolarPaybackInput:
        fio_b_brl_per_kwh = self.tusd_fio_b_brl_per_mwh / _MWH_PER_KWH
        if fio_b_brl_per_kwh > self.base_tariff_brl_per_kwh:
            raise ValueError("TUSD Fio B must not exceed the regulated base tariff")
        return self


class AnnualCashFlow(BaseModel):
    """One reported calendar year of the payback projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    projection_year: int
    calendar_year: int
    generation_kwh: Decimal
    compensated_kwh: Decimal
    expired_credit_kwh: Decimal
    ending_credit_kwh: Decimal
    baseline_energy_cost_brl: Decimal
    solar_energy_cost_brl: Decimal
    net_cash_flow_brl: Decimal
    cumulative_cash_flow_brl: Decimal
    compensation_charge_fraction: Decimal
    regulatory_basis: str


class SolarPaybackEstimate(BaseModel):
    """Auditable 25-year residential solar payback result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_outlay_brl: Decimal
    annual_cash_flows: list[AnnualCashFlow]
    payback_year: int | None
    irr_annual_percent: Decimal | None
    assumptions: dict[str, object]


def decimal_within_model_bounds(value: Decimal) -> bool:
    """Keep input size and arithmetic cost bounded before entering the fixed context."""
    if not value.is_finite():
        return False
    digits = value.as_tuple().digits
    return len(digits) <= _MAX_DECIMAL_DIGITS and (
        value.is_zero() or _MIN_DECIMAL_ADJUSTED <= value.adjusted() <= _MAX_DECIMAL_ADJUSTED
    )


def _round(value: Decimal, step: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = _WORKING_PRECISION
        return value.quantize(step, rounding=ROUND_HALF_UP)


def _irr_annual_percent(initial_outlay: Decimal, annual_flows: list[Decimal]) -> Decimal | None:
    if not any(flow > 0 for flow in annual_flows):
        return None

    def npv(rate: Decimal) -> Decimal:
        factor = Decimal("1") + rate
        total = -initial_outlay
        discount = factor
        for flow in annual_flows:
            total += flow / discount
            discount *= factor
        return total

    try:
        with localcontext() as context:
            context.prec = _WORKING_PRECISION
            low = _IRR_LOW
            high = _IRR_HIGH
            low_npv = npv(low)
            if not low_npv.is_finite() or low_npv <= 0:
                return None

            high_npv = npv(high)
            for _ in range(20):
                if not high_npv.is_finite() or high_npv <= 0:
                    break
                high *= 2
                high_npv = npv(high)
            if not high_npv.is_finite() or high_npv > 0:
                return None

            midpoint = (low + high) / 2
            for _ in range(256):
                if high - low <= _IRR_TOLERANCE:
                    midpoint = (low + high) / 2
                    break
                midpoint = (low + high) / 2
                if not midpoint.is_finite():
                    return None
                midpoint_npv = npv(midpoint)
                if not midpoint_npv.is_finite():
                    return None
                if midpoint_npv == 0:
                    break
                if midpoint_npv > 0:
                    low = midpoint
                else:
                    high = midpoint
            else:
                return None
            return _round(midpoint * Decimal("100"), _PERCENT_STEP)
    except (DecimalException, OverflowError):
        return None


def _assumptions(payback_input: SolarPaybackInput) -> dict[str, object]:
    return {
        "inputs_and_units": {
            "monthly_consumption_kwh": payback_input.monthly_consumption_kwh,
            "monthly_generation_kwh": payback_input.monthly_generation_kwh,
            "system_cost_brl": payback_input.system_cost_brl,
            "distributor": payback_input.distributor,
            "connection_year": payback_input.connection_year,
            "connection_type": payback_input.connection_type,
            "base_tariff_brl_per_kwh": payback_input.base_tariff_brl_per_kwh,
            "tusd_fio_b_brl_per_mwh": payback_input.tusd_fio_b_brl_per_mwh,
            "real_tariff_inflation_rate": payback_input.real_tariff_inflation_rate,
            "annual_generation_degradation_rate": (
                payback_input.annual_generation_degradation_rate
            ),
        },
        "tariff_provenance": payback_input.tariff_provenance.model_dump(mode="json"),
        "fio_b_provenance": payback_input.fio_b_provenance.model_dump(mode="json"),
        "legal_sources": {
            "Lei 14.300/2022": _LEI_14300_URL,
            "ANEEL distributed generation guidance": _ANEEL_GD_URL,
            "ANEEL REN 1.000/2021": _ANEEL_REN_1000_URL,
            "Article 17 rulemaking": _ARTICLE_17_RULEMAKING_URL,
        },
        "fixed_model": {
            "horizon_months": _HORIZON_MONTHS,
            "horizon_years": _YEARS,
            "credit_lifetime_months": _CREDIT_LIFETIME_MONTHS,
            "availability_floor_kwh": _AVAILABILITY_KWH,
        },
        "formulas": {
            "tariff_y": (
                "base_tariff_brl_per_kwh * (1 + real_tariff_inflation_rate) "
                "** (projection_year - 1)"
            ),
            "fio_b_y": (
                "(tusd_fio_b_brl_per_mwh / 1000) * "
                "(1 + real_tariff_inflation_rate) ** (projection_year - 1)"
            ),
            "generation_y": (
                "monthly_generation_kwh * (1 - annual_generation_degradation_rate) "
                "** (projection_year - 1)"
            ),
            "baseline_month_brl": (
                "max(monthly_consumption_kwh, availability_kwh) * tariff_y"
            ),
            "solar_month_brl": (
                "max(availability_kwh * tariff_y, uncompensated_kwh * tariff_y + "
                "compensated_kwh * fio_b_y * compensation_charge_fraction)"
            ),
            "net_cash_flow_brl": "baseline_energy_cost_brl - solar_energy_cost_brl",
            "payback": (
                "first whole projection_year where cumulative_cash_flow_brl >= 0"
            ),
            "npv": "-initial_outlay_brl + sum(annual_cash_flow_t / (1 + rate) ** t)",
        },
        "irr_solver": {
            "low": str(_IRR_LOW),
            "initial_high": str(_IRR_HIGH),
            "max_high_expansions": 20,
            "max_bisections": 256,
            "tolerance": "0.00000001",
        },
        "credit_ledger": (
            "FIFO credits expire after exactly 60 monthly cycles: a lot created after "
            "month 0 allocation is usable through month 59 and expires before month 60."
        ),
        "network_compensation": (
            "All compensated energy is conservatively treated as network-compensated "
            "because no hourly load shape is available."
        ),
        "post_2028": (
            "conservative_post_2028_planning_scenario applies 100% of the versioned "
            "TUSD_FioB component pending final Article 17 regulation; it is not current law."
        ),
        "rounding": (
            "Unrounded monthly Decimal values are aggregated annually, then BRL, kWh, "
            "and percentage outputs are rounded to 0.01 with ROUND_HALF_UP."
        ),
        "omitted_costs": (
            "financing, maintenance, insurance, replacement, taxes, PIS/COFINS, ICMS, "
            "COSIP/CIP, tariff flags, batteries, curtailment, outages, and residual value"
        ),
        "terminal_value": (
            "Credits remaining after month 300 have no terminal value and payback is not "
            "extrapolated beyond year 25."
        ),
    }


def calculate_solar_payback(payback_input: SolarPaybackInput) -> SolarPaybackEstimate:
    """Calculate the fixed 300-month residential solar payback projection."""
    with localcontext() as context:
        context.prec = _WORKING_PRECISION
        initial_outlay = _round(payback_input.system_cost_brl, _CENTS)
        cumulative_cash_flow = -initial_outlay
        annual_rows: list[AnnualCashFlow] = []
        ledger: deque[tuple[int, Decimal]] = deque()
        availability_kwh = _AVAILABILITY_KWH[payback_input.connection_type]

        for year_index in range(_YEARS):
            projection_year = year_index + 1
            calendar_year = payback_input.connection_year + year_index
            charge = compensation_charge(calendar_year)
            tariff_factor = (
                Decimal("1") + payback_input.real_tariff_inflation_rate
            ) ** year_index
            generation_factor = (
                Decimal("1") - payback_input.annual_generation_degradation_rate
            ) ** year_index
            tariff = payback_input.base_tariff_brl_per_kwh * tariff_factor
            fio_b = payback_input.tusd_fio_b_brl_per_mwh / _MWH_PER_KWH * tariff_factor

            annual_generation = Decimal("0")
            annual_compensated = Decimal("0")
            annual_expired = Decimal("0")
            annual_baseline_cost = Decimal("0")
            annual_solar_cost = Decimal("0")
            annual_savings = Decimal("0")

            for month_in_year, base_generation in enumerate(
                payback_input.monthly_generation_kwh
            ):
                month_index = year_index * _MONTHS_PER_YEAR + month_in_year
                while ledger and ledger[0][0] + _CREDIT_LIFETIME_MONTHS <= month_index:
                    _, expired_kwh = ledger.popleft()
                    annual_expired += expired_kwh

                generation = base_generation * generation_factor
                remaining_consumption = payback_input.monthly_consumption_kwh
                compensated = Decimal("0")

                while ledger and remaining_consumption > 0:
                    creation_month, credit_kwh = ledger.popleft()
                    used_kwh = min(credit_kwh, remaining_consumption)
                    compensated += used_kwh
                    remaining_consumption -= used_kwh
                    if credit_kwh > used_kwh:
                        ledger.appendleft((creation_month, credit_kwh - used_kwh))
                        break

                current_generation_used = min(generation, remaining_consumption)
                compensated += current_generation_used
                remaining_consumption -= current_generation_used
                surplus = generation - current_generation_used
                if surplus > 0:
                    ledger.append((month_index, surplus))

                baseline_month = max(
                    payback_input.monthly_consumption_kwh, availability_kwh
                ) * tariff
                solar_month = max(
                    availability_kwh * tariff,
                    remaining_consumption * tariff
                    + compensated * fio_b * charge.fraction,
                )
                savings = baseline_month - solar_month
                if savings < 0:
                    raise SolarPaybackError("calculated annual saving cannot be negative")

                annual_generation += generation
                annual_compensated += compensated
                annual_baseline_cost += baseline_month
                annual_solar_cost += solar_month
                annual_savings += savings

            net_cash_flow = _round(annual_savings, _CENTS)
            cumulative_cash_flow += net_cash_flow
            annual_rows.append(
                AnnualCashFlow(
                    projection_year=projection_year,
                    calendar_year=calendar_year,
                    generation_kwh=_round(annual_generation, _KWH_STEP),
                    compensated_kwh=_round(annual_compensated, _KWH_STEP),
                    expired_credit_kwh=_round(annual_expired, _KWH_STEP),
                    ending_credit_kwh=_round(
                        sum((credit for _, credit in ledger), Decimal("0")), _KWH_STEP
                    ),
                    baseline_energy_cost_brl=_round(annual_baseline_cost, _CENTS),
                    solar_energy_cost_brl=_round(annual_solar_cost, _CENTS),
                    net_cash_flow_brl=net_cash_flow,
                    cumulative_cash_flow_brl=_round(cumulative_cash_flow, _CENTS),
                    compensation_charge_fraction=charge.fraction,
                    regulatory_basis=charge.regulatory_basis,
                )
            )

        payback_year = next(
            (
                row.projection_year
                for row in annual_rows
                if row.cumulative_cash_flow_brl >= Decimal("0")
            ),
            None,
        )
        annual_flows = [row.net_cash_flow_brl for row in annual_rows]

    return SolarPaybackEstimate(
        initial_outlay_brl=initial_outlay,
        annual_cash_flows=annual_rows,
        payback_year=payback_year,
        irr_annual_percent=_irr_annual_percent(initial_outlay, annual_flows),
        assumptions=_assumptions(payback_input),
    )
