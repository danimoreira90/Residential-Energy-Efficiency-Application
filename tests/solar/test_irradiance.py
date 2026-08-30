"""NASA POWER hourly weather client tests."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import cast
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest
import responses

_ENDPOINT = "https://power.larc.nasa.gov/api/temporal/hourly/point"
_LATITUDE = -22.9
_LONGITUDE = -43.1
_TS_FORMAT = "%Y%m%d%H"


def _query(year: int) -> dict[str, str]:
    return {
        "parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M",
        "community": "RE",
        "longitude": str(_LONGITUDE),
        "latitude": str(_LATITUDE),
        "start": f"{year}0101",
        "end": f"{year}1231",
        "format": "JSON",
        "time-standard": "UTC",
    }


def _expected_hourly_index(year: int) -> pd.DatetimeIndex:
    start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
    end = pd.Timestamp(year=year, month=12, day=31, hour=23, tz="UTC")
    return pd.date_range(start=start, end=end, freq="h")


def _stdlib_hour_keys(year: int) -> list[str]:
    """Every UTC hour timestamp key for ``year`` using only stdlib datetime.

    Unlike ``pandas.Timestamp``, ``datetime.datetime`` supports the full
    stdlib year range (``datetime.MINYEAR``..``datetime.MAXYEAR`` == 9999),
    so this also works for the boundary year 9999.
    """
    current: datetime = datetime(year, 1, 1, tzinfo=UTC)
    last: datetime = datetime(year, 12, 31, 23, tzinfo=UTC)
    step: timedelta = timedelta(hours=1)
    keys: list[str] = []
    while current <= last:
        keys.append(current.strftime(_TS_FORMAT))
        if current == last:
            break
        current += step
    return keys


def _parameters(
    year: int,
    ghi_overrides: Mapping[str, float] | None = None,
    temp_overrides: Mapping[str, float] | None = None,
    wind_overrides: Mapping[str, float] | None = None,
    omit_keys: frozenset[str] = frozenset(),
) -> dict[str, dict[str, float]]:
    keys = [key for key in _stdlib_hour_keys(year) if key not in omit_keys]
    ghi = {key: 10.0 for key in keys}
    temp = {key: 24.5 for key in keys}
    wind = {key: 2.2 for key in keys}
    ghi.update(ghi_overrides or {})
    temp.update(temp_overrides or {})
    wind.update(wind_overrides or {})
    return {"ALLSKY_SFC_SW_DWN": ghi, "T2M": temp, "WS10M": wind}


def _payload(parameters: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    return {"properties": {"parameter": parameters}}


def _full_year_payload(
    year: int,
    ghi_overrides: Mapping[str, float] | None = None,
    temp_overrides: Mapping[str, float] | None = None,
    wind_overrides: Mapping[str, float] | None = None,
    omit_keys: frozenset[str] = frozenset(),
) -> dict[str, object]:
    return _payload(
        _parameters(
            year,
            ghi_overrides=ghi_overrides,
            temp_overrides=temp_overrides,
            wind_overrides=wind_overrides,
            omit_keys=omit_keys,
        )
    )


_MISSING_CHANNEL_PAYLOAD: dict[str, object] = _payload(
    {key: values for key, values in _parameters(2024).items() if key != "WS10M"}
)
_MISMATCHED_CHANNEL_KEYS_PAYLOAD: dict[str, object] = _payload(
    {
        "ALLSKY_SFC_SW_DWN": {"2024010100": 1.0, "2024010101": 2.0},
        "T2M": {"2024010100": 24.5},
        "WS10M": {"2024010100": 2.2},
    }
)
_MISSING_VALUE_SENTINEL_PAYLOAD: dict[str, object] = _full_year_payload(
    2024, ghi_overrides={"2024070112": -999.0}
)
_UNPARSABLE_TIMESTAMP_PAYLOAD: dict[str, object] = _payload(
    {
        "ALLSKY_SFC_SW_DWN": {"not-a-timestamp": 1.0},
        "T2M": {"not-a-timestamp": 24.5},
        "WS10M": {"not-a-timestamp": 2.2},
    }
)
_NON_NUMERIC_VALUE_PAYLOAD: dict[str, object] = _payload(
    {
        "ALLSKY_SFC_SW_DWN": {"2024010100": "not-a-number"},
        "T2M": {"2024010100": 24.5},
        "WS10M": {"2024010100": 2.2},
    }
)
_OVERSIZED_NUMERIC_VALUE_PAYLOAD: dict[str, object] = _payload(
    {
        "ALLSKY_SFC_SW_DWN": {"2024010100": 10**400},
        "T2M": {"2024010100": 24.5},
        "WS10M": {"2024010100": 2.2},
    }
)


def _assert_domain_error_leaks_nothing(
    error: BaseException,
    latitude: float,
    longitude: float,
    *,
    forbidden_substrings: tuple[str, ...] = (),
) -> None:
    """Assert a domain error has no cause/context and leaks nothing via locals.

    Shared by every test asserting that a raised domain error's cause and
    context are both ``None`` and that no ``energia.solar.irradiance``
    traceback frame local retains the supplied ``latitude``/``longitude``
    (or any of ``forbidden_substrings``, when checking upstream response
    leakage as well).
    """
    assert error.__cause__ is None
    assert error.__context__ is None

    found_irradiance_frame = False
    traceback: TracebackType | None = error.__traceback__
    while traceback is not None:
        frame = traceback.tb_frame
        if frame.f_globals.get("__name__") == "energia.solar.irradiance":
            found_irradiance_frame = True
            for local_value in frame.f_locals.values():
                assert local_value != latitude
                assert local_value != longitude
                for forbidden in forbidden_substrings:
                    assert forbidden not in str(local_value)
        traceback = traceback.tb_next
    assert found_irradiance_frame


def test_irradiance_module_exposes_hourly_weather_client() -> None:
    from energia.solar.irradiance import get_hourly_weather

    assert callable(get_hourly_weather)


@pytest.mark.parametrize("year", [2023, 2024])
@responses.activate
def test_hourly_weather_normalizes_complete_calendar_year(year: int) -> None:
    from energia.solar.irradiance import get_hourly_weather

    responses.add(responses.GET, _ENDPOINT, json=_full_year_payload(year), status=200)

    weather = get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=year)

    expected_index = _expected_hourly_index(year)
    assert list(weather.columns) == ["ghi", "temp_air", "wind_speed"]
    assert len(weather.index) == (8784 if year == 2024 else 8760)
    assert weather.index.equals(expected_index)
    assert weather.index[0] == pd.Timestamp(year=year, month=1, day=1, tz="UTC")
    assert weather.index[-1] == pd.Timestamp(year=year, month=12, day=31, hour=23, tz="UTC")

    url = responses.calls[0].request.url
    assert url is not None
    requested = parse_qs(urlparse(url).query)
    assert requested == {key: [value] for key, value in _query(year).items()}


@responses.activate
def test_hourly_weather_normalizes_complete_calendar_year_9999() -> None:
    """Year 9999 (the stdlib ``datetime.MAXYEAR`` boundary) must normalize."""
    from energia.solar.irradiance import get_hourly_weather

    responses.add(responses.GET, _ENDPOINT, json=_full_year_payload(9999), status=200)

    weather = get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=9999)

    assert list(weather.columns) == ["ghi", "temp_air", "wind_speed"]
    assert len(weather.index) == 8760


def test_hourly_weather_uses_fixed_timeout_and_query_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from energia.solar import irradiance
    from energia.solar.irradiance import get_hourly_weather

    captured: dict[str, object] = {}

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return _full_year_payload(2024)

    def _fake_get(
        url: str,
        params: Mapping[str, str],
        timeout: int,
        allow_redirects: bool,
    ) -> _FakeResponse:
        captured["url"] = url
        captured["params"] = dict(params)
        captured["timeout"] = timeout
        captured["allow_redirects"] = allow_redirects
        return _FakeResponse()

    monkeypatch.setattr(irradiance.requests, "get", _fake_get)

    get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)

    assert captured["timeout"] == 30
    assert captured["url"] == _ENDPOINT
    assert captured["params"] == _query(2024)
    assert captured["allow_redirects"] is False


@responses.activate
def test_hourly_weather_rejects_redirect_response() -> None:
    from energia.solar.irradiance import WeatherDataError, get_hourly_weather

    responses.add(
        responses.GET,
        _ENDPOINT,
        status=302,
        headers={"Location": "https://example.invalid/redirected"},
    )

    with pytest.raises(WeatherDataError):
        get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)


def test_hourly_weather_rejects_missing_shared_interior_hour() -> None:
    from energia.solar.irradiance import WeatherDataError, get_hourly_weather

    missing_key = pd.Timestamp(year=2024, month=7, day=1, hour=12, tz="UTC").strftime(_TS_FORMAT)
    payload = _full_year_payload(2024, omit_keys=frozenset({missing_key}))

    with responses.RequestsMock() as mocked:
        mocked.add(responses.GET, _ENDPOINT, json=payload, status=200)
        with pytest.raises(WeatherDataError) as raised:
            get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)

    assert raised.value.__cause__ is None


@responses.activate
def test_hourly_weather_rejects_negative_ghi() -> None:
    from energia.solar.irradiance import WeatherDataError, get_hourly_weather

    payload = _full_year_payload(2024, ghi_overrides={"2024070112": -5.0})
    responses.add(responses.GET, _ENDPOINT, json=payload, status=200)

    with pytest.raises(WeatherDataError) as raised:
        get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)

    assert raised.value.__cause__ is None


@responses.activate
def test_hourly_weather_rejects_negative_wind_speed() -> None:
    from energia.solar.irradiance import WeatherDataError, get_hourly_weather

    payload = _full_year_payload(2024, wind_overrides={"2024070112": -1.0})
    responses.add(responses.GET, _ENDPOINT, json=payload, status=200)

    with pytest.raises(WeatherDataError) as raised:
        get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)

    assert raised.value.__cause__ is None


@responses.activate
def test_hourly_weather_accepts_negative_temperature() -> None:
    from energia.solar.irradiance import get_hourly_weather

    payload = _full_year_payload(2024, temp_overrides={"2024070112": -12.5})
    responses.add(responses.GET, _ENDPOINT, json=payload, status=200)

    weather = get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)

    target = pd.Timestamp(year=2024, month=7, day=1, hour=12, tz="UTC")
    assert weather.loc[target, "temp_air"] == -12.5


@pytest.mark.parametrize(
    ("latitude", "longitude", "year"),
    [
        (float("nan"), 0.0, 2024),
        (91.0, 0.0, 2024),
        (-91.0, 0.0, 2024),
        (0.0, float("inf"), 2024),
        (0.0, 181.0, 2024),
        (0.0, -181.0, 2024),
        (0.0, 0.0, 999),
        (0.0, 0.0, 10_000),
    ],
)
def test_hourly_weather_rejects_invalid_input_before_request(
    latitude: float,
    longitude: float,
    year: int,
) -> None:
    from energia.solar.irradiance import get_hourly_weather

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
        with pytest.raises(ValueError):
            get_hourly_weather(latitude=latitude, longitude=longitude, year=year)

    assert len(mocked.calls) == 0


@pytest.mark.parametrize(
    ("latitude", "longitude", "year"),
    [
        (float("nan"), 0.0, 2024),
        (91.0, 0.0, 2024),
        (-91.0, 0.0, 2024),
        (0.0, float("inf"), 2024),
        (0.0, 181.0, 2024),
        (0.0, -181.0, 2024),
    ],
)
def test_hourly_weather_invalid_coordinate_domain_error_leaks_nothing(
    latitude: float,
    longitude: float,
    year: int,
) -> None:
    """Invalid-coordinate domain errors must have no cause/context and no leak.

    Same leakage contract as the HTTP-details domain error: no
    ``energia.solar.irradiance`` traceback frame local may retain the
    supplied latitude or longitude.
    """
    from energia.solar.irradiance import get_hourly_weather

    with pytest.raises(ValueError) as raised:
        get_hourly_weather(latitude=latitude, longitude=longitude, year=year)

    _assert_domain_error_leaks_nothing(raised.value, latitude, longitude)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(10**10000, 0.0), (0.0, 10**10000)],
    ids=["latitude", "longitude"],
)
def test_hourly_weather_rejects_arbitrarily_large_integer_coordinate_before_request(
    latitude: float,
    longitude: float,
) -> None:
    """A huge int coordinate must fail with ``ValueError``, never ``OverflowError``.

    ``int.__float__`` raises ``OverflowError`` for integers too large to be
    represented as a ``float`` (e.g. ``10**10000``). Validation must reject
    such coordinates deliberately, before any HTTP call, with the documented
    ``ValueError`` domain error rather than letting ``OverflowError`` escape.
    """
    from energia.solar.irradiance import get_hourly_weather

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
        with pytest.raises(ValueError):
            get_hourly_weather(latitude=latitude, longitude=longitude, year=2024)

    assert len(mocked.calls) == 0


@pytest.mark.parametrize(
    "year",
    [cast(int, True), cast(int, 2024.0), cast(int, "2024")],
    ids=["bool", "float", "str"],
)
def test_hourly_weather_rejects_non_int_year_types_before_request(year: int) -> None:
    """bool/float/str year values must be rejected before any HTTP call.

    ``year`` is annotated ``int`` in the public signature; these values are
    deliberately mistyped to exercise runtime validation, so a narrow
    ``cast(int, ...)`` (not ``Any``/``# type: ignore``) is used to pass them
    through the type checker for this negative test.
    """
    from energia.solar.irradiance import get_hourly_weather

    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
        with pytest.raises(ValueError):
            get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=year)

    assert len(mocked.calls) == 0


@responses.activate
def test_hourly_weather_hides_http_response_details_in_domain_error() -> None:
    from energia.solar.irradiance import WeatherDataError, get_hourly_weather

    responses.add(responses.GET, _ENDPOINT, body="upstream-secret-body", status=503)

    with pytest.raises(WeatherDataError) as raised:
        get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)

    assert str(_LATITUDE) not in str(raised.value)
    assert str(_LONGITUDE) not in str(raised.value)
    assert "upstream-secret-body" not in str(raised.value)

    _assert_domain_error_leaks_nothing(
        raised.value,
        _LATITUDE,
        _LONGITUDE,
        forbidden_substrings=("upstream-secret-body",),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        _MISSING_CHANNEL_PAYLOAD,
        _MISMATCHED_CHANNEL_KEYS_PAYLOAD,
        _MISSING_VALUE_SENTINEL_PAYLOAD,
        _UNPARSABLE_TIMESTAMP_PAYLOAD,
        _NON_NUMERIC_VALUE_PAYLOAD,
        _OVERSIZED_NUMERIC_VALUE_PAYLOAD,
    ],
)
@responses.activate
def test_hourly_weather_hides_bad_upstream_payload_details_in_domain_error(
    payload: dict[str, object],
) -> None:
    from energia.solar.irradiance import WeatherDataError, get_hourly_weather

    responses.add(responses.GET, _ENDPOINT, json=payload, status=200)

    with pytest.raises(WeatherDataError) as raised:
        get_hourly_weather(latitude=_LATITUDE, longitude=_LONGITUDE, year=2024)

    assert str(_LATITUDE) not in str(raised.value)
    assert str(_LONGITUDE) not in str(raised.value)
    assert "not-a-timestamp" not in str(raised.value)
    assert "not-a-number" not in str(raised.value)
    assert raised.value.__cause__ is None
