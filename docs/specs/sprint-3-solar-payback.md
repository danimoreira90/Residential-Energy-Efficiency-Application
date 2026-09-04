# Spec: Sprint 3 Task 3.3 — residential solar payback

**Status:** Approved by Daniel Moreira on 2026-09-04
**Date:** 2026-09-03
**Scope:** Sprint 3 Task 3.3 only

## Problem

Task 3.2 returns a planning cost and twelve monthly generation values, and the
tariff snapshot provides regulated B1 energy prices. The application still
cannot turn those grounded inputs into an auditable payback estimate that
accounts for the post-2022 SCEE transition, Group B minimum billing, seasonal
credits, tariff escalation, or PV degradation.

## User outcome

A prospective residential B1 customer can obtain a deterministic twenty-five
year cash-flow projection, the first whole year in which cumulative savings
recover the initial cost (or `null`), and annual-cash-flow IRR (or `null`). The
result identifies every legal fact, planning assumption, tariff component, and
omitted cost; it is not a quotation, legal opinion, financing offer, or guarantee.

## In scope

- New/prospective, local, residential B1 microgeneration under the Article 27
  transition; `connection_year >= 2023`.
- A pure, offline `energia.solar.payback` calculation and the small legal
  schedule helper it consumes.
- A typed, self-registering `solar_payback` LangChain tool using the existing
  registry and `ToolMessage`/`Command` pattern.
- Constant average monthly consumption, twelve January-to-December generation
  inputs, monthly FIFO energy-credit accounting, and a fixed twenty-five-year
  horizon.
- Regulated base tariff (TUSD + TE), the official ANEEL `TUSD_FioB` component,
  and Group B minimum availability billing.
- Decimal arithmetic, disclosed assumptions/provenance, and deterministic
  tests/evals written before production registration.

## Out of scope

- Installations covered by Article 26, connection before 2023, minigeneration,
  Group A, B1 baixa renda, rural/commercial subclasses, remote self-consumption,
  shared generation, or multiple consumer units.
- Financing, discount rates/NPV, taxes, PIS/COFINS, ICMS, COSIP/CIP, tariff
  flags, maintenance, insurance, replacement, residual value, tax incentives,
  demand charges, curtailment, outages, batteries, or hourly self-consumption.
- Equipment catalog/quantization, vendor quotations, UI, prompt edits, bill
  ingestion, schema/migration changes, or a new dependency.
- Treating the post-2028 planning scenario as current law, or substituting
  aggregate TUSD/SCEE TE for the official `TUSD_FioB` component.

## Regulatory facts and planning boundary

1. Lei 14.300/2022 Article 27 applies these fractions to its named distribution
   components on compensated active energy for units not covered by Article 26:

   | Calendar year | Charge fraction | Status |
   |---|---:|---|
   | 2023 | 15% | Article 27 transition |
   | 2024 | 30% | Article 27 transition |
   | 2025 | 45% | Article 27 transition |
   | 2026 | 60% | Article 27 transition |
   | 2027 | 75% | Article 27 transition |
   | 2028 | 90% | Article 27 transition |

2. Article 27 points to Article 17 from 2029; it does **not** establish a 100%
   Fio B rule for 2029 onward. Official material published in 2026 documents an
   ongoing ANEEL process evaluating alternatives, with later impact analysis
   and public consultation. To complete a twenty-five-year projection, this
   task applies `100%` of the versioned `TUSD_FioB` component from 2029 onward
   and labels every such year `conservative_post_2028_planning_scenario`. This
   is an application assumption pending final ANEEL Article 17 regulation,
   never a statement of current law.
3. Article 13 gives energy credits a sixty-month life and requires oldest
   credits to be used first. Months are zero-based: a surplus lot created after
   allocation in month `0` is usable through month `59` and is removed before
   month `60` allocation. This exact conservative boundary must be disclosed.
4. Article 16 preserves minimum billable energy. ANEEL's Group B categories are
   30 kWh for monophase or two-conductor biphase service, 50 kWh for
   three-conductor biphase service, and 100 kWh for triphase service. The tool
   uses unambiguous conductor-aware literals rather than a generic `bifasica`.
5. ANEEL's separate Componentes Tarifárias dataset identifies `TUSD_FioB`
   directly. For ENEL RJ's B1 Convencional, Residencial/Residencial,
   `Não se aplica`, Tarifa de Aplicação row effective 2026-03-15, the reviewed
   raw source value is `361.02479751700002 BRL/MWh`. Parse that lexical value
   directly as `Decimal("361.02479751700002")`; do not pass it through float or
   truncate it. The resource is
   `e8717aa8-2521-453f-bf16-fbb9a16eea39`, hash
   `c4bd43306833b0583a2fad9fa0945665`, updated 2026-09-03. Preserve those filter
   dimensions and metadata in a minimal local snapshot. Do not infer Fio B from
   aggregate TUSD or the separate SCEE TE row.

Official sources, verified 2026-09-03:

- Lei 14.300/2022, especially Articles 13, 16, 17, and 27:
  <https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14300.htm>
- ANEEL MMGD guidance (credit validity and Group B availability cost):
  <https://www.gov.br/aneel/pt-br/assuntos/geracao-distribuida>
- ANEEL Resolução Normativa 1.000/2021, Article 291 (conductor-aware Group B
  availability values):
  <https://www2.aneel.gov.br/cedoc/ren20211000.pdf>
- Ministry of Finance analysis of ANEEL Subsidy-Gathering Proceeding 23/2025,
  documenting alternatives and the continuing Article 17 rulemaking:
  <https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-reformas-economicas/manifestacoes-em-consultas-publicas-de-orgaos-reguladores/2026/agencia-nacional-de-energia-eletrica-aneel/sei_58000857_nota_tecnica_958-1-_260325_090518.pdf/view>
- ANEEL Componentes Tarifárias 2026 resource and data dictionary:
  <https://dadosabertos.aneel.gov.br/pt_BR/dataset/componentes-tarifarias/resource/e8717aa8-2521-453f-bf16-fbb9a16eea39>

## Public contract

The model-visible `SolarPaybackToolInput` contains only:

| Field | Type | Contract/source |
|---|---|---|
| `monthly_consumption_kwh` | `Decimal` | Finite, `> 0`; reusable from the input accepted by `estimate_solar_system`. |
| `monthly_generation_kwh` | `list[Decimal]` | Exactly twelve finite, non-negative January-to-December values; reusable unchanged from `estimate_solar_system.monthly_generation_kwh`; at least one must be positive. |
| `system_cost_brl` | `Decimal` | Finite, `> 0`; reusable from `estimate_solar_system.estimated_cost_brl`. |
| `distributor` | `str` | Non-empty distributor name. Only the canonical committed Enel RJ B1 conventional snapshot and its aliases are accepted. The wrapper resolves rates; the model never supplies them. |
| `connection_year` | `int` | Boolean rejected; `>= 2023`. It is year one of the projection and selects the calendar-year transition fraction. |
| `connection_type` | `Literal["monofasica_ou_bifasica_2_condutores", "bifasica_3_condutores", "trifasica"]` | Selects the 30/50/100 kWh availability floor without an ambiguous biphase label. |
| `real_tariff_inflation_rate` | `Decimal` | Optional; default `0.05`; finite and in `[0, 1)`. |
| `annual_generation_degradation_rate` | `Decimal` | Optional; default `0.005`; finite and in `[0, 1)`. |

All public numeric values reject booleans, NaN, infinities, and positive
digit-only values with exactly 11 or 14 digits before Decimal normalization.
This narrow LGPD boundary prevents CPF/CNPJ-shaped identifiers from being
accepted, echoed in assumptions, or stored by the audit callback. The horizon,
credit lifetime, legal schedule, tariff/component rates, and post-2028 scenario
are not caller overrides.

The wrapper resolves exactly one matching committed Enel RJ B1 conventional
tariff snapshot and exactly one overlapping `TUSD_FioB` component snapshot. It
passes an internal typed `SolarPaybackInput` to the pure calculator containing
the public numeric values plus `base_tariff_brl_per_kwh`,
`tusd_fio_b_brl_per_mwh`, tariff/component provenance, and effective dates. The
internal rates must be finite and positive, and converted `TUSD_FioB` in
BRL/kWh must not exceed the base tariff. The wrapper neither calls nor expands
`get_tariff`; unmatched, missing, non-overlapping, or conflicting snapshot data
fails safely.

`SolarPaybackEstimate` contains:

- `initial_outlay_brl`: the system cost, rounded to cents.
- `annual_cash_flows`: exactly twenty-five records with:
  `projection_year` (1–25), `calendar_year`, `generation_kwh`,
  `compensated_kwh`, `expired_credit_kwh`, `ending_credit_kwh`,
  `baseline_energy_cost_brl`, `solar_energy_cost_brl`,
  `net_cash_flow_brl`, `cumulative_cash_flow_brl`,
  `compensation_charge_fraction`, and `regulatory_basis`.
- `payback_year`: first whole `projection_year` whose reported cumulative cash
  flow is non-negative; otherwise `null`.
- `irr_annual_percent`: IRR of `[-initial_outlay, year-1 cash flow, ..., year-25
  cash flow]`, rounded to `0.01` percentage point; `null` when all annual cash
  flows are zero or a unique finite root cannot be calculated.
- `assumptions`: all input values and units, fixed/default values, formulas,
  rounding rules, source URLs, ANEEL component resource ID/hash/effective date,
  the post-2028 non-legal scenario label, credit-expiry convention, omitted
  costs, and the no-terminal-value treatment of remaining credits.

## Calculation contract

All arithmetic is `Decimal`; binary floating-point must not enter tariff,
money, generation, ledger, cumulative-payback, or IRR calculations.

For projection year `n` in `1..25`, calendar year
`y = connection_year + n - 1`:

1. `tariff_y = base_tariff_brl_per_kwh × (1 + inflation)^(n - 1)`.
2. `fio_b_y = (tusd_fio_b_brl_per_mwh / 1000) × (1 + inflation)^(n - 1)`.
3. Each base monthly generation value is multiplied by
   `(1 - degradation)^(n - 1)`. The consumption input remains constant in real
   kWh across all months.
4. At the start of each month, expire credit lots whose expiry index has been
   reached. Satisfy consumption with the oldest surviving lots first, then the
   current month's generation. Store unused current generation as one new lot.
   `compensated_kwh` is old credits used plus current generation used.
5. Because no hourly load shape is available, conservatively treat all
   `compensated_kwh` as network-compensated energy subject to the applicable
   charge fraction. Do not infer behind-the-meter self-consumption.
6. Let `A` be 30, 50, or 100 kWh from the conductor-aware
   `connection_type` mapping above:

   ```text
   baseline_month_brl = max(monthly_consumption_kwh, A) × tariff_y
   residual_month_brl = uncompensated_kwh × tariff_y
   transition_charge_brl = compensated_kwh × fio_b_y × charge_fraction(y)
   solar_month_brl = max(A × tariff_y,
                         residual_month_brl + transition_charge_brl)
   monthly_savings_brl = baseline_month_brl - solar_month_brl
   ```

   The maximum applies the availability amount as a floor, not a second charge.
7. Sum unrounded monthly values into annual values. Report money at
   `Decimal("0.01")`, kWh at `Decimal("0.01")`, and percentages at
   `Decimal("0.01")`, all with `ROUND_HALF_UP`.
8. The billing constraints make every annual saving non-negative, so the IRR
   sequence has exactly one negative time-zero outlay followed by non-negative
   annual flows. Treat a negative calculated annual saving as an invalid model
   result. With at least one positive annual flow, solve `NPV(r) = 0` for the
   unique `r > -1` using Decimal bisection under `localcontext(prec=50)`:
   `low = Decimal("-0.999999")`, `high = Decimal("1")`; while `NPV(high) > 0`,
   double `high`, at most twenty times. If no future flow is positive, return
   `null` before solving. If `NPV(low) <= 0`, the unique root lies below the
   supported numerical bracket (or there is no positive future flow), so return
   `null`. Also return `null` when no high bracket exists after those
   expansions, evaluation fails, or a finite midpoint is not reached. Otherwise
   bisect for at most 256 iterations, stopping when
   `high - low <= Decimal("0.00000001")`, and return the midpoint times 100
   rounded to `0.01` percentage point. Add no finance dependency.
9. Remaining credits after month 300 have no terminal value. Payback is not
   extrapolated past year twenty-five.

## Functional requirements

| ID | Requirement |
|---|---|
| F1 | Represent 2023–2028 Article 27 fractions exactly as Decimal constants. A year from 2029 onward returns `1.00` only with the non-statutory `conservative_post_2028_planning_scenario` basis. Reject pre-2023 use. |
| F2 | Simulate 300 monthly cycles with the fixed-consumption, degraded-generation, sixty-month FIFO ledger and conservative all-compensated-energy convention above. |
| F3 | Apply the connection-type availability floor and annual escalation to both the regulated base tariff and versioned `TUSD_FioB` component without double-counting the floor. |
| F4 | Produce exactly twenty-five annual records; calculate payback from reported cumulative cash flow and annual IRR from the time-zero outlay plus reported annual flows. |
| F5 | Use Decimal throughout and apply the specified output rounding only after annual aggregation; no single-division payback. |
| F6 | Return a complete assumptions/provenance block that distinguishes legal facts, official tariff inputs, conservative modeling assumptions, and omissions. |
| F7 | The `solar_payback` wrapper exposes only the eight public inputs, including `distributor` but no tariff rate/provenance field. It hides runtime state/call ID, resolves one committed Enel RJ B1 conventional tariff/component pair, returns JSON only on success, and uses one fixed number-free PT-BR message for schema validation, expected errors, and unexpected errors. No input value or exception text may appear in the error response or audit error. |
| F8 | Self-register through the existing registry. Do not create a second tool list, call another tool internally, change the graph, or edit the system prompt. |
| F9 | Accept no PII, coordinates, address, installation number, document, user identifier, secret, or external-service credential. The pure calculator performs no I/O. The wrapper performs only allowlisted local reads of the two committed tariff/component snapshots and performs no network, DB, or logging operation. Existing tool-call audit receives only the model inputs and safe result/error. |

The fixed error message is:

> Não consegui calcular o retorno solar com as premissas fornecidas. Revise os dados e tente novamente.

It contains no digit, currency symbol, unit, percentage, offending value, or
exception detail. Define an explicit Pydantic `args_schema` and assign the
registered LangChain tool a `handle_validation_error` callable that returns
exactly this message. Thus BaseTool consumes pre-body `ValidationError` and
ToolNode emits the safe content as the tool call's `ToolMessage`; the wrapper
catches expected and unexpected post-validation failures and returns the same
message. The deterministic boundary test must invoke the real registered tool
through `ToolNode` with an invalid tool call, without mocking the calculator,
and assert one exact safe `ToolMessage` with the original tool-call ID and no
offending value/exception text.

## EDD and test requirements

- Before production registration, create deterministic domain, schedule,
  wrapper, and eval-harness tests and observe them fail for the missing feature.
  Existing tests and append-only regression fixtures remain unchanged.
- Domain cases cover every schedule year and the post-2028 label; each
  connection type; FIFO consumption; exact expiry boundary; credit carryover
  across years; degradation/inflation; availability floor; no-payback; negative
  IRR; positive IRR; `NPV(low) <= 0` returning `null` at the supported-bracket
  boundary; and remaining credits with no terminal value.
- Wrapper cases cover the exact public schema, successful Enel RJ alias
  resolution, rejection of unmatched/conflicting snapshots, success JSON,
  registration, and identical number-free handling for schema, expected, and
  unexpected failures. The schema case crosses the real ToolNode boundary.
- Add a new capability fixture for a complete grounded payback request, missing
  required tariff/sizing data (no call), and an unrelated sizing-only request
  that keeps `estimate_solar_system` and forbids `solar_payback`.
- Capability gate: pass@3 >= 0.90. Regression gate: pass^3 = 1.00. Without an
  existing `ANTHROPIC_API_KEY`, report the live gates as `SKIPPED`, never pass.
- No live ANEEL, NASA POWER, or Anthropic call occurs in deterministic tests.

## Architecture checks

- **C4:** no Level 1 or Level 2 change is warranted. The existing user,
  Streamlit/LangGraph application, and DuckDB audit relationships are unchanged;
  this task adds only in-process domain calculation and a registered tool.
- **CAP:** not applicable. This task selects no database, cache, or messaging
  system and adds no persisted state; the monthly credit ledger is an ephemeral
  value local to one calculation.
- **12-Factor:** no new service is introduced. The calculation remains in the
  existing codebase and process, declares no dependency/config, is stateless,
  writes no file/log, opens no port, and needs no lifecycle/admin process.

## Acceptance checks

- The spec and ADR-010/ADR-011 are approved before implementation.
- New tests/eval contracts are observed RED before production code.
- Focused schedule/domain/wrapper/eval-harness tests, full pytest, Ruff, and
  strict Pyright pass with fresh output.
- Every output number traces to an input, locked Decimal constant, or documented
  formula; every post-2028 record carries the scenario label.
- No existing test, eval baseline, prompt, migration, dependency, UI file, or
  existing ADR is edited.

## Implementation notes

- Reuse `Decimal`, Pydantic validation, `register_tool`, and the existing safe
  `Command`/`ToolMessage` wrapper pattern. A small domain function and monthly
  list of credit lots are sufficient; no service, repository, database table,
  queue, abstraction layer, or third-party IRR package is warranted.
- Do not expand `get_tariff`. The payback wrapper resolves its `distributor`
  against the committed Enel RJ B1 conventional tariff snapshot, then loads the
  smallest reviewed component snapshot containing only the matched ANEEL row's
  resource ID, hash, update/effective dates, allowlisted filter dimensions,
  unit, and raw Decimal value. If the source contains duplicate identical rows,
  deduplicate only by the complete allowlisted dimensions plus exact value;
  conflicting rows fail closed. Never copy `NumCPFCNPJ` into the snapshot and
  never derive Fio B from aggregate TUSD or the SCEE TE row.

## Open questions

None block the deterministic contract. Final ANEEL Article 17 regulation is an
external future change: replace the post-2028 scenario only through a new ADR,
updated official provenance, and new RED tests.
