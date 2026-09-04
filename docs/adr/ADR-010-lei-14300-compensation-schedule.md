# ADR-010: Lei 14.300 compensation schedule and post-2028 scenario

**Status:** Accepted by Daniel Moreira on 2026-09-04
**Date:** 2026-09-03
**Decider:** Daniel Moreira
**Tags:** solar, payback, SCEE, Lei-14300, ANEEL

## Context

Task 3.3 needs one deterministic charge fraction for every calendar year in a
twenty-five-year payback projection. Lei 14.300/2022 Article 27 gives explicit
transition fractions only for 2023 through 2028, then directs units to the
Article 17 rules from 2029. Official 2026 material still describes ANEEL's
evaluation of alternative Article 17 methods and a later regulatory process.

ANEEL publishes a separate Componentes Tarifárias dataset that identifies the
`TUSD_FioB` component directly. For the reviewed ENEL RJ B1 conventional
residential Tarifa de Aplicação row effective 2026-03-15, its raw value is
`361.02479751700002 BRL/MWh`. This is better evidence than treating aggregate
TUSD or a separate SCEE tariff row as Fio B.

## Decision

- Encode the Article 27 transition as exact Decimal values: 2023 `0.15`, 2024
  `0.30`, 2025 `0.45`, 2026 `0.60`, 2027 `0.75`, and 2028 `0.90`.
- Reject a connection year before 2023; Article 26/grandfathered projects are
  outside this task.
- For 2029 onward, apply `1.00` only as a conservative planning scenario needed
  to close the projection. Return it together with the machine-readable basis
  `conservative_post_2028_planning_scenario` and a human-readable warning that
  final ANEEL Article 17 tariff rules remain pending. Never call it statutory,
  enacted, current law, or the Article 27 schedule.
- Use `TUSD_FioB` from a minimal reviewed local snapshot of the official ANEEL
  component row. Preserve resource ID, resource hash, update/effective dates,
  allowlisted filter dimensions, unit, and the raw lexical value parsed directly
  as `Decimal("361.02479751700002")`. Do not truncate or pass it through float,
  and do not infer the component from aggregate TUSD or the SCEE TE row.
- Deduplicate identical source rows only when every allowlisted dimension and
  the exact value match. Conflicting matches fail closed. Do not copy the source
  `NumCPFCNPJ` field into the committed component snapshot.
- Lock schedule values in code. Any legal/regulatory replacement requires a new
  ADR, official source review, and new failing tests before the constants or
  scenario change. The schedule is not a user override.
- This ADR supersedes `docs/CONTEXT.md` statements that describe 2029+ as full
  Fio B charged under law or imply that 2029+ belongs to the Article 27
  hardcoded legal schedule. Until that glossary is corrected, this ADR and the
  linked spec are authoritative: `1.00` is only the disclosed planning scenario.

## C4 impact

No C4 Level 1 or Level 2 change is warranted. This is an in-process rule used
by an existing application container; it introduces no actor, external system,
deployable container, or communication path.

## CAP trade-off

CAP classification is **not applicable** because this decision adds no
database, cache, messaging system, replication, or persisted state. Under a
network partition the local versioned rule remains available; no live
regulatory lookup or silent fallback occurs.

## 12-Factor compliance

No new service is introduced, so no separate twelve-factor service review is
applicable. The rule lives in the same codebase and release, needs no config or
backing service, is stateless, logs nothing, and adds no process, port,
dependency, lifecycle hook, or admin command. Existing application compliance
is unchanged.

## Consequences

### Positive

- 2023–2028 results reproduce the enacted transition exactly.
- Every post-2028 value is usable for conservative planning without being
  misrepresented as law.
- Versioned constants make regulatory drift visible in review and tests.

### Negative

- A component snapshot adds a small update obligation when ANEEL publishes a
  new effective tariff.
- The post-2028 scenario can diverge materially from final Article 17 rules.
- Mitigation: expose both caveats in every result and replace the scenario only
  after official rules are final.

## Alternatives considered

1. **Call 100% Fio B the 2029+ legal rule** — rejected because Article 27 points
   to Article 17, and official 2026 evidence shows the implementing method is
   still being developed.
2. **Stop the projection at 2028** — rejected because it cannot satisfy the
   fixed twenty-five-year payback contract.
3. **Let callers override the legal schedule** — rejected because it weakens
   provenance and permits a grounded tool to present arbitrary policy as law.
4. **Fetch regulation at runtime** — rejected because a live page is not a
   versioned calculation input and would add avoidable availability/failure
   modes.

## Risks

- **Scenario presented without its qualifier** — Probability: Medium; Impact:
  High. Mitigation: return regulatory basis per year and repeat it in the
  assumptions block and tool description.
- **Stale regulation after ANEEL acts** — Probability: High; Impact: High.
  Mitigation: new ADR plus official-source review and RED tests before release.
- **Stale or mismatched component row** — Probability: Medium; Impact: High.
  Mitigation: retain the full row dimensions, effective dates, resource ID/hash,
  and exact `Decimal("361.02479751700002")` value in the reviewed snapshot;
  full-key identical duplicates deduplicate and conflicts fail closed.

## Implementation notes

Return a small typed value containing `fraction` and `regulatory_basis`; a bare
number cannot preserve the required legal distinction. Decimal constants, one
year branch, and one minimal component snapshot are sufficient. No database
table, runtime fetch, remote configuration, or policy engine is warranted.

## References

- Lei 14.300/2022, Articles 17 and 27:
  <https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14300.htm>
- ANEEL MMGD guidance:
  <https://www.gov.br/aneel/pt-br/assuntos/geracao-distribuida>
- ANEEL Resolução Normativa 1.000/2021, Article 291:
  <https://www2.aneel.gov.br/cedoc/ren20211000.pdf>
- Ministry of Finance, Nota Técnica SEI 958/2026/MF on ANEEL's Article 17
  subsidy-gathering proceeding:
  <https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-reformas-economicas/manifestacoes-em-consultas-publicas-de-orgaos-reguladores/2026/agencia-nacional-de-energia-eletrica-aneel/sei_58000857_nota_tecnica_958-1-_260325_090518.pdf/view>
- ANEEL Componentes Tarifárias 2026 resource
  `e8717aa8-2521-453f-bf16-fbb9a16eea39`, hash
  `c4bd43306833b0583a2fad9fa0945665`, updated 2026-09-03:
  <https://dadosabertos.aneel.gov.br/pt_BR/dataset/componentes-tarifarias/resource/e8717aa8-2521-453f-bf16-fbb9a16eea39>
- `docs/specs/sprint-3-solar-payback.md`.
