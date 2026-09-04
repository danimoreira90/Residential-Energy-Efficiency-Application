> **For agentic workers:** REQUIRED: Use subagent-driven-development for every task.
> Each task = one fresh subagent. Spec compliance review → code quality review → ✅ done.
> No task is "done" without: passing verification command, reviewer sign-off.

# Plan: Sprint 3 Task 3.1 — NASA POWER hourly weather client

**Spec:** `docs/specs/sprint-3-nasa-power-weather.md`  
**Status:** Ready to implement

## Task 3.1 — fetch and normalize hourly weather

- **Files:** create `tests/solar/__init__.py`, `tests/solar/test_irradiance.py`,
  and `src/energia/solar/irradiance.py` only.
- **RED:** create the new focused test file before production code. Its first
  test imports the missing module inside the test body and asserts the public
  function exists, so the observed failure is caused by the absent module.
  Add deterministic mocked-NASA tests for request parameters, normalized UTC
  data, invalid input without a request, and safe failures.
- **GREEN:** implement only `get_hourly_weather` and its domain exception.
  Use `requests.get(..., timeout=30)`, fixed endpoint/query parameters from
  F1, strict payload extraction, a complete pandas UTC-indexed calendar-year
  frame, and fully sanitized upstream failures. The test changes below are
  explicitly authorized by Daniel on 2026-08-30 because this is a new,
  uncommitted task-owned test file. Do not add a cache, tool wrapper, model
  catalog, or sizing/payback code.
- **Verification:** run the new test file with `-p no:cacheprovider`, then
  `ruff check src tests` and strict Pyright. Run no live API call: mocked
  responses are the required deterministic gate for this client slice.
- **Exit criteria:** F1–F5 pass; no location data reaches logs/errors, no
  protected existing test/eval/prompt path is edited, and both reviewers
  approve the actual diff.
- **Dependencies:** installed `requests`, `pandas`, and `responses` only.
- **Risk:** medium — incorrect time standards silently corrupt later solar
  position calculations, so exact UTC query assertions are mandatory.

## Review gates

1. A fresh spec-compliance reviewer checks F1–F5 against the actual diff and
   RED/GREEN evidence.
2. A separate fresh code-quality/security reviewer checks HTTP handling,
   PII/location exposure, typing, and protected paths.
