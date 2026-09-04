> **For agentic workers:** REQUIRED: Use subagent-driven-development for every task.

# Plan: Sprint 3 Task 3.3 — residential solar payback

**Date:** 2026-09-03
**Status:** In execution after Daniel's 2026-09-04 approval
**Spec:** `docs/specs/sprint-3-solar-payback.md`

## Contract

- One fresh implementation agent per task; agents preserve other edits and never mutate Git.
- Existing tests are immutable. Create only the listed tests and capability fixture.
- EDD and RED evidence precede production code. A failing environment is not RED evidence.
- No prompt, graph, UI, migration, dependency, or `get_tariff` change. Audit
  changes are limited to the approved Task 3.3 input/error sanitization fix.
- Daniel alone stages, commits, pushes, opens PRs, merges, and tags.

## Dependency order

```text
spec + ADRs
  -> eval/RED contracts
  -> GD schedule + Fio B snapshot
  -> pure 300-month payback
  -> registered safe tool
  -> spec review
  -> quality/security review
  -> full gates and manual Git handoff
```

## Task 1 — EDD and RED contracts

Fresh QA agent creates only:

- `evals/capability/solar_payback.jsonl`
- `tests/tariff/test_gd.py`
- `tests/solar/test_payback.py`
- `tests/chat/tools/test_solar_payback.py`
- `tests/evals/test_solar_payback_harness.py`

The fixture has three cases: complete grounded payback selects `solar_payback`; missing
required data makes no payback call; sizing-only selects `estimate_solar_system` and forbids
`solar_payback`. Tests cover F1–F9, including exact schedule/provenance, all three connection
types, month 0/59/60 FIFO expiry, floor math, escalation/degradation, payback, positive and
negative IRR, unsupported IRR bracket, 25 annual rows, no terminal credit value, eight-field
tool schema, registration, snapshot mismatch/conflict, and the real ToolNode validation path.

Run before any Task 3.3 production file exists:

```powershell
& '.venv\Scripts\python.exe' -m pytest tests/tariff/test_gd.py tests/solar/test_payback.py tests/chat/tools/test_solar_payback.py tests/evals/test_solar_payback_harness.py -q -p no:cacheprovider --basetemp "$env:TEMP\energia-task33-red"
$LASTEXITCODE
```

Accept RED only when exit is non-zero solely because the new modules/tool are absent. Preserve
the output; do not edit these tests after production starts without Daniel's explicit approval.

## Task 2 — GD schedule and component snapshot

Fresh Python agent creates only:

- `src/energia/tariff/gd.py`
- `src/energia/tariff/snapshots/enel_rj_fio_b.json`

Implement exact Decimal Article 27 fractions, pre-2023 rejection, and the explicitly
non-statutory 2029+ basis. The snapshot contains only allowlisted ENEL RJ B1 conventional row
dimensions and provenance, with raw `361.02479751700002` BRL/MWh; never include
`NumCPFCNPJ`. Deduplicate identical complete rows and fail closed on conflicts/mismatches.
No network, DB, cache, policy engine, or new dependency.

```powershell
& '.venv\Scripts\python.exe' -m pytest tests/tariff/test_gd.py -q -p no:cacheprovider --basetemp "$env:TEMP\energia-task33-gd"
$LASTEXITCODE
```

GREEN requires exit `0`.

## Task 3 — Pure payback calculation

Fresh Python agent creates only `src/energia/solar/payback.py`.

Implement the approved Pydantic/Decimal input and output models, exactly 300 monthly cycles,
FIFO lots, one availability floor, annual tariff escalation and generation degradation,
25 annual rows, cumulative whole-year payback, and the specified stdlib Decimal IRR bisection.
Aggregate before `ROUND_HALF_UP`; return complete assumptions/provenance; perform no I/O or
logging.

```powershell
& '.venv\Scripts\python.exe' -m pytest tests/tariff/test_gd.py tests/solar/test_payback.py -q -p no:cacheprovider --basetemp "$env:TEMP\energia-task33-domain"
$LASTEXITCODE
```

GREEN requires exit `0`.

## Task 4 — Registered safe tool

Fresh chatbot-tool agent modifies only `src/energia/chat/tools/solar.py`.

Preserve sizing behavior. Add `SolarPaybackToolInput` and `solar_payback` with exactly eight
model-visible inputs. Resolve `distributor` against the two committed local snapshots, build
the internal domain input, call the calculator once, and return its JSON. Register through the
existing registry. Configure `handle_validation_error` and all post-validation failures to
return the same fixed number-free message. Do not call or expand `get_tariff`.

```powershell
& '.venv\Scripts\python.exe' -m pytest tests/chat/tools/test_solar_payback.py tests/evals/test_solar_payback_harness.py -q -p no:cacheprovider --basetemp "$env:TEMP\energia-task33-tool"
$LASTEXITCODE
```

Then rerun the complete focused command from Task 1. GREEN requires exit `0`.

## Task 5 — Independent reviews

1. Fresh read-only spec reviewer maps F1–F9 and the calculation contract to code/tests.
2. Separate fresh read-only quality/security reviewer checks Decimal purity, snapshot
   allowlisting, safe validation/errors, no PII/secrets/network/DB/logging, registry uniqueness,
   type safety, protected paths, and over-engineering.

Any finding returns to a fresh bounded implementation agent, then both reviews repeat.

## Task 6 — Final gates

Use unique `$env:TEMP` basetemps; `$LASTEXITCODE` is authoritative.

```powershell
& '.venv\Scripts\python.exe' -m pytest tests/tariff/test_gd.py tests/solar/test_payback.py tests/chat/tools/test_solar_payback.py tests/evals/test_solar_payback_harness.py -q -p no:cacheprovider --basetemp "$env:TEMP\energia-task33-final"
& '.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP\energia-task33-full"
& '.venv\Scripts\python.exe' -m ruff check src tests
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' '.venv\Lib\site-packages\pyright\dist\index.js' -p pyrightconfig.json
```

All deterministic commands must exit `0`. Run live evals only if credentials already exist:

```powershell
& '.venv\Scripts\python.exe' -m energia.evals.run capability solar_payback
& '.venv\Scripts\python.exe' -m energia.evals.run regression
```

Required live gates are capability pass@3 >= 0.90 and regression pass^3 = 1.00. Without a key,
record both as `SKIPPED` with exit `2`; never call that a pass.

Review `git status --short`, `git diff --check`, the full intended diff, and protected paths.
Exclude `.pytest-tmp*` and the nested repository from staging.

## Daniel-only logical commits

1. `docs(solar): specify residential payback model` — spec, plan, ADR-010/011, `CONTEXT.md`.
2. `test(solar): define residential payback contracts` — five new eval/test files.
3. `feat(tariff): add Article 27 schedule and Fio B snapshot` — GD module and snapshot.
4. `feat(solar): add grounded residential payback tool` — payback module and solar tool.

Exact narrow staging/push commands are generated only after the final branch/status check.
