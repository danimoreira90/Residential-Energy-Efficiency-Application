"""NASA POWER hourly weather data normalized for pvlib."""
from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping
from typing import Final, cast

import pandas as pd
import requests

_ENDPOINT: Final = "https://power.larc.nasa.gov/api/temporal/hourly/point"
_CHANNELS: Final = {
    "ALLSKY_SFC_SW_DWN": "ghi",
    "T2M": "temp_air",
    "WS10M": "wind_speed",
}
_NON_NEGATIVE_COLUMNS: Final = frozenset({"ghi", "wind_speed"})
_MISSING_VALUE: Final = -999.0
_TIMESTAMP_FORMAT: Final = "%Y%m%d%H"
_UNUSABLE_MESSAGE: Final = "NASA POWER returned unusable weather data."
_UNAVAILABLE_MESSAGE: Final = "NASA POWER weather data is unavailable."


class WeatherDataError(ValueError):
    """NASA POWER data could not be safely used for a solar calculation."""


def get_hourly_weather(latitude: float, longitude: float, year: int) -> pd.DataFrame:
    """Fetch one UTC calendar year of irradiance, air temperature, and wind speed."""
    validation_error = _validation_error(latitude, longitude, year)
    if validation_error is not None:
        del latitude, longitude
        raise ValueError(validation_error) from None
    result = _fetch_and_normalize(latitude, longitude, year)
    del latitude, longitude
    if isinstance(result, str):
        raise WeatherDataError(result) from None
    return result


def _fetch_and_normalize(latitude: float, longitude: float, year: int) -> pd.DataFrame | str:
    """Fetch NASA POWER data and normalize it, returning a safe result.

    Every network, redirect, JSON-decoding, and normalization failure is
    caught here and turned into a sanitized message string instead of being
    raised. Because this frame always returns normally, it never appears in
    the traceback of an exception ultimately raised by the caller, so any
    coordinate value or response body held in these locals cannot leak
    through the caller's traceback.
    """
    try:
        response = requests.get(
            _ENDPOINT,
            params={
                "parameters": ",".join(_CHANNELS),
                "community": "RE",
                "longitude": str(longitude),
                "latitude": str(latitude),
                "start": f"{year:04d}0101",
                "end": f"{year:04d}1231",
                "format": "JSON",
                "time-standard": "UTC",
            },
            timeout=30,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            return _UNAVAILABLE_MESSAGE
        response.raise_for_status()
    except requests.RequestException:
        return _UNAVAILABLE_MESSAGE

    try:
        payload: object = response.json()
    except ValueError:
        return _UNAVAILABLE_MESSAGE

    try:
        return _normalize(payload, year)
    except WeatherDataError:
        return _UNUSABLE_MESSAGE


def _validation_error(latitude: object, longitude: object, year: object) -> str | None:
    """Return a safe validation error message, or ``None`` if inputs are valid.

    This returns normally in every case instead of raising, so this frame
    never appears in the traceback of a ``ValueError`` ultimately raised by
    the caller, and the coordinate values held in these locals cannot leak
    through that traceback.
    """
    if not _is_valid_coordinate(latitude, -90.0, 90.0):
        return "latitude must be a finite geographic coordinate"
    if not _is_valid_coordinate(longitude, -180.0, 180.0):
        return "longitude must be a finite geographic coordinate"
    if type(year) is not int or not 1000 <= year <= 9999:
        return "year must be a four-digit calendar year"
    return None


def _is_valid_coordinate(value: object, lower: float, upper: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and lower <= value <= upper
        and math.isfinite(value)
    )


def _expected_keys(year: int) -> frozenset[str]:
    current = dt.datetime(year, 1, 1, tzinfo=dt.UTC)
    last = dt.datetime(year, 12, 31, 23, tzinfo=dt.UTC)
    step = dt.timedelta(hours=1)
    keys: set[str] = set()
    while current <= last:
        keys.add(current.strftime(_TIMESTAMP_FORMAT))
        if current == last:
            break
        current += step
    return frozenset(keys)


def _normalize(payload: object, year: int) -> pd.DataFrame:
    parameters = _extract_parameters(payload)
    data: dict[str, dict[str, float]] = {
        column: _extract_channel(parameters, channel, column)
        for channel, column in _CHANNELS.items()
    }

    key_sets = {frozenset(values) for values in data.values()}
    if len(key_sets) != 1:
        raise WeatherDataError(_UNUSABLE_MESSAGE)

    actual_keys = next(iter(key_sets))
    if actual_keys != _expected_keys(year):
        raise WeatherDataError(_UNUSABLE_MESSAGE)

    try:
        frame = pd.DataFrame(data)
        frame.index = pd.to_datetime(
            frame.index, format=_TIMESTAMP_FORMAT, utc=True, errors="raise"
        )
        frame = frame.sort_index()
    except (TypeError, ValueError):
        raise WeatherDataError(_UNUSABLE_MESSAGE) from None

    return frame


def _as_str_keyed_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise WeatherDataError(_UNUSABLE_MESSAGE)
    untyped = cast("dict[object, object]", value)
    typed: dict[str, object] = {}
    for key, item in untyped.items():
        if not isinstance(key, str):
            raise WeatherDataError(_UNUSABLE_MESSAGE)
        typed[key] = item
    return typed


def _extract_parameters(payload: object) -> Mapping[str, object]:
    root = _as_str_keyed_mapping(payload)
    properties = _as_str_keyed_mapping(root.get("properties"))
    return _as_str_keyed_mapping(properties.get("parameter"))


def _extract_channel(
    parameters: Mapping[str, object], channel: str, column: str
) -> dict[str, float]:
    values = _as_str_keyed_mapping(parameters.get(channel))
    if not values:
        raise WeatherDataError(_UNUSABLE_MESSAGE)

    reject_negative = column in _NON_NEGATIVE_COLUMNS
    normalized: dict[str, float] = {}
    for timestamp, raw_value in values.items():
        value: object = raw_value
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise WeatherDataError(_UNUSABLE_MESSAGE)
        try:
            number = float(value)
        except (OverflowError, ValueError):
            raise WeatherDataError(_UNUSABLE_MESSAGE) from None
        if not math.isfinite(number) or number == _MISSING_VALUE:
            raise WeatherDataError(_UNUSABLE_MESSAGE)
        if reject_negative and number < 0.0:
            raise WeatherDataError(_UNUSABLE_MESSAGE)
        normalized[timestamp] = number
    return normalized
