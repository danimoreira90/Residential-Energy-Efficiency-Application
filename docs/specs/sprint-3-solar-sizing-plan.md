> **For agentic workers:** REQUIRED: Use subagent-driven-development for every task.
> Each task = one fresh subagent. Spec compliance review → code quality review → ✅ done.
> No task is "done" without: passing verification command, reviewer sign-off.

# Plan: Sprint 3 Task 3.2 — solar system sizing

**Spec:** `docs/specs/sprint-3-solar-sizing.md`  
**Decision:** `docs/adr/ADR-009-pvlib-nasa-power-solar-sizing.md`  
**Status:** Ready to implement

## EDD preamble

Create the capability JSONL and deterministic harness before registering the
tool. Capture the missing-tool RED result. The live capability/regression gate
uses existing credentials only; otherwise its canonical skip is evidence, not
a pass.

## Task 3.2A — RED contracts

- **Owner:** fresh test/eval worker.
- **Files:** new `tests/solar/test_sizing.py`,
  `tests/chat/tools/test_solar.py`,
  `tests/chat/test_solar_location_redaction.py`,
  `tests/evals/test_solar_sizing_harness.py`, and
  `evals/capability/estimate_solar_system.jsonl`.
- **RED:** prove the missing domain module/tool plus absent coordinate redaction.
- **Constraint:** tests use deterministic synthetic weather and never call NASA
  POWER or Anthropic.
- **Security:** inject an unexpected coordinate-bearing failure and prove the
  wrapper response and every stored audit field contain only the fixed safe
  message/redacted values.
- **Exit:** focused command fails for the expected missing capability only.

## Task 3.2B — GREEN implementation

- **Owner:** fresh Claude Code Sonnet 5 worker.
- **Files:** new `src/energia/solar/sizing.py`, new
  `src/energia/chat/tools/solar.py`, one side-effect import in
  `src/energia/chat/tools/__init__.py`, and the minimum coordinate scrubbing
  change in `src/energia/chat/audit.py`.
- **GREEN:** implement F1-F10 exactly; no catalog, payback, UI, prompt, cache,
  retry, dependency, or runner change.
- **Exit:** all Task 3.2 focused tests pass.

## Task 3.2C — verification and review

- Run focused tests, full pytest with a repository-external `--basetemp`, Ruff,
  strict Pyright, deterministic eval/harness tests, and live evals only if an
  existing API key is available.
- A fresh spec reviewer checks F1-F10 and protected paths.
- A separate fresh code-quality/security reviewer checks PV math, rounding,
  error honesty, coordinate handling, and dependency/scope discipline.
- Any finding returns to the Sonnet worker with a new RED test before a fix.

## Risks

- Interval-edge solar position silently distorts hourly transposition; midpoint
  tests are mandatory.
- A one-year historical model is not TMY; assumptions must say so.
- Continuous capacity is not purchaseable equipment; Task 3.4 owns catalog
  quantization.
- Coordinate leakage through local audit is a release blocker.
