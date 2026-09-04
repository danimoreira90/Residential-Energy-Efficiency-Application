# Spec: Sprint 3 Task 3.2 — solar system sizing

**Status:** Approved for implementation  
**Date:** 2026-08-30  
**Scope:** Sprint 3 Task 3.2 only

## Problem

The application can fetch a validated year of NASA POWER weather, but it cannot
turn that weather and a household's average consumption into an auditable PV
system size, monthly generation profile, or planning-level installed cost.

## In scope

- A pure `energia.solar.sizing` domain function using the installed `pvlib`.
- A typed, self-registering `estimate_solar_system` LangChain tool.
- A 2025 NASA POWER reference year, fetched once through
  `get_hourly_weather(latitude, longitude, 2025)`.
- Continuous residential sizing, a 12-element January-to-December generation
  series, annual generation, and an EPE-sourced planning cost benchmark.
- Redaction of latitude and longitude from the existing local DuckDB tool-call
  audit, including expected-error text.
- New deterministic tests and capability eval contracts written before the
  production implementation.

## Out of scope

- Panel or inverter brands, bills of materials, discrete module counts, vendor
  quotations, payback, Lei 14.300 cash flow, UI controls, prompt edits, caching,
  retries, geocoding, multi-year/TMY synthesis, or a new dependency.
- Group A, commercial/industrial, or systems above the v1 microgeneration
  boundary.

## Public contract

`SolarSizingInput` contains:

- `latitude`: finite decimal degrees in `[-90, 90]`.
- `longitude`: finite decimal degrees in `[-180, 180]`.
- `monthly_consumption_kwh`: finite and greater than zero.
- `roof_orientation`: one of `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`.
- `roof_tilt_deg`: finite degrees in `[0, 90]`, default `15`.

`SolarSizingEstimate` contains:

- `recommended_kwp`: continuous capacity, rounded upward to `0.01 kWp`.
- `monthly_generation_kwh`: exactly 12 Decimal values in calendar-month order.
- `annual_generation_kwh`: the exact sum of the 12 reported values.
- `estimated_cost_brl`: planning benchmark rounded to cents.
- `assumptions`: the numerical model, reference year, source, and limitations.

## Functional requirements

| ID | Requirement |
|---|---|
| F1 | Round validated coordinates to `0.1` degree before the single 2025 UTC weather fetch. No application-controlled log, audit field, error, or output may contain either the raw or transmitted coordinates. The success assumptions disclose NASA POWER as the external recipient and the coordinate precision. |
| F2 | Evaluate solar position at the midpoint of each left-labelled hourly interval, decompose GHI with Erbs, and transpose it to the requested fixed roof plane with pvlib's isotropic model. |
| F3 | Use the SAPM close-mount glass/glass temperature model and the exact per-kWp PVWatts chain defined below with `gamma_pdc=-0.004`, default PVWatts system losses, nominal inverter efficiency `0.96`, and DC/AC ratio `1.2`. |
| F4 | Map `N, NE, E, SE, S, SW, W, NW` to pvlib azimuths `0, 45, 90, 135, 180, 225, 270, 315` degrees. |
| F5 | Let the unrounded target be `monthly_consumption_kwh × 12 × 1.10`. Divide it by the unrounded annual AC yield per kWp, then round capacity upward with `Decimal("0.01")` and `ROUND_CEILING`. The unrounded generation at the reported capacity must cover the target. Reject a result above 75 kWp with a number-free v1-scope error. |
| F6 | Scale each unrounded monthly AC yield by the reported capacity, convert Wh to kWh, and quantize each value to `Decimal("0.01")` with `ROUND_HALF_UP`. Return exactly 12 UTC calendar-month values; the annual value is the exact Decimal sum of those reported values. Reject zero, non-finite, negative, or incomplete modeled yield. |
| F7 | Compute cost as `recommended_kwp × 3150 BRL/kWp`; identify it as an EPE 2025 budget benchmark, not a quotation, and expose the source URL in assumptions. |
| F8 | The wrapper exposes only the five public inputs, hides runtime state/call ID, returns JSON only on success, and converts expected or unexpected failures to one fixed, number-free PT-BR ToolMessage without storing exception text. Its description covers sizing/generation/cost only and does not claim payback. |
| F9 | The tool self-registers through the existing registry; no second registry/list or graph change is introduced. |
| F10 | Audit redaction removes numeric latitude/longitude values from tool input and expected-error storage without redacting consumption, tilt, or unrelated numbers. |

## Exact per-kWp model

For each timestamp, compute a one-kWp reference array in this order:

1. `pvwatts_dc(..., pdc0=1000, gamma_pdc=-0.004)` produces DC watts.
2. Multiply by `1 - pvwatts_losses() / 100` using pvlib's installed default
   system-loss value.
3. Define AC nameplate as `1000 / 1.2` watts and inverter DC input limit as
   `(1000 / 1.2) / 0.96` watts.
4. Call `inverter.pvwatts` with that DC input limit and
   `eta_inv_nom=0.96`; sum only finite, non-negative AC watts.
5. The input frame is hourly, so summed AC watts are numerically Wh. Group by
   UTC calendar month before scaling by the continuous system capacity.

This order fixes system losses before inverter clipping and makes the stated
DC/AC ratio the ratio of array DC nameplate to inverter AC nameplate.

## Numerical provenance and limitations

- Weather: NASA POWER hourly point data, reference calendar year 2025, UTC.
- Cost: EPE 2025 residential benchmark: `1.24 BRL/Wp` integration plus
  `1.91 BRL/Wp` equipment = `3.15 BRL/Wp` (`3150 BRL/kWp`). Source:
  <https://www.epe.gov.br/sites-pt/publicacoes-dados-abertos/publicacoes/PublicacoesArquivos/publicacao-305/topico-730/Apresentac%CC%A7o%CC%83es_Workshop%20da%20Previsa%CC%A3o%20de%20Carga%20-%201RQC%20PLAN%202025-2029.pdf>.
- This is a feasibility estimate from one historical year and generic PVWatts
  assumptions. It is not a forecast, engineering design, equipment quote, or
  guarantee. Task 3.4 later quantizes capacity to real catalog equipment.

## Security and LGPD

Coordinates can identify a residence. Before the weather call, the sizing
module reduces them to `0.1`-degree precision (roughly neighborhood scale) and
performs no logging. NASA POWER is the external recipient of those approximate
coordinates and the fixed reference year; its infrastructure is outside the
application's logging guarantee. `PIIScrubber` must redact `latitude`,
`longitude`, `lat`, and `lon` numeric fields before local audit storage and
must scrub every stored error outcome. The public wrapper catches unexpected
exceptions and emits only its fixed safe message. No bill, CPF/CNPJ, address,
installation number, or user identity reaches NASA POWER or an eval fixture.

## Precedence over legacy sketches

For Task 3.2, this spec and ADR-009 supersede the older conceptual sketches in
`docs/PLAN.md` and `docs/KICKOFF.md`: there is no PVGIS fallback, catalog
selection, or payback behavior in `estimate_solar_system`. Those behaviors are
owned by later Sprint 3 tasks and must not be inferred into this implementation.

Daniel explicitly approved proposed ADR-009 and the use of synthetic Null
Island coordinates `(0, 0)` in the new solar eval on 2026-08-30. They are test
data, not a household location.

## EDD requirements

- Before production registration, create the new capability JSONL and a
  deterministic harness that proves the tool is absent (RED).
- Capability cases cover: complete synthetic inputs select and bind
  `estimate_solar_system`; missing coordinates produce no tool call; an
  unrelated regulated-tariff question keeps `get_tariff` and forbids solar.
- Capability gate: pass@3 >= 0.90.
- Run the existing append-only regression baseline unchanged with pass^3 =
  1.00. A solar-specific strict regression expansion belongs to Task 3.5
  because the protected Sprint 2 harness currently pins the baseline length.
- A live run is allowed only when credentials already exist; otherwise record
  the canonical skipped gate without exposing a secret.

## Acceptance checks

- New tests and eval contracts are observed RED before production code.
- Focused domain, wrapper, audit-redaction, and deterministic harness tests pass.
- Full `pytest`, `ruff check .`, and strict Pyright pass.
- No live NASA request occurs in tests.
- Failure-injection tests prove unexpected exception text and coordinates do
  not reach the tool response or local audit.
- No existing test, prompt, migration, dependency file, or existing ADR is
  edited; the capability fixture is new and the regression baseline unchanged.
