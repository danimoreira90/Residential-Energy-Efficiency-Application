"""RED contracts for Sprint 3 Task 3.2 solar sizing."""
from __future__ import annotations

import importlib
from decimal import Decimal
from types import ModuleType
from typing import Any, cast

import numpy as np
import pandas as pd
import pvlib
import pytest


def _sizing() -> ModuleType:
    try:
        return importlib.import_module("energia.solar.sizing")
    except ModuleNotFoundError:
        pytest.fail("energia.solar.sizing is not implemented", pytrace=False)


def _weather() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", "2025-12-31 23:00", freq="h", tz="UTC")
    return pd.DataFrame(
        {"ghi": 500.0, "temp_air": 25.0, "wind_speed": 2.0},
        index=index,
    )


def _payload(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "latitude": 10.04,
        "longitude": 20.06,
        "monthly_consumption_kwh": Decimal("100"),
        "roof_orientation": "N",
        "roof_tilt_deg": Decimal("15"),
    }
    values.update(changes)
    return values


def _fake_model(
    monkeypatch: pytest.MonkeyPatch,
    *,
    frame: pd.DataFrame | None = None,
    ac_watts: float = 100.0,
) -> tuple[ModuleType, list[str], dict[str, Any]]:
    weather = _weather() if frame is None else frame
    events: list[str] = []
    seen: dict[str, Any] = {"weather": [], "azimuth": []}

    def solar_position(time: pd.DatetimeIndex, *_args: object, **_kwargs: object) -> pd.DataFrame:
        events.append("solarposition")
        seen["solar_time"] = time
        return pd.DataFrame(
            {"zenith": 31.0, "apparent_zenith": 30.0, "azimuth": 180.0},
            index=time,
        )

    def erbs(
        ghi: pd.Series,
        zenith: pd.Series,
        *_args: object,
        **_kwargs: object,
    ) -> pd.DataFrame:
        events.append("erbs")
        seen["erbs_zenith"] = zenith
        return pd.DataFrame({"dni": 600.0, "dhi": 100.0}, index=ghi.index)

    def total_irradiance(*_args: object, **kwargs: object) -> dict[str, pd.Series]:
        events.append("transposition")
        seen["transposition"] = kwargs
        seen["azimuth"].append(kwargs["surface_azimuth"])
        ghi = cast(pd.Series, kwargs["ghi"])
        return {"poa_global": pd.Series(1000.0, index=ghi.index)}

    def cell_temperature(
        poa_global: pd.Series, *_args: object, **kwargs: object
    ) -> pd.Series:
        events.append("temperature")
        seen["temperature"] = kwargs
        return pd.Series(25.0, index=poa_global.index)

    def dc_power(
        effective_irradiance: pd.Series,
        _temp_cell: pd.Series,
        **kwargs: object,
    ) -> pd.Series:
        events.append("dc")
        seen["dc"] = kwargs
        return pd.Series(1000.0, index=effective_irradiance.index)

    def losses(**kwargs: object) -> float:
        events.append("losses")
        seen["losses"] = kwargs
        return 10.0

    def inverter(pdc: pd.Series, **kwargs: object) -> pd.Series:
        events.append("inverter")
        seen["inverter"] = kwargs
        seen["inverter_input"] = pdc
        return pd.Series(ac_watts, index=pdc.index)

    monkeypatch.setattr(pvlib.solarposition, "get_solarposition", solar_position)
    monkeypatch.setattr(pvlib.irradiance, "erbs", erbs)
    monkeypatch.setattr(pvlib.irradiance, "get_total_irradiance", total_irradiance)
    monkeypatch.setattr(pvlib.temperature, "sapm_cell", cell_temperature)
    monkeypatch.setattr(pvlib.pvsystem, "pvwatts_dc", dc_power)
    monkeypatch.setattr(pvlib.pvsystem, "pvwatts_losses", losses)
    monkeypatch.setattr(pvlib.inverter, "pvwatts", inverter)

    sizing = _sizing()

    def get_weather(latitude: float, longitude: float, year: int) -> pd.DataFrame:
        seen["weather"].append((latitude, longitude, year))
        return weather

    monkeypatch.setattr(sizing, "get_hourly_weather", get_weather)
    return sizing, events, seen


def test_public_contract_defaults_and_boundaries() -> None:
    sizing = _sizing()
    assert set(sizing.SolarSizingInput.model_fields) == {
        "latitude",
        "longitude",
        "monthly_consumption_kwh",
        "roof_orientation",
        "roof_tilt_deg",
    }
    assert set(sizing.SolarSizingEstimate.model_fields) == {
        "recommended_kwp",
        "monthly_generation_kwh",
        "annual_generation_kwh",
        "estimated_cost_brl",
        "assumptions",
    }
    values = _payload(latitude=90, longitude=180)
    values.pop("roof_tilt_deg")
    assert sizing.SolarSizingInput(**values).roof_tilt_deg == 15
    assert issubclass(sizing.SolarSizingError, ValueError)


@pytest.mark.parametrize(
    "change",
    [
        {"latitude": float("nan")},
        {"latitude": True},
        {"longitude": 181},
        {"monthly_consumption_kwh": 0},
        {"roof_orientation": "north"},
        {"roof_tilt_deg": 91},
    ],
)
def test_input_rejects_invalid_values(change: dict[str, object]) -> None:
    sizing = _sizing()
    with pytest.raises(ValueError):
        sizing.SolarSizingInput(**_payload(**change))


def test_happy_path_uses_locked_model_and_rounding(monkeypatch: pytest.MonkeyPatch) -> None:
    sizing, events, seen = _fake_model(monkeypatch)
    result = sizing.estimate_solar_system(
        sizing.SolarSizingInput(**_payload(roof_orientation="SE", roof_tilt_deg=20))
    )

    assert seen["weather"] == [(10.0, 20.1, 2025)]
    assert seen["solar_time"][0] == pd.Timestamp("2025-01-01 00:30", tz="UTC")
    assert (seen["erbs_zenith"] == 31.0).all()
    assert events == [
        "solarposition",
        "erbs",
        "transposition",
        "temperature",
        "dc",
        "losses",
        "inverter",
    ]
    assert seen["transposition"]["model"] == "isotropic"
    assert seen["transposition"]["surface_tilt"] == 20
    assert seen["transposition"]["surface_azimuth"] == 135
    expected_temperature = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"][
        "close_mount_glass_glass"
    ]
    assert seen["temperature"] == expected_temperature
    assert seen["dc"] == {"pdc0": 1000, "gamma_pdc": -0.004}
    assert seen["losses"] == {}
    assert (seen["inverter_input"] == 900).all()
    assert seen["inverter"]["pdc0"] == pytest.approx((1000 / 1.2) / 0.96)
    assert seen["inverter"]["eta_inv_nom"] == 0.96

    assert result.recommended_kwp == Decimal("1.51")
    assert len(result.monthly_generation_kwh) == 12
    assert all(
        type(value) is Decimal and value.as_tuple().exponent == -2
        for value in result.monthly_generation_kwh
    )
    assert result.annual_generation_kwh == sum(result.monthly_generation_kwh, Decimal())
    assert result.estimated_cost_brl == Decimal("4756.50")
    assumptions = str(result.assumptions)
    assert "NASA POWER" in assumptions and "0.1" in assumptions and "epe.gov.br" in assumptions
    assert all(value not in assumptions for value in ("10.04", "20.06", "10.0", "20.1"))


def test_real_pvlib_chain_aligns_left_labelled_weather_to_interval_midpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sizing = _sizing()
    weather = _weather()
    hours = np.arange(len(weather), dtype=float) % 24
    weather["ghi"] = np.maximum(0.0, np.sin(np.pi * (hours - 6.0) / 12.0)) * 800.0

    def get_weather(latitude: float, longitude: float, year: int) -> pd.DataFrame:
        assert (latitude, longitude, year) == (0.0, 0.0, 2025)
        return weather

    monkeypatch.setattr(sizing, "get_hourly_weather", get_weather)
    result = sizing.estimate_solar_system(
        sizing.SolarSizingInput(**_payload(latitude=0, longitude=0))
    )

    assert len(result.monthly_generation_kwh) == 12
    assert result.annual_generation_kwh > 0


@pytest.mark.parametrize(
    ("orientation", "azimuth"),
    zip(("N", "NE", "E", "SE", "S", "SW", "W", "NW"), range(0, 360, 45), strict=True),
)
def test_orientation_maps_to_pvlib_azimuth(
    monkeypatch: pytest.MonkeyPatch, orientation: str, azimuth: int
) -> None:
    sizing, _, seen = _fake_model(monkeypatch)
    sizing.estimate_solar_system(
        sizing.SolarSizingInput(**_payload(roof_orientation=orientation))
    )
    assert seen["azimuth"] == [azimuth]


@pytest.mark.parametrize("case", ["incomplete", "zero", "nonfinite"])
def test_unusable_yield_has_safe_error(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    frame: pd.DataFrame | None = None
    if case == "incomplete":
        frame = cast(pd.DataFrame, _weather().iloc[:-1])
    ac_watts = {"zero": 0.0, "nonfinite": float("nan")}.get(case, 100.0)
    sizing, _, _ = _fake_model(monkeypatch, frame=frame, ac_watts=ac_watts)
    with pytest.raises(sizing.SolarSizingError) as raised:
        sizing.estimate_solar_system(sizing.SolarSizingInput(**_payload()))
    assert not any(character.isdigit() for character in str(raised.value))


@pytest.mark.parametrize(
    "consumption",
    [Decimal("50000"), Decimal("1E+100"), Decimal("1E+1000000")],
)
def test_capacity_above_v1_scope_has_safe_error(
    monkeypatch: pytest.MonkeyPatch,
    consumption: Decimal,
) -> None:
    sizing, _, _ = _fake_model(monkeypatch)
    with pytest.raises(sizing.SolarSizingError) as raised:
        sizing.estimate_solar_system(
            sizing.SolarSizingInput(**_payload(monthly_consumption_kwh=consumption))
        )
    assert not any(character.isdigit() for character in str(raised.value))
