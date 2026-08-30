# Spec: Sprint 2 tariff-awareness follow-up

**Status:** Approved for implementation  
**Date:** 2026-08-30  
**Scope:** Tasks 2.2, 2.4, and 2.5

## Problem

The chatbot can look up Enel RJ's conventional tariff but cannot report the
authoritative Bandeira Tarifária or compare a user-supplied consumption profile
against Tarifa Branca. Both features must be auditable and offline at runtime.

## In scope

- A versioned local 12-month Bandeira snapshot for 2025-09 through 2026-08,
  sourced from ANEEL's *Bandeira Tarifária - Acionamento* resource
  `0591b8f6-fe54-437b-b72b-1aa2efd46e42` (updated 2026-08-24; source hash
  `c098ee1b39e75b28b5ac646e1e9746ca`).
- Pure `current_bandeira` and `bandeira_history` domain functions and typed,
  registered LangChain tools.
- An Enel RJ B1 Tarifa Branca simulation using the application rates in
  REH 3570/2026, provided by the user as ponta, intermediária, and fora de
  ponta kWh buckets.
- Deterministic fixture and harness coverage plus append-only capability and
  regression eval fixtures.

## Out of scope

- Live ANEEL requests, cache refresh jobs, new dependencies, bill/UC reads,
  taxes, COSIP, Bandeira charges in the Branca comparison, subsidized tariffs,
  alternative distributors, or a guessed/default consumption profile.
- Editing `src/energia/chat/prompts.py` or any existing test/eval fixture.

## Functional requirements

| ID | Requirement |
|---|---|
| F1 | `current_bandeira(as_of)` returns the exact record for that reference month; a missing month is explicit rather than stale or invented. |
| F2 | `bandeira_history(as_of, months)` returns up to 12 chronological snapshot records ending in the requested month. |
| F3 | Both flag tool payloads expose only snapshot-sourced flag, period, surcharge, and provenance. |
| F4 | The Branca comparison uses exact `Decimal` tariff calculations from REH 3570/2026 and user-supplied kWh buckets. |
| F5 | The Branca tool rejects negative consumption and profiles whose buckets do not form a meaningful input; unsupported distributor paths return a number-free disclaimer. |
| F6 | The Branca result states that it compares regulated TUSD+TE only, excluding taxes, COSIP, and Bandeira. |
| F7 | Every new LLM-facing tool self-registers; it has deterministic tests and new append-only eval examples. |

## Authoritative numerical inputs

- Bandeira source: ANEEL activation dataset above. The committed review window
  is: 2025-09 Vermelha Patamar 2 (R$ 0.07877/kWh); 2025-10 and 2025-11
  Vermelha Patamar 1 (R$ 0.04463/kWh); 2025-12 Amarela (R$ 0.01885/kWh);
  2026-01 through 2026-04 Verde (R$ 0/kWh); and 2026-05 through 2026-08
  Amarela (R$ 0.01885/kWh).
- Branca source: Enel RJ REH 3570/2026, table 2: ponta TUSD 1665.26 + TE
  493.30 R$/MWh; intermediária 1122.11 + 314.47 R$/MWh; fora de ponta
  578.96 + 314.47 R$/MWh. These are application tariffs effective
  2026-03-15 through 2027-03-14.

## Security and LGPD

The tools do not read a bill, database, or installation number. They validate
only distributor strings, a bounded month count, and non-negative consumption
values. Logs may contain only tool name, month, and distributor scope.

## EDD requirements

- Capability fixture: tool selection for the current Bandeira, history, and
  user-supplied Branca profile; code/rule grader, pass@3 >= 0.90.
- Regression fixture: existing `get_tariff` lookup remains selected and its
  answer must not use a Bandeira/Branca tool; code/rule grader,
  pass^3 = 1.00.
- Before implementation, the new deterministic tests must fail because the
  tools/functions do not exist. A live run is permitted only when the existing
  `ANTHROPIC_API_KEY` is present; otherwise its exit-2 skip is recorded.

## Acceptance checks

- New focused tests observe RED then GREEN without editing existing tests.
- `pytest`, `ruff check .`, and `pyright` pass.
- New JSONL files parse and deterministic eval/harness tests pass three times.
- No protected path is changed.
