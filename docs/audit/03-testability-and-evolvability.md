# Lane 3 — Testability & Evolvability
**Audit date:** 2026-05-14
**Branch audited:** `chore/sprint-1-audit`
**Lane:** 3 of 4 (sequential audit series — final lane)
**Predecessors:** `docs/audit/00-context.md` (Lane 0), `docs/audit/01-clean-code-and-craft.md` (Lane 1), `docs/audit/02-architecture-and-fitness.md` (Lane 2)

---

## 1. Methodology

**Lenses applied:** TDD seam analysis (where are the natural injection points for testing, and what
paths cannot currently be reached by any test?), EDD gate analysis (is the eval infrastructure
capable of expressing the HR-5 and Task 1.3 requirements?), test evolvability (will the current
fixture and conftest structure support the tests that Task 1.3 and beyond need to write?).

**Files read during this session:**
All 16 `.py` files under `tests/` — `test_audit.py`, `test_budget.py`, `test_graph.py`,
`test_runner.py`, `test_scorers.py`, `test_models.py`, `test_bill_schema.py`, `test_smoke.py`,
`test_migrations.py`, `conftest.py` (does not exist), `tests/chat/conftest.py` (the only conftest),
`tests/evals/test_run.py` (does not exist). Source files `evals/runner.py`, `evals/scorers.py`,
`evals/run.py`, `chat/memory.py`, `chat/audit.py`, `chat/budget.py`.

**Verified-absence methodology:** every claim that a test path is uncovered is backed by a grep of
`tests/` run during this session. "Zero matches" claims are falsification attempts, not
assumptions.

**Cross-references:** Lane 0's coverage map (file-level) is the starting point. Lane 1's Open
Questions 4 (silent early return) and the call-site-coupling concern are resolved here with direct
evidence. Lane 2's Open Questions 1 (CI eval-gate posture), 2 (synthetic ID safety), 3
(`tokens_in=0` testability angle), and 4 (vision beta headers) are resolved here. Lane 2's five
failure-mode fitness proposals for Task 1.3 are mapped to PLAN.md's seven test functions.

**What this lane does NOT produce:** new naming or function-length findings (Lane 1 owns those),
new architectural characteristic rankings or fitness-function audit rows (Lane 2 owns those),
cross-lane synthesis or final prioritization (Daniel post-audit). No code edits. No commits.

---

## 2. Inherited Open Questions — Resolved

The following questions were explicitly passed forward from Lanes 1 and 2. Each is resolved below
with direct evidence.

#### Q1 — `on_tool_end`/`on_tool_error` silent early return — dark path (from Lane 1)

**Question:** `audit.py:86-88` and `105-106` contain `if call_id is None: return` branches. Does
any test cover this path?

**Finding:** Grep of `tests/` for `call_id is None`, `_run_to_call_id`, and inspection of
`tests/chat/test_audit.py` (3 tests) confirm that no test covers this path. All three test
functions call `on_tool_start` successfully first, which always populates `_run_to_call_id` with a
valid entry. No test simulates a missing or failed `on_tool_start` followed by `on_tool_end` or
`on_tool_error`. The silent return at lines 86–88 and 105–106 is a permanently dark path in the
current suite.

**Resolution:** Addressed as TE-01. Two assertions can be added to `test_audit.py` — one for
`on_tool_end` and one for `on_tool_error` — by calling those methods directly without a prior
`on_tool_start`. Both should complete without exception (the silent return is correct behavior;
the gap is that no test verifies the correct behavior). Requires HR-4 approval before editing
`test_audit.py`.

---

#### Q2 — `run_example` synthetic IDs — does the eval runner wire `DuckDBAuditCallback`? (from Lanes 1 and 2)

**Question:** `runner.py:159` uses `"eval-runner"` and `"eval-{example.name}"` as synthetic user
and conversation IDs. If `DuckDBAuditCallback` were wired into the graph invocation, those IDs
would need to exist as FK rows in `users` and `conversations`. Do they?

**Finding:** `runner.py:159` calls `GRAPH.invoke({"messages": ..., "user_id": "eval-runner",
"conversation_id": f"eval-{example.name}", "tokens_used": 0})` with no `config` argument and no
`callbacks` list. Grep of `runner.py` for `config` and `callbacks` returns zero matches. The eval
runner does NOT wire `DuckDBAuditCallback`.

**Resolution:** FK violation risk is zero in the current design. The synthetic IDs are safe by
current implementation. The evolvability risk — future addition of callbacks to `run_example`
without also seeding the synthetic IDs — is addressed as TE-08 (an architectural assertion in
`tests/test_architecture.py` that guards against accidental coupling).

---

#### Q3 — CI eval-gate posture: `_check_api_key()` exits code 2 when key absent (from Lane 2)

**Question:** `run.py`'s `_check_api_key()` exits with code 2 when `ANTHROPIC_API_KEY` is absent.
Standard CI exit-code semantics treat 0 as pass, non-zero as fail. If CI interprets code 2 as
"failed," the gate can never pass in a keyless environment. If CI is configured to ignore code 2,
the gate is always-passing. Is a stub-response eval path feasible, or is "skip in CI" acceptable?

**Finding:** No CI configuration exists yet (the `.github/` directory is absent). The current unit
tests mock `_check_api_key` out entirely — they do not exercise the `sys.exit(2)` path. Code 2 is
currently neither passing nor failing in CI; it is neither because no CI exists.

**Resolution:** Three options are available for when CI is added; Daniel decides. They are
documented in Section 5 (Eval Design Assessment) and Section 7 (Open Questions for Synthesis).
The choice has no impact on Tasks 1.2–1.3 but must be made before CI is wired.

---

#### Q4 — `tokens_in=0` testability angle (from Lane 2)

**Question:** `streamlit_app.py:95` calls `update_token_totals(tokens_in=0, ...)` always writing
zero to `conversations.total_tokens_in`. Is this easy to test? Is fixing it Daniel's decision?

**Finding:** The bug is testable today: a test that calls `update_token_totals(tokens_in=5, ...)`
and then queries the `conversations` row would either pass (correct behavior) or fail
(demonstrating the bug). However, `chat/memory.py` has zero direct test coverage — there is no
`tests/chat/test_memory.py` in which to write that assertion. The forcing function is TE-05: once
`test_memory.py` is written as part of that finding's fix, the `update_token_totals` column-value
assertion will make the current call-site behavior visibly wrong. The design decision (whether to
carry `tokens_in`/`tokens_out` separately in `ChatState` or simplify the schema) remains Daniel's.

**Resolution:** Addressed as TE-05 and as Open Question 2 in Section 7.

---

#### Q5 — Vision parameters: does `claude-sonnet-4-6` need beta headers for base64 image input? (from Lane 2)

**Question:** Task 1.3 adds `parse_bill_image` which calls `anthropic.messages.create` directly
with base64-encoded image content. Does this require beta headers?

**Finding:** `claude-sonnet-4-6` handles base64 image inputs via the standard Anthropic messages
API without any beta headers. Beta headers are required for extended thinking, extended output
(128k+ tokens), and the Files API — not standard multimodal (vision) inputs. Vision capability
has been a stable, non-beta feature since Claude 3. The `parse_bill_image` implementation will use
the same `anthropic.messages.create` call pattern as text-only calls, with an additional
`image/base64` content block.

**Implication for nodes.py:** `parse_bill_image` calls the Anthropic SDK directly (not via the
LangChain `ChatAnthropic` singleton `_llm`). CC-01 and AF-01 are not must-fix blockers before
Task 1.3 on vision grounds. They remain should-fix for the reasons stated in Lanes 1 and 2.

**Resolution:** No blocking issue. Task 1.3 can proceed with standard SDK calls.

---

#### Q6 — `output_not_matches_pattern` scorer exists? (implicit from Lane 2 HR-5 refusal eval gap)

**Question:** Lane 2's fitness function table shows the HR-5 refusal path (chatbot refuses to
invent numbers when no tool is called) as an ❌ unasserted property. Is the current scorer
vocabulary capable of expressing this eval case?

**Finding:** `scorers.py` contains exactly three scorers: `tool_called`, `input_matches`, and
`output_matches_pattern`. `score_attempt` returns True for `expected_tool: null` when
`len(result.tool_calls) == 0` — the "no tool called" case is expressible. But there is no
`output_not_matches_pattern` scorer and no `expected_output_not_pattern` field on `EvalExample`.
The refusal eval requires asserting that the model's final text does NOT match a numeric pattern
(e.g., `\d+[\.,]\d{2}`). A positive `output_matches_pattern` cannot express negation.
`EvalExample` has no `expected_output_not_pattern: str | None = None` field.

**Resolution:** Addressed as TE-04.

---

## 3. Test Coverage Reality

Lane 0 produced a file-level coverage map. This section goes deeper: behavioral gaps within
modules that do have test files, and a risk-stratified assessment of modules with no test file.

### 3A. Modules with test files — dark paths within those files

**`tests/chat/test_audit.py` — 3 tests**

The three existing tests cover the happy path: `on_tool_start` succeeds, `on_tool_end` succeeds,
and PII is redacted before the DuckDB write. What is never triggered: the `if call_id is None:
return` branch at `audit.py:86-88` (inside `on_tool_end`) and `audit.py:105-106` (inside
`on_tool_error`). To reach these branches, `on_tool_end` or `on_tool_error` must be called with a
`run_id` that was never registered by a prior `on_tool_start`. This is a realistic failure mode —
LangGraph can emit an `on_tool_error` without a matching `on_tool_start` if the tool raises before
the callback chain fires `on_tool_start`. The behavior (silent return) is correct; the gap is that
no test asserts the callback is resilient to this sequence. See TE-01.

**`tests/chat/test_budget.py` — 2 tests**

`test_budget_callback_raises_at_threshold` covers the 100% halt path. `test_budget_callback_warns_at_50_percent` covers the 50% warning path. The 80% warning path (`TokenBudgetCallback._warned_80`) has no corresponding test. Grep of `test_budget.py` for `80`, `_warned_80`, and `warned_at` returns zero matches. The file ends at line 50. The 80% path is a hard rule (CLAUDE.md HR-7) and the behavior (`logger.warning(...)` fires exactly once between 50% and 100%) is non-trivial. See TE-02.

**`tests/evals/test_runner.py` — covers runner.py logic but not run.py**

`test_runner.py` correctly mocks `load_eval`, `_check_api_key`, and `run_example` separately,
testing the `pass@3`/`pass^3` gate math in isolation from live LLM calls. This separation of
concerns is correct and endorsed (see Section 8). However, `evals/run.py` (the CLI entrypoint and
orchestration layer) has no corresponding test file. `main()`, argparse, and the `sys.exit(0/1/2)`
paths are completely untested. See TE-06.

### 3B. Modules with no test file — risk assessment

**`chat/memory.py` — MEDIUM-HIGH risk**

Four public functions: `mint_user`, `mint_conversation`, `save_message`, `update_token_totals`.
These are the load-bearing persistence functions for every conversation — every chatbot turn calls
at least two of them. Grep of `tests/` for `mint_user`, `mint_conversation`, `save_message`, and
`update_token_totals` returns zero matches. `tests/chat/conftest.py` seeds users and conversations
with raw DuckDB `INSERT` statements — it does not call the memory functions. This means:

- The `mint_user` idempotency path (SELECT first, INSERT only if absent) is never executed by
  any test.
- The `RuntimeError` raises in `mint_user` and `mint_conversation` (when the DB returns no row
  after insert) are never triggered.
- `update_token_totals(tokens_in=0, ...)` always writes zero to `total_tokens_in`. No test asserts
  the column value, so this bug (AF-08) is invisible to the suite.

Until `test_memory.py` exists, any regression in these functions will be caught only at end-to-end
Streamlit runtime, not by the test suite. See TE-05.

**`evals/run.py` — MEDIUM risk**

The CLI entrypoint for the EDD gate. `main()` parses `--capability` and `--regression` flags, calls
`_run_capability` and/or `_run_regression`, and exits with code 0 (pass), 1 (fail), or 2 (no API
key). The hardcoded `× 3` run-count label (CC-11 from Lane 1) is also in this file. No test file
exists that imports from `energia.evals.run` or exercises `main()`. The three exit codes — which
are the gates that enforce EDD discipline — are never verified by the test suite. See TE-06.

**`ui/streamlit_app.py` — LOW risk (intentional deferral)**

Lane 0 noted Task 1.6 intentionally defers UI testing. `streamlit_app.py` is a flat procedural
script (CC-02 from Lane 1 noted this), which makes unit testing difficult without extracting
logic into testable functions. The risk is low for the current sprint because the file is thin
glue. The risk grows as the UI accumulates more logic before Task 1.6 lands. No finding is raised
here; it is tracked as scope for Task 1.6.

**`chat/prompts.py` — HIGH conceptual risk, LOW file risk**

`chat/prompts.py` is a 13-line string constant file (Protected Path). The file itself is trivial.
The risk is conceptual: HR-5 requires the system prompt to contain the PT-BR no-invented-numbers
instruction `"Você nunca inventa números..."`. Lane 2's fitness function table shows this as an ❌
unasserted property — no test confirms the string is present. If `prompts.py` is edited (which
requires Daniel's approval per Protected Paths), the missing assertion means a regression would
be invisible to the test suite. Lane 2 flagged this as a fitness function gap (AF-04 territory).
It is not re-raised as a new finding here — Lane 2 already documented it. The testability angle is
that a `test_smoke.py`-style assertion (`assert "nunca inventa" in SYSTEM_PROMPT`) costs one line
and closes the gap without touching the protected file.

---

## 4. Findings

Finding schema: **Location**, **Lens**, **Evidence**, **Smell**, **Why it matters now**,
**Recommended fix**, **Cost**, **Priority**. Prefix `TE-`. Cost scale: XS < S < M < L.

---

### TE-01: `on_tool_end`/`on_tool_error` silent early return — permanently dark path

**Location:** `src/energia/chat/audit.py:86-88` and `audit.py:105-106`; `tests/chat/test_audit.py`

**Lens:** TDD seam analysis — unreachable production path in current test suite

**Evidence:**
```python
# audit.py:86-88 — on_tool_end
def on_tool_end(self, output, *, run_id, **kwargs):
    call_id = self._run_to_call_id.get(str(run_id))
    if call_id is None:
        return          # <-- never triggered by any test

# audit.py:105-106 — on_tool_error
def on_tool_error(self, error, *, run_id, **kwargs):
    call_id = self._run_to_call_id.get(str(run_id))
    if call_id is None:
        return          # <-- never triggered by any test
```
Grep of `tests/` for `call_id is None` and `_run_to_call_id` → 0 matches. All three existing
tests always call `on_tool_start` before `on_tool_end` or `on_tool_error`.

**Smell:** The behavior (silent return) is correct. The gap is that no test asserts the callback
is resilient to a call sequence where `on_tool_start` never fired for a given `run_id`. LangGraph
can produce this sequence when a tool raises before the callback chain completes `on_tool_start`.

**Why it matters now:** `DuckDBAuditCallback` is the LGPD-compliant LangSmith substitute. If the
silent return silently swallows a tool error that should have been logged (e.g., a PII leak in an
error payload), the observability guarantee fails without any test catching it. Task 1.3 adds a
bill-parsing tool that processes image bytes and CPF fields — the risk of an untracked error path
rises with each new tool.

**Recommended fix:** Add two test functions to `tests/chat/test_audit.py`: one calling
`on_tool_end` directly with a `run_id` that was never registered by `on_tool_start` (asserting
the call does not raise and does not write to DuckDB), and one doing the same for `on_tool_error`.
This requires HR-4 approval before editing `test_audit.py`.

**Cost:** XS

**Priority:** should-fix — before Task 1.3 adds a new tool

---

### TE-02: 80% budget warning threshold — no test

**Location:** `src/energia/chat/budget.py` (80% warning logic); `tests/chat/test_budget.py`

**Lens:** TDD seam analysis — hard rule (HR-7) with an unexercised enforcement branch

**Evidence:**
```python
# budget.py — the three threshold branches
# 100%: raises TokenBudgetExceededError  ← test_budget_callback_raises_at_threshold ✅
# 80%:  logger.warning(...)              ← NO TEST ❌
# 50%:  logger.warning(...)              ← test_budget_callback_warns_at_50_percent ✅
```
`test_budget.py` ends at line 50. Grep of `test_budget.py` for `80`, `_warned_80`, and `warned_at`
→ 0 matches.

**Smell:** HR-7 mandates warnings at 50% and 80%. The 50% test exists. The 80% test does not. The
two warning paths are not equivalent — one fires at 80% (between two already-tested thresholds)
and the internal `_warned_80` flag governs "fire exactly once." The boundary behavior and the
idempotency flag are both untested.

**Why it matters now:** The 80% warning is part of the documented operator contract (CLAUDE.md
HR-7). A regression that silently drops the 80% warning would not be caught before it reached a
session where Daniel needs it.

**Recommended fix:** Add `test_budget_callback_warns_at_80_percent` to `tests/chat/test_budget.py`
that drives token count to 80% of `session_token_budget` and asserts a `WARNING` log is emitted
(using `caplog`). Also assert the warning does not fire a second time when called again at 81%.
This requires HR-4 approval before editing `test_budget.py`.

**Cost:** XS

**Priority:** should-fix

---

### TE-03: `tmp_db` fixture scoped to `tests/chat/conftest.py` — Task 1.3 will fail at collection time

**Location:** `tests/chat/conftest.py` (the only conftest in the project); planned
`tests/bill/test_parser.py` (Task 1.3)

**Lens:** Test evolvability — fixture scope gap blocks a future task

**Evidence:**
```python
# tests/chat/conftest.py — fixture defined here only
@pytest.fixture
def tmp_db(tmp_path):
    ...
    return conn
```
`tests/conftest.py` does not exist. pytest conftest scoping rules: a conftest at
`tests/chat/conftest.py` provides fixtures only to tests in `tests/chat/` and its subdirectories.
Task 1.3 creates `tests/bill/test_parser.py`. All 7 planned test functions in that file have the
signature `(tmp_db, mocker)`. pytest will fail at collection time with:
`fixture 'tmp_db' not found`.

**Smell:** The fixture is general-purpose (creates an isolated DuckDB with migrations applied) and
is already the right abstraction for all database-touching tests in the project. Its current
placement in `tests/chat/conftest.py` was correct when only chat tests existed. It is now a
structural bottleneck.

**Why it matters now:** This is a hard blocker for Task 1.3. If `tests/bill/test_parser.py` is
written before the fixture is promoted, every test fails at collection — not at assertion. The
failure is invisible until Task 1.3's test run, at which point confusion about pytest scoping will
cost time to diagnose.

**Recommended fix:** Create `tests/conftest.py` and move `tmp_db` into it. Remove `tmp_db` from
`tests/chat/conftest.py`. `conftest.py` is not a `test_*.py` file — HR-4 does not apply. The
change requires no HR-4 approval. `tests/chat/conftest.py` may retain other chat-specific
fixtures if any exist. This fix must be completed before Task 1.3 begins.

**Cost:** XS

**Priority:** must-fix — before Task 1.3 begins (hard blocker)

---

### TE-04: No `output_not_matches_pattern` scorer — HR-5 refusal eval case is inexpressible

**Location:** `src/energia/evals/scorers.py`; `src/energia/evals/runner.py` (`EvalExample` model
and `score_attempt`)

**Lens:** EDD gate analysis — scorer vocabulary gap prevents expressing a required eval case

**Evidence:**
```python
# scorers.py — three scorers only
def tool_called(result, expected_tool): ...
def input_matches(result, expected_input_match): ...
def output_matches_pattern(result, expected_output_pattern): ...

# runner.py — EvalExample schema
class EvalExample(BaseModel):
    name: str
    input_messages: list[MessageInput]
    expected_tool: str | None = None
    expected_input_match: dict[str, Any] | None = None
    expected_output_pattern: str | None = None
    # no expected_output_not_pattern field

# score_attempt — short-circuit flow
def score_attempt(result, example):
    if not tool_called(result, example.expected_tool): return False
    if example.expected_input_match is not None:
        if not input_matches(result, example.expected_input_match): return False
    if example.expected_output_pattern is not None:
        if not output_matches_pattern(result, example.expected_output_pattern): return False
    return True
```

**Smell:** The HR-5 refusal case requires an eval example that asserts: (a) no tool was called,
AND (b) the model's final response does not contain a numeric claim (e.g., `\d+[\.,]\d{2}`). Case
(a) is expressible via `expected_tool: null`. Case (b) requires asserting that a pattern does NOT
appear — which is the logical negation of `output_matches_pattern`. There is no way to express
this negation with the current scorer vocabulary or `EvalExample` schema.

**Why it matters now:** Task 1.3 must ship an eval file for `parse_bill_image`. The HR-5 refusal
case — "user sends an image that is not a bill; model must not invent any numbers" — is one of
the most important capability tests for the prototype's trust model. Without this scorer, the eval
suite cannot certify the refusal behavior before shipping.

**Recommended fix:**
1. Add `output_not_matches_pattern(result: RunResult, pattern: str) -> bool` to `scorers.py`
   (returns True when no tool call's output and no final assistant message match the pattern).
2. Add `expected_output_not_pattern: str | None = None` to `EvalExample` in `runner.py`.
3. Wire it in `score_attempt` after the existing pattern check.
4. Add positive and negative test cases in `test_scorers.py`.

All of the above are source files and a new test — not edits to existing test files. HR-4 does
not apply. `test_scorers.py` is an existing file; if the new scorer tests are added there, HR-4
approval is required. Alternatively, create `tests/evals/test_scorers_extended.py` for the new
cases only (no HR-4 approval needed).

**Cost:** S

**Priority:** should-fix — needed before Task 1.3 eval file is written

---

### TE-05: `chat/memory.py` — zero direct test coverage across four load-bearing functions

**Location:** `src/energia/chat/memory.py`; no corresponding test file exists

**Lens:** TDD seam analysis — load-bearing persistence layer with no test seam

**Evidence:**
```python
# memory.py — four public functions, none tested
def mint_user(conn, user_id: str) -> None: ...
def mint_conversation(conn, conversation_id: str, user_id: str) -> None: ...
def save_message(conn, ...) -> None: ...
def update_token_totals(conn, conversation_id: str, tokens_in: int, tokens_out: int) -> None: ...
```
Grep of `tests/` for `mint_user`, `mint_conversation`, `save_message`, `update_token_totals` →
0 matches in all four cases. `tests/chat/conftest.py` seeds the database with raw SQL `INSERT`
statements instead of calling `memory.py` functions — deliberately bypassing the layer under test.

**Smell:** The conftest bypass means every test that uses `tmp_db` implicitly trusts that
`mint_user` and `mint_conversation` behave identically to the raw INSERT. If they diverge (e.g.,
`mint_user` adds a `created_at` timestamp the raw INSERT omits), tests pass but production breaks.
The `mint_user` idempotency logic (SELECT → INSERT only if absent) is the most likely divergence
point. The `RuntimeError` raise paths are the most likely latent bugs.

The `tokens_in=0` call-site bug (AF-08 from Lane 2) is invisible precisely because no test asserts
column values after `update_token_totals`. Writing `test_memory.py` and adding a column-value
assertion will surface the bug as a failing test — which is the correct forcing function for
Daniel's design decision on the schema (Open Question 2 in Section 7).

**Why it matters now:** `chat/memory.py` is called on every conversation turn. Task 1.3 adds a
new tool that will trigger `save_message` and `update_token_totals` with non-trivial token counts
for the first time. If `mint_conversation` silently fails on duplicate IDs (the eval runner uses
the same conversation ID format across runs), Task 1.3's eval suite will produce FK errors against
the eval DuckDB instance.

**Recommended fix:** Create `tests/chat/test_memory.py` (new file — no HR-4 approval required).
Cover:
- `mint_user` happy path (row is inserted, re-calling with same ID is idempotent, no exception)
- `mint_user` error path (mock the DB to return no rows after insert; assert `RuntimeError`)
- `mint_conversation` happy path and error path
- `save_message` happy path (assert the row exists with correct content after the call)
- `update_token_totals` column-value assertion — assert `total_tokens_in` equals the value passed
  (this test will fail until AF-08 is fixed, which is the intended forcing function)

**Cost:** M

**Priority:** should-fix — before Task 1.3 begins, to prevent silent eval-runner FK failures

---

### TE-06: `evals/run.py` CLI entrypoint is completely untested — exit codes and gate integrity unverified

**Location:** `src/energia/evals/run.py`; no corresponding test file exists

**Lens:** EDD gate analysis — the CLI that enforces the EDD gate has no test coverage

**Evidence:**
```python
# run.py — main() orchestrates the eval gate
def main() -> None:
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--capability", ...)
    parser.add_argument("--regression", ...)
    args = parser.parse_args()
    ...
    if not _check_api_key():
        sys.exit(2)          # ← exit code 2: no API key — untested
    ...
    # exit(0) if all pass, exit(1) if any fail — both untested
```
No test file exists under `tests/evals/` for `run.py`. Grep of `tests/` for `evals.run`,
`evals/run`, and `sys.exit` → 0 matches related to `run.py`. The hardcoded `× 3` run-count
label (CC-11 from Lane 1 — at approximately `run.py:32` and `run.py:66`) is also untested.

**Smell:** The `evals/run.py` entrypoint is the outermost enforcement layer of EDD discipline for
this project. Exit codes 0, 1, and 2 carry distinct semantics: 0 means the gate passed and
shipping is allowed; 1 means the gate failed and shipping is blocked; 2 means the key was absent
and the gate was skipped. If argument parsing is broken, if `_run_capability` and `_run_regression`
are called in the wrong order, or if a bug in the control flow exits 0 when it should exit 1, no
test catches it. The gate integrity is entirely convention-dependent.

**Why it matters now:** Every capability eval written for Task 1.3 (`parse_bill_image`) will be
run through `run.py`. If `run.py` has a latent bug in its exit-code logic, the gate can silently
pass a failing eval suite. This is the anti-cheat concern applied at the eval-runner layer.

**Recommended fix:** Create `tests/evals/test_run.py` (new file — no HR-4 approval required).
Use `pytest`'s `monkeypatch` and `mock` to patch `_run_capability`, `_run_regression`, and
`_check_api_key`. Test the following paths:
- `--capability` only: calls `_run_capability`, exits 0 on pass, 1 on fail
- `--regression` only: calls `_run_regression`, exits 0 on pass, 1 on fail
- both flags: calls both, exits 1 if either fails
- no API key: exits 2 without calling capability or regression
- `× 3` label assertion: verify the run-count string in output matches the hardcoded value

**Cost:** M

**Priority:** should-fix — before Task 1.3 eval file is written

---

### TE-07: Task 1.3 spec is missing one test function from Lane 2's five failure-mode proposals

**Location:** `PLAN.md` (Task 1.3 spec); planned `tests/bill/test_parser.py`

**Lens:** Test evolvability — plan-to-test gap before work begins

**Evidence:**

Lane 2 proposed five failure modes for `parse_bill_image`:
1. Anthropic 5xx → one retry
2. Pydantic validation failure → `tool_calls.error` column non-null in DuckDB
3. Confidence < 0.85 → `needs_user_confirmation=True`
4. Duplicate hash → `ON CONFLICT DO NOTHING` (unique constraint exercised at SQL level)
5. Image too large / format unsupported → typed exception, not opaque HTTP error

PLAN.md's Task 1.3 specifies seven test functions. Cross-referencing against the five failure
modes:

- Failure mode 1 (5xx retry): covered by test 6 (`test_parse_bill_handles_anthropic_5xx_with_one_retry`)
- Failure mode 2 (validation → `tool_calls.error` non-null): tests 3 and 5 cover parser behavior
  and "no store on error," but neither asserts the `tool_calls.error` DB column. That assertion
  belongs in `tests/chat/tools/test_bill.py` — the tool wrapper test — which is not in the
  current Task 1.3 plan.
- Failure mode 3 (confidence < 0.85 → `needs_confirmation`): covered by test 4
- Failure mode 4 (duplicate hash → SQL UNIQUE constraint): test 1 covers app-level idempotency
  (return existing record). The SQL-level `ON CONFLICT DO NOTHING` clause is not exercised.
  Belongs in Task 1.4's `tests/chat/test_bill_store.py`.
- Failure mode 5 (image too large / format unsupported → typed exception): NOT present in any of
  the seven planned tests.

**Smell:** Failure mode 5 is the one gap in `test_parser.py`'s own scope. It is a realistic
input error (user photographs a gas bill in TIFF format, or attaches a 20 MB raw photo). Without
a typed exception, the Anthropic SDK's HTTP error propagates as an unhandled exception to the
Streamlit UI, producing a raw stack trace visible to the user — an LGPD concern if it contains
request metadata.

**Why it matters now:** The spec must be updated before Task 1.3 work begins, not during. Adding
a test after the parser is written reverses TDD discipline.

**Recommended fix:**
1. Add `test_parse_bill_rejects_invalid_format(tmp_db, mocker)` to Task 1.3's spec (one
   additional test function). This is a PLAN.md edit — no HR-4 applies; PLAN.md is not a test file.
2. Create `tests/chat/tools/test_bill.py` as a follow-on task to cover the audit-trail assertion
   for failure mode 2 (`tool_calls.error` non-null).
Both are new files — no HR-4 approval required.

**Cost:** XS for the spec addition; M for the follow-on `test_bill.py` (separate task)

**Priority:** must-fix before Task 1.3 begins (spec gap); the follow-on `test_bill.py` is
should-fix in a subsequent task

---

### TE-08: Eval runner uses synthetic IDs with no guard against future callback wiring

**Location:** `src/energia/evals/runner.py:159`; planned `tests/test_architecture.py` (from AF-03)

**Lens:** Test evolvability — safe today, unguarded against a realistic future change

**Evidence:**
```python
# runner.py:159 — no config, no callbacks
state: Any = GRAPH.invoke(
    {
        "messages": ...,
        "user_id": "eval-runner",
        "conversation_id": f"eval-{example.name}",
        "tokens_used": 0,
    }
)
# grep of runner.py for 'config' or 'callbacks' → 0 matches
```
The synthetic IDs `"eval-runner"` and `"eval-{example.name}"` are never inserted into `users` or
`conversations` by `mint_user` / `mint_conversation`. This is safe today because no
`DuckDBAuditCallback` is wired into the `run_example` invocation.

**Smell:** If a future developer adds `DuckDBAuditCallback` to `run_example` — a natural impulse
when improving eval observability — the FK constraints on `tool_calls` will raise immediately
because the synthetic IDs have no parent rows. Nothing in the current codebase warns against this.
No comment, no architectural test, no type annotation prevents it.

**Why it matters now:** This is a low-probability but high-diagnosis-cost failure: FK violations
in the eval runner would appear as database errors during eval runs, not as test failures, and the
connection to the synthetic-ID design decision would not be obvious to a new contributor.

**Recommended fix:** Add `test_run_example_does_not_wire_audit_callback` to
`tests/test_architecture.py` (the same file as AF-03's proposed test). Use `inspect.getsource`
or `ast.parse` to assert that `run_example` does not reference `DuckDBAuditCallback` by name.
This is a new file addition — no HR-4 approval required. The test is cheap and self-documenting:
its name explains the design constraint to future contributors.

**Cost:** XS

**Priority:** nice-to-have — no immediate risk; guards against a specific future mistake

---

## 5. Eval Design Assessment

### Scorer vocabulary

The current three scorers (`tool_called`, `input_matches`, `output_matches_pattern`) are
sufficient for the existing eval suite and for the positive half of Task 1.3's eval cases. The
gap is the refusal case: asserting that the model did NOT produce a numeric claim when no tool was
called. `tool_called(result, None)` returns True when `len(result.tool_calls) == 0`, so the
"no tool" condition is expressible. But there is no way to further constrain the model's output
text to exclude numeric patterns. TE-04 addresses this with `output_not_matches_pattern`.

### `score_attempt` short-circuit order

The current order (tool_called → input_matches → output_matches_pattern) is logically correct.
If no tool was called when one was expected, there is nothing to match against. Short-circuiting
early avoids false positives from partial matches. The `pass@3` / `pass^3` gate math downstream
of `score_attempt` is correct and well unit-tested in `test_runner.py`.

### `pass@3` and `pass^3` math

Both gate math implementations are verified by the test suite (`tests/evals/test_runner.py`).
`run_capability` and `run_regression` are tested with mock `run_example` calls that return
controlled pass/fail sequences. The mathematical properties (exactly 3 runs, threshold 0.90 for
capability, 1.00 for regression) are directly asserted. No gap here.

### CI gate posture

The `_check_api_key()` guard in `run.py` exits code 2 when `ANTHROPIC_API_KEY` is absent. The
unit tests mock this function out entirely — the `sys.exit(2)` path is not exercised by any test
(TE-06). No CI configuration exists yet. When CI is added, Daniel must choose one of three
postures:

**Option A — API key in CI secrets.** Most teams choose this. The key is stored as an encrypted
GitHub Actions secret; CI passes it as an environment variable to the eval run step. The gate
runs for real on every PR. For a single-user prototype this is low-overhead and high-integrity.
Exit code 2 becomes a failure indicator (misconfiguration) rather than an accepted skip.

**Option B — Stub-response eval path.** Add a `--mock-llm` flag to `run.py` that substitutes
deterministic stub responses for real Anthropic API calls. Evals run without an API key; the gate
confirms eval logic and score_attempt math. The trade-off: stub responses test the plumbing, not
the model. A regression in prompt quality would not be caught by CI. Feasibility: approximately
M effort.

**Option C — Permanent "skip in CI" posture.** CI is configured to treat exit code 2 as a
neutral result (equivalent to `pytest.mark.skip`). Evals are run manually by Daniel before
releasing. Acceptable for a single-user prototype. Risk: the gate is only as reliable as Daniel's
discipline about running evals manually. For a one-person team, this is the lowest-friction
choice.

All three options are valid. The choice has no impact on Tasks 1.2–1.3 and must be made before
CI is wired. See Section 7, Open Question 1.

### `EvalExample` schema gap

`EvalExample` has no `expected_output_not_pattern` field. This is addressed as TE-04 above and is
the only structural gap in the schema relative to the requirements of Task 1.3's eval file.

---

## 6. Test Evolvability for Task 1.3

### 6A. Fixture infrastructure

Task 1.3 creates `tests/bill/test_parser.py` with 7 test functions, all using `tmp_db`. The
`tmp_db` fixture currently lives in `tests/chat/conftest.py`. pytest conftest scoping rules mean
the fixture is invisible to `tests/bill/`. The consequence is a hard collection-time failure —
not a runtime test failure — which can be confusing to diagnose if the developer writing Task 1.3
is not familiar with pytest's conftest scoping semantics.

The fix (TE-03) is to create `tests/conftest.py` and move `tmp_db` there. This is a two-step
change: add the fixture to `tests/conftest.py`, remove it from `tests/chat/conftest.py`. The
`tests/chat/conftest.py` file may remain for chat-specific fixtures. Since `conftest.py` is not a
`test_*.py` file, HR-4 does not apply and no approval is needed. This fix must land before Task
1.3 begins.

### 6B. Lane 2 failure modes mapped to PLAN.md seven tests

| Failure mode (Lane 2) | PLAN.md test (Task 1.3) | Status |
|---|---|---|
| Anthropic 5xx → one retry | test 6: `test_parse_bill_handles_anthropic_5xx_with_one_retry` | Covered |
| Pydantic validation failure → `tool_calls.error` non-null | tests 3 + 5: parser behavior covered, DB column not asserted | Partial — `tool_calls.error` assertion belongs in future `tests/chat/tools/test_bill.py` |
| Confidence < 0.85 → `needs_user_confirmation=True` | test 4: `test_parse_bill_sets_needs_confirmation_when_low_confidence` | Covered |
| Duplicate hash → DB `UNIQUE` constraint exercised | test 1: `test_parse_bill_returns_existing_when_hash_matches` | Partial — app-level idempotency covered; SQL `ON CONFLICT` path belongs in Task 1.4's `test_bill_store.py` |
| Image too large / format unsupported → typed exception | Not present in any of the seven tests | Gap — must add (TE-07) |

The two partial coverages and the one gap do not block Task 1.3 from shipping, but they do mean
Task 1.3's test suite, as currently specced, provides approximately 5 of 7 meaningful behavioral
guarantees for the parser. The gaps are assigned to follow-on tasks (Task 1.4 for the `UNIQUE`
constraint path; a new task for `test_bill.py`). The missing "invalid format" test (failure mode
5) must be added to the Task 1.3 spec before work begins, per TE-07.

---

## 7. Open Questions for Synthesis

These questions have no further lane to forward to. They go directly to Daniel.

### OQ-1 — CI eval-gate posture

**Options:**
- **A (API key in CI secrets):** Key stored as GitHub Actions secret; evals run for real on
  every PR; exit code 2 becomes a configuration error. Highest integrity. Low overhead for a
  single-user team.
- **B (stub-response path):** Add `--mock-llm` flag; CI runs without key; tests eval plumbing but
  not model quality. Approximately M effort to implement.
- **C (permanent skip):** CI treats exit code 2 as neutral; Daniel runs evals manually before
  releases. Lowest friction. Relies on personal discipline.

**What Daniel needs to decide:** before CI is wired — which option matches the team's release
discipline for a single-user prototype?

### OQ-2 — `tokens_in=0` schema decision (AF-08)

`streamlit_app.py:95` calls `update_token_totals(tokens_in=0, ...)` unconditionally, always
writing zero to `conversations.total_tokens_in`. The column is thus permanently wrong for input
tokens. Two options:

- **Fix the call site:** modify `ChatState` to carry `tokens_in` and `tokens_out` separately
  (both populated from the Anthropic response), then pass them to `update_token_totals`. Correct
  but requires a `ChatState` schema change.
- **Simplify the schema:** drop `total_tokens_in` from `conversations` via a new forward
  migration (HR-3 compliant). If input token tracking is not needed for v1, this is the simpler
  path.

**Forcing function:** TE-05's `test_memory.py` includes an assertion that `total_tokens_in`
equals the value passed to `update_token_totals`. When that test is written, the current call-site
bug becomes a red test. Use the failing test as the moment to make the design decision —
before Task 1.3 ships (which will be the first operation producing non-trivial input token counts).

### OQ-3 — `tmp_db` promotion timing

`tests/conftest.py` must be created and `tmp_db` promoted before Task 1.3 can collect. Two
scheduling options:

- **As part of Task 1.2 cleanup:** fold TE-03's fix into the Task 1.2 close-out. Minimal
  overhead; fixes the gap while the test infrastructure is already being worked.
- **As a dedicated pre-Task-1.3 step:** create a tiny `chore/` commit specifically for the
  conftest promotion, explicitly gating Task 1.3. More visible in the git log.

Either option is correct. The question is which aligns better with Daniel's sprint workflow.

### OQ-4 — `needs_user_confirmation` placement and test structure for Task 1.3

Lane 1 (CC-03) flagged two design options for this field:

- **Option A (`ParseResult` wrapper):** `needs_user_confirmation` is a field on a wrapper
  dataclass, derived after `Bill` validation. `test_parser.py` test 4 asserts
  `result.needs_confirmation is True`.
- **Option B (model validator on `Bill`):** `needs_user_confirmation` is derived from `confidence`
  inside `Bill` itself. `test_parser.py` test 4 asserts `bill.needs_user_confirmation is True`.

The assertion in test 4 changes depending on which design is chosen. Writing test 4 before the
design is settled will require revising it when the design lands — which triggers HR-4. The
cleaner path is to make this decision explicitly before Task 1.3 writing begins, so test 4 is
written once against the final design.

---

## 8. Non-Findings

The following items were inspected and found to be solid. They are documented here to prevent
future audit passes from re-examining them.

**`evals/scorers.py` — pure functions, no mocking required.** All three scorers are pure
functions (no side effects, no I/O, no global state). Tests in `test_scorers.py` cover positive
and negative cases for each scorer. The scorer logic is correct and complete for the current eval
suite. The only gap is the absence of `output_not_matches_pattern`, which is a missing capability
(TE-04), not a quality issue with existing scorers.

**`tests/evals/test_runner.py` — correct mock separation.** `load_eval`, `_check_api_key`, and
`run_example` are mocked independently. This is the correct pattern: it isolates gate math from
live LLM invocation, allowing the mathematical properties of the pass@3 / pass^3 protocol to be
tested without an API key. The test does not accidentally test the mock instead of the real
scoring logic.

**`tests/chat/conftest.py` — fixture design is sound.** The `tmp_db` fixture uses `tmp_path`
for DuckDB file isolation (no contamination of `data/energia.duckdb`), applies migrations via the
production `migrate()` function (not raw SQL DDL), and seeds data with raw INSERT (correct — the
fixture is testing infrastructure, not the memory functions). The only issue is scope (TE-03), not
quality.

**`tests/chat/test_graph.py` — patch target is correct.** `mocker.patch("energia.chat.nodes._llm_with_tools")`
patches the attribute on the module object — the object the module actually uses at call time —
rather than patching the import reference. This is the correct Python mocking pattern. It does not
accidentally leave the real `ChatAnthropic` instance in place during the test.

**`tests/models/test_models.py` — comprehensive validation coverage.** 9 tests cover all
validation paths on `Bill` and `BillComposition`: period format constraints (YYYY-MM), confidence
bounds (0.0–1.0), decimal type enforcement, and required field presence. No coverage gaps exist
in the model layer for current fields.

**`tests/db/test_migrations.py` — best-tested architectural property in the codebase.** 4 tests:
create tables, idempotent re-run, hash-match acceptance, tamper-reject (raises
`MigrationIntegrityError`). Lane 2 confirmed this; Lane 3 endorses it. The migration integrity
guarantee is solid and executable.
