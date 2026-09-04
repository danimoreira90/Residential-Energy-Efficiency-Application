"""RED contracts for the pure 25-year residential solar payback model."""
from __future__ import annotations

import importlib
from decimal import Decimal
from types import ModuleType

import pytest


def _payback() -> ModuleType:
    try:
        return importlib.import_module("energia.solar.payback")
    except ModuleNotFoundError:
        pytest.fail("energia.solar.payback is not implemented", pytrace=False)


def _payload(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "monthly_consumption_kwh": Decimal("100"),
        "monthly_generation_kwh": [Decimal("100")] * 12,
        "system_cost_brl": Decimal("1000"),
        "distributor": "Enel Distribuição Rio",
        "connection_year": 2023,
        "connection_type": "monofasica_ou_bifasica_2_condutores",
        "base_tariff_brl_per_kwh": Decimal("1"),
        "tusd_fio_b_brl_per_mwh": Decimal("100"),
        "real_tariff_inflation_rate": Decimal("0"),
        "annual_generation_degradation_rate": Decimal("0"),
        "tariff_provenance": {
            "url": "https://www.enel.com.br/synthetic-tariff",
            "effective_from": "2026-03-15",
            "effective_to": "2027-03-14",
        },
        "fio_b_provenance": {
            "url": "https://dadosabertos.aneel.gov.br/",
            "resource_id": "e8717aa8-2521-453f-bf16-fbb9a16eea39",
            "resource_hash": "c4bd43306833b0583a2fad9fa0945665",
            "effective_from": "2026-03-15",
            "effective_to": "2027-03-14",
        },
    }
    values.update(changes)
    return values


def _calculate(**changes: object):  # type: ignore[no-untyped-def]
    payback = _payback()
    return payback.calculate_solar_payback(payback.SolarPaybackInput(**_payload(**changes)))


@pytest.mark.parametrize(
    "change",
    [
        {"monthly_consumption_kwh": True},
        {"monthly_generation_kwh": [Decimal("1")] * 11},
        {"monthly_generation_kwh": [Decimal("0")] * 12},
        {"monthly_generation_kwh": [Decimal("1")] * 11 + [Decimal("NaN")]},
        {"system_cost_brl": 0},
        {"system_cost_brl": Decimal("0.004")},
        {"system_cost_brl": Decimal("1E+100")},
        {"connection_year": True},
        {"connection_year": 2022},
        {"connection_type": "bifasica"},
        {"base_tariff_brl_per_kwh": Decimal("0")},
        {"tusd_fio_b_brl_per_mwh": Decimal("1001")},
        {"real_tariff_inflation_rate": Decimal("1")},
        {"annual_generation_degradation_rate": Decimal("Infinity")},
    ],
)
def test_input_rejects_invalid_or_ambiguous_values(change: dict[str, object]) -> None:
    payback = _payback()
    with pytest.raises(ValueError):
        payback.SolarPaybackInput(**_payload(**change))


@pytest.mark.parametrize(
    ("connection_type", "first_year_savings"),
    [
        ("monofasica_ou_bifasica_2_condutores", "840.00"),
        ("bifasica_3_condutores", "600.00"),
        ("trifasica", "0.00"),
    ],
)
def test_connection_type_applies_one_availability_floor(
    connection_type: str, first_year_savings: str
) -> None:
    result = _calculate(connection_type=connection_type)
    assert result.annual_cash_flows[0].net_cash_flow_brl == Decimal(first_year_savings)


def test_annual_aggregation_escalation_and_degradation_are_exact() -> None:
    result = _calculate(
        monthly_generation_kwh=[Decimal("50")] * 12,
        tusd_fio_b_brl_per_mwh=Decimal("200"),
        real_tariff_inflation_rate=Decimal("0.10"),
        annual_generation_degradation_rate=Decimal("0.10"),
    )
    first, second = result.annual_cash_flows[:2]
    assert (first.generation_kwh, first.compensated_kwh) == (
        Decimal("600.00"), Decimal("600.00")
    )
    assert first.net_cash_flow_brl == Decimal("582.00")
    assert (second.generation_kwh, second.compensated_kwh) == (
        Decimal("540.00"), Decimal("540.00")
    )
    assert second.net_cash_flow_brl == Decimal("558.36")

    rounded_after_sum = _calculate(
        monthly_consumption_kwh=Decimal("31"),
        monthly_generation_kwh=[Decimal("1")] * 12,
        base_tariff_brl_per_kwh=Decimal("0.015"),
        tusd_fio_b_brl_per_mwh=Decimal("1"),
    )
    assert rounded_after_sum.annual_cash_flows[0].net_cash_flow_brl == Decimal("0.18")


def test_fifo_credit_expiry_and_terminal_boundary_are_auditable() -> None:
    result = _calculate(
        monthly_consumption_kwh=Decimal("10"),
        monthly_generation_kwh=[Decimal("700")] + [Decimal("0")] * 11,
        tusd_fio_b_brl_per_mwh=Decimal("1"),
    )
    assert result.annual_cash_flows[0].ending_credit_kwh == Decimal("580.00")
    assert result.annual_cash_flows[4].expired_credit_kwh == Decimal("0.00")
    assert result.annual_cash_flows[5].expired_credit_kwh == Decimal("100.00")
    assert result.annual_cash_flows[-1].ending_credit_kwh > 0
    assert result.annual_cash_flows[-1].cumulative_cash_flow_brl == (
        -result.initial_outlay_brl
        + sum((row.net_cash_flow_brl for row in result.annual_cash_flows), Decimal("0"))
    )


def test_fifo_consumes_oldest_of_multiple_credit_lots_before_expiry() -> None:
    result = _calculate(
        monthly_consumption_kwh=Decimal("100"),
        monthly_generation_kwh=[Decimal("700"), Decimal("700")] + [Decimal("0")] * 10,
        tusd_fio_b_brl_per_mwh=Decimal("1"),
    )
    first_six = result.annual_cash_flows[:6]
    assert [row.ending_credit_kwh for row in first_six] == [
        Decimal("200.00"),
        Decimal("400.00"),
        Decimal("600.00"),
        Decimal("800.00"),
        Decimal("1000.00"),
        Decimal("1200.00"),
    ]
    assert all(row.expired_credit_kwh == Decimal("0.00") for row in first_six)


def test_annual_output_payback_and_irr_boundaries() -> None:
    payback = _payback()
    positive = _calculate()
    assert len(positive.annual_cash_flows) == 25
    assert [row.projection_year for row in positive.annual_cash_flows] == list(range(1, 26))
    assert positive.payback_year == 2
    assert positive.irr_annual_percent is not None and positive.irr_annual_percent > 0
    assert positive.irr_annual_percent.as_tuple().exponent == -2
    assert all(
        row.regulatory_basis == "conservative_post_2028_planning_scenario"
        for row in positive.annual_cash_flows[6:]
    )

    negative = _calculate(system_cost_brl=Decimal("30000"))
    assert negative.payback_year is None
    assert negative.irr_annual_percent is not None and negative.irr_annual_percent < 0

    no_savings = _calculate(connection_type="trifasica")
    assert no_savings.irr_annual_percent is None
    assert payback._irr_annual_percent(  # pyright: ignore[reportPrivateUsage]
        Decimal("1E+200"), [Decimal("1")] * 25
    ) is None


def test_assumptions_preserve_provenance_and_model_limits() -> None:
    result = _calculate()
    fixed = result.assumptions["fixed_model"]
    formulas = result.assumptions["formulas"]
    solver = result.assumptions["irr_solver"]
    inputs = result.assumptions["inputs_and_units"]
    legal_sources = result.assumptions["legal_sources"]
    assert isinstance(inputs, dict)
    assert inputs["distributor"] == "Enel Distribuição Rio"
    assert isinstance(legal_sources, dict)
    assert legal_sources["Article 17 rulemaking"] == (
        "https://www.gov.br/fazenda/pt-br/composicao/orgaos/"
        "secretaria-de-reformas-economicas/manifestacoes-em-consultas-publicas-de-"
        "orgaos-reguladores/2026/agencia-nacional-de-energia-eletrica-aneel/"
        "sei_58000857_nota_tecnica_958-1-_260325_090518.pdf/view"
    )
    assert isinstance(fixed, dict) and fixed == {
        "horizon_months": 300,
        "horizon_years": 25,
        "credit_lifetime_months": 60,
        "availability_floor_kwh": {
            "monofasica_ou_bifasica_2_condutores": Decimal("30"),
            "bifasica_3_condutores": Decimal("50"),
            "trifasica": Decimal("100"),
        },
    }
    assert isinstance(formulas, dict) and formulas == {
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
        "baseline_month_brl": "max(monthly_consumption_kwh, availability_kwh) * tariff_y",
        "solar_month_brl": (
            "max(availability_kwh * tariff_y, uncompensated_kwh * tariff_y + "
            "compensated_kwh * fio_b_y * compensation_charge_fraction)"
        ),
        "net_cash_flow_brl": "baseline_energy_cost_brl - solar_energy_cost_brl",
        "payback": "first whole projection_year where cumulative_cash_flow_brl >= 0",
        "npv": "-initial_outlay_brl + sum(annual_cash_flow_t / (1 + rate) ** t)",
    }
    assert isinstance(solver, dict) and solver == {
        "low": "-0.999999",
        "initial_high": "1",
        "max_high_expansions": 20,
        "max_bisections": 256,
        "tolerance": "0.00000001",
    }
    assumptions = str(result.assumptions)
    for required in (
        "e8717aa8-2521-453f-bf16-fbb9a16eea39",
        "c4bd43306833b0583a2fad9fa0945665",
        "conservative_post_2028_planning_scenario",
        "ROUND_HALF_UP",
        "60",
        "300",
        "terminal",
        "financing",
        "maintenance",
        "tax",
    ):
        assert required.casefold() in assumptions.casefold()
