# ADR-011: Year-by-year residential solar payback

**Status:** Accepted by Daniel Moreira on 2026-09-04
**Date:** 2026-09-03
**Decider:** Daniel Moreira
**Tags:** solar, payback, cash-flow, Decimal, credits

## Context

A single `system cost / first-year savings` division cannot represent the
Article 27 transition, the uncertain post-2028 planning assumption, tariff
escalation, generation degradation, seasonal credit carryover/expiry, or Group
B minimum availability billing. Task 3.3 needs an auditable answer that can be
fed directly by Task 3.2 sizing and the existing regulated tariff data without
adding a financial dependency or service.

Only average monthly consumption and twelve monthly generation values are
available. There is no hourly load curve, so the model cannot establish
behind-the-meter self-consumption. It must make that limitation conservative
and explicit rather than inventing an hourly profile.

## Decision

- Simulate exactly 300 monthly cycles and aggregate them into twenty-five
  calendar-year cash-flow records.
- Keep consumption constant in kWh. Use the twelve generation inputs for year
  one, degrade them by `0.5%` per year by default, and escalate both regulated
  base tariff and versioned `TUSD_FioB` component by `5%` real per year by
  default. Permit validated optional rate overrides; do not permit a horizon
  override.
- Carry surplus energy in monthly lots and use oldest lots first. With zero-based
  months, a lot created after month `0` allocation is usable through month `59`
  and removed before month `60` allocation.
- With no hourly load shape, treat every offset kWh as network-compensated and
  subject to ADR-010's charge fraction. This intentionally tends to understate
  savings.
- Model the Group B 30/50/100 kWh availability equivalent as a minimum monetary
  floor for monophase or two-conductor biphase / three-conductor biphase /
  triphase service, not as a charge added twice. Use conductor-aware literals;
  generic `bifasica` is ambiguous and is not accepted.
- Use Decimal for all values. Aggregate before rounding; report BRL and kWh to
  two decimals with `ROUND_HALF_UP`.
- Treat the system cost as the sole time-zero outflow. Each annual net cash flow
  is regulated baseline energy cost minus modeled solar energy cost. Return the
  first whole year with non-negative cumulative cash flow, else `null`.
- Compute annual IRR from the reported sequence
  `[-cost, year1_savings, ..., year25_savings]`, which contains one negative
  flow followed by non-negative flows. Use Decimal bisection with precision 50,
  initial bracket `(-0.999999, 1]`, at most twenty high-bound doublings, rate
  tolerance `0.00000001`, and at most 256 bisections. If `NPV(low) <= 0`, the
  unique root lies below the supported numerical bracket (or there is no
  positive future flow), so return `null`; lock this boundary in a deterministic
  test. Also return `null` for no high bracket, evaluation failure, or
  non-convergence. Do not add `numpy-financial` or another dependency.
- Give credits remaining after month 300 no terminal value.
- Return full assumptions and provenance; do not include financing, tax,
  maintenance, battery, catalog, UI, or prompt behavior.

## C4 impact

No C4 Level 1 or Level 2 change is warranted. The decision adds deterministic
domain logic and one tool inside the existing application process. Existing
user, Anthropic, Streamlit/LangGraph, and DuckDB-audit relationships do not
change.

## CAP trade-off

CAP classification is **not applicable** because the simulation introduces no
database, cache, queue, replication, or persisted credit balance. Its credit
ledger is ephemeral input-derived state inside one deterministic invocation.
There is no partition behavior to trade against consistency.

## 12-Factor compliance

No new service is introduced. The calculation stays in the existing codebase
and process; dependencies remain locked; there is no new config/backing
service/build stage/port/concurrency model; the function is stateless and
disposable; tests run the same logic; it emits no file or log; and it requires
no admin process. Existing application compliance is unchanged.

## Consequences

### Positive

- Cash flow, payback, and IRR remain reproducible from the reported annual
  records.
- Seasonal generation and legally required credit lifetime affect the result
  without inventing an hourly consumption profile.
- Inputs reuse existing sizing and tariff values, keeping the new tool thin and
  independently testable.

### Negative

- Constant monthly consumption is less accurate than a twelve-month bill
  history.
- Treating all offset energy as network-compensated is deliberately
  conservative and may materially understate savings even with the exact
  `TUSD_FioB` component.
- Omitting maintenance, replacement, taxes, financing, and residual value makes
  this a bounded energy-cost comparison, not a complete investment model.

## Alternatives considered

1. **Single-division payback** — rejected because it freezes year-one economics
   and cannot represent the legal transition or credit ledger.
2. **Hourly self-consumption simulation** — rejected because no hourly load
   input exists; synthesizing one would violate the no-invented-numbers rule.
3. **Add a financial library** — rejected because one deterministic IRR root can
   be solved with the standard library/domain code and a dependency would add
   more surface than behavior.
4. **Store monthly credit balances** — rejected because this is a prospective
   projection, not operational billing; persistence would invent a new data
   lifecycle and confuse simulated credits with a distributor's ledger.

## Risks

- **Consumers read the projection as guaranteed savings** — Probability:
  Medium; Impact: High. Mitigation: assumptions explicitly call it a feasibility
  scenario and enumerate excluded charges/costs.
- **Rounding changes payback at a year boundary** — Probability: Low; Impact:
  Medium. Mitigation: calculate payback and IRR from the same reported cent-level
  annual cash flows and document `ROUND_HALF_UP`.
- **Credit expiry off by one billing cycle** — Probability: Medium; Impact:
  Medium. Mitigation: lock cycle order and the exact boundary in focused tests
  and disclose the conservative convention.

## Implementation notes

A list of `(creation_month, remaining_kwh)` lots plus FIFO consumption is enough
for the fixed horizon. Reuse Pydantic, Decimal, the existing tool registry, and
the safe `ToolMessage` wrapper. Do not add repositories, services, persistence,
NumPy finance helpers, or generalized simulation frameworks.

The pure calculator has no I/O. The wrapper performs only allowlisted local
reads of the committed Enel RJ B1 conventional tariff snapshot and committed
`TUSD_FioB` component snapshot; it performs no network, database, or logging
operation.

## References

- `docs/specs/sprint-3-solar-payback.md`.
- ADR-010, compensation schedule and post-2028 scenario.
- Lei 14.300/2022, Articles 13, 16, 17, and 27:
  <https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14300.htm>
- ANEEL MMGD guidance:
  <https://www.gov.br/aneel/pt-br/assuntos/geracao-distribuida>
- ANEEL Resolução Normativa 1.000/2021, Article 291:
  <https://www2.aneel.gov.br/cedoc/ren20211000.pdf>
