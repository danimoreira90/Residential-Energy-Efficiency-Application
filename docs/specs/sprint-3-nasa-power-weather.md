# Spec: Sprint 3 Task 3.1 — NASA POWER hourly weather client

**Status:** Approved for implementation  
**Date:** 2026-08-30  
**Scope:** Sprint 3 Task 3.1 only

## Problem

Solar sizing needs location-specific irradiance, air temperature, and wind
speed before pvlib can estimate generation. The current `energia.solar`
package is a stub and has no weather client.

## In scope

- A pure-importable `energia.solar.irradiance` client for NASA POWER's hourly,
  single-point JSON endpoint.
- Explicit latitude, longitude, and calendar-year inputs, validated before the
  request is made.
- A pandas `DataFrame` suitable for the later pvlib sizing task: UTC
  `DatetimeIndex` and `ghi`, `temp_air`, and `wind_speed` columns.
- Deterministic request/response tests using the installed `responses`
  library. NASA POWER is the only mocked dependency.

## Out of scope

- A LangChain tool, prompt change, eval fixture, Streamlit input flow, bill or
  DuckDB access, caching, PV sizing, panel catalog, cost, payback, or a live
  NASA request during tests.
- Calling an inverter, a proprietary API, or any service outside locked v1.

## Functional requirements

| ID | Requirement |
|---|---|
| F1 | `get_hourly_weather(latitude, longitude, year)` requests NASA POWER's hourly point endpoint with community `RE`, JSON output, `start={year}0101`, `end={year}1231`, `time-standard=UTC`, and `ALLSKY_SFC_SW_DWN`, `T2M`, and `WS10M`. |
| F2 | The returned frame has the complete, contiguous UTC hourly index for the requested calendar year (8,760 or 8,784 rows), whose labels mark the start of each hourly-average interval, and exactly `ghi`, `temp_air`, and `wind_speed` columns. `ALLSKY_SFC_SW_DWN` is an hourly Wh/m² value and is represented as the corresponding hourly-average W/m² GHI value; temperature is °C and wind speed is m/s. |
| F3 | Latitude and longitude must be finite and within geographic bounds; the year must be a four-digit calendar year. Invalid input makes no HTTP request. |
| F4 | An HTTP failure, malformed payload, missing requested channel, missing-value sentinel, unparsable timestamp, incomplete series, negative GHI, or negative wind speed raises a clear domain error that contains neither coordinates nor an upstream response body. The domain error must not retain an upstream exception as its explicit cause. |
| F5 | The module performs no logging and sends only coordinates, the requested year, and static NASA POWER query parameters. It never reads or transmits bill, installation, account, or identity data. |

## Non-functional requirements

- HTTP timeout: 30 seconds.
- No retries or cache in this slice; a transient source failure remains explicit
  so the later chat tool can state that it cannot calculate yet.
- No new dependency: use installed `requests`, `pandas`, and `responses`.
- The existing Sprint 3 roadmap already selects NASA POWER + pvlib; this task
  makes no new service, datastore, or dependency decision.

## Security and LGPD

Coordinates can reveal a residence. Do not log them, include them in exception
messages, persist them, or put them in eval fixtures. NASA POWER receives only
the validated coordinates required to obtain weather data. Tests use synthetic
coordinates and mocked responses.

## EDD requirements

Not applicable to this slice: it exposes no LLM-facing tool. Task 3.2 must
define capability and regression evals before registering
`estimate_solar_system`.

## Acceptance checks

- New focused tests are observed RED before production code exists, then GREEN.
- Mocked NASA response parsing, input rejection, and safe failure paths pass.
- `ruff check src tests` and strict Pyright pass for changed code.
- No protected prompt, existing test, eval baseline, migration, or approved ADR
  is edited.
