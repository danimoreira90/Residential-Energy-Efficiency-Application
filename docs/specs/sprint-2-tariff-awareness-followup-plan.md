> **For agentic workers:** REQUIRED: Use subagent-driven-development for every task.
> Each task = one fresh subagent. Spec compliance review → code quality review → ✅ done.
> No task is "done" without: passing verification command, reviewer sign-off.

# Plan: Sprint 2 tariff-awareness follow-up

**Spec:** `docs/specs/sprint-2-tariff-awareness-followup.md`  
**Status:** Ready to implement

## EDD preamble

Create the capability/regression JSONL fixtures before production code. The
deterministic RED tests prove the absent functions/tools; the live eval gate is
run only with an already-configured API key.

## Task 2.2 — Bandeira status and history

- **Files:** new `src/energia/tariff/bandeira.py`, local snapshot JSON, new
  `src/energia/chat/tools/bandeira.py`, registry import, and new focused tests.
- **RED:** test exact decimal current/history behavior, bounded history,
  registered schemas, ToolMessage payload, and out-of-snapshot honesty branch.
- **GREEN:** minimum pure snapshot reader and wrappers; no network or bill access.
- **Verify:** targeted tests, then inspect the changed paths and logs for PII.
- **Exit:** F1–F3 pass with source provenance in the snapshot.

## Task 2.4 — Tarifa Branca simulation

- **Files:** minimal extension to the existing Enel snapshot model/data, new
  `src/energia/tariff/branca.py`, new `src/energia/chat/tools/branca.py`,
  registry import, and new focused tests.
- **RED:** test exact Decimal totals, no default profile, invalid inputs,
  Enel-only scope, and assumptions statement.
- **GREEN:** sum user buckets and multiply against snapshot rates only.
- **Verify:** targeted tests and pyright on the touched modules.
- **Exit:** F4–F6 pass without taxes or estimated bill totals.

## Task 2.5 — deterministic eval coverage

- **Files:** new append-only capability and regression JSONL fixtures plus
  new deterministic harness tests; no prompt edit unless Daniel explicitly
  authorizes it after a focused blocker report.
- **RED:** new harness coverage fails until the new tools are registered and
  fixture contracts are complete.
- **GREEN:** add fixtures and the smallest harness assertions that validate
  all new tool names and scorer contracts.
- **Verify:** run the deterministic gate three times and run the live CLI only
  if the existing credentials are available.
- **Exit:** F7 and the EDD gate evidence are recorded.

## Review gates

After each task, use a fresh reviewer for spec compliance and a separate fresh
reviewer for code quality/security. Reviewers must inspect the real diff and
report any protected-path touch or numeric provenance gap.
