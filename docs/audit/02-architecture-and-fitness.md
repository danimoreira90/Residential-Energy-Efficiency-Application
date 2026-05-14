# Lane 2 — Architecture & Fitness Functions
**Audit date:** 2026-05-14
**Branch audited:** `chore/sprint-1-audit`
**Lane:** 2 of 4 (sequential audit series)
**Predecessors:** `docs/audit/00-context.md` (Lane 0), `docs/audit/01-clean-code-and-craft.md` (Lane 1)

---

## 1. Methodology

**Lenses applied:** Neal Ford's architectural characteristics ("-ilities"), fitness functions as
executable architectural assertions, module-level coupling (afferent/efferent), and evolvability
under Task 1.3 pressure.

**What this lane does NOT produce:** naming, SRP, or function-length findings (Lane 1 owns those);
test-quality or eval-design recommendations beyond identifying fitness-function gaps (Lane 3 owns
those); synthesis or cross-lane prioritization; no code edits.

**Files read or grepped in this session** (Lane 0 and Lane 1 were the map; this lane verified
specific claims):
- `src/energia/db.py` — hash-check implementation
- `src/energia/models.py` — inner-ring purity verification (grep for framework imports)
- `src/energia/evals/runner.py` — pass@3 / pass^3 gate implementations
- `src/energia/chat/audit.py` — `_scrub_pii` regex scope
- `src/energia/chat/graph.py` — return type annotation on `build_graph()`
- `src/energia/ui/streamlit_app.py` — `update_token_totals` call site
- `tests/db/test_migrations.py` — SHA-256 fitness check
- `tests/db/test_bill_schema.py` — schema column tests
- `tests/chat/test_audit.py` — PII redaction test coverage
- `tests/chat/test_budget.py` — HR-7 threshold tests
- `tests/chat/test_graph.py` — mocking pattern and call sites
- `tests/test_smoke.py` — budget constant smoke check
- `pyproject.toml` — runtime dependency surface
- `docs/adr/ADR-001`, `ADR-002`, `ADR-003` — architectural decisions and their claims
- `docs/tech-debt.md` — TD-001 through TD-007

**Verified-absence methodology:** every "no fitness function exists for X" claim is backed by a
grep of `tests/` run during this session. Claims are not assumed — they are falsification attempts
that returned no matches.

**Cross-references:** Lane 1 findings CC-01, CC-04, CC-05, CC-06 are cited in findings below where
the fitness-function lens adds a distinct, non-overlapping perspective. The subject may overlap but
the lens does not.

---

## 2. Architectural Characteristics Ranking

Ranked by observable evidence — code patterns, test investment, ADR rationale, HR rules — not by
stated intent. Counter-evidence listed where the rank is disputed by actual code behavior.

| Rank | Characteristic | Evidence (what proves it's prioritized) | Counter-evidence |
|------|---------------|------------------------------------------|-----------------|
| 1 | **Correctness** | pyright strict; Pydantic v2 at every external boundary; HR-5 (no invented numbers) is the only HR with a docstring in `energia/__init__.py`; eval `pass@3`/`pass^3` gates; `MigrationIntegrityError` raises on hash mismatch | `tokens_in=0` in `streamlit_app.py:95` silently misreports input tokens (AF-08); `build_graph() -> Any` (AF-02) allows wrong GRAPH invocation shapes past pyright |
| 2 | **LGPD compliance / Security** | LangSmith explicitly rejected in ADR-002 on LGPD grounds; DuckDB local file means bill PII stays on-device by default; CPF redaction tested in `test_audit_callback_does_not_log_pii`; `data/energia.duckdb` gitignored | `_scrub_pii` covers CPF format only; `installation_number` (UC) traverses the audit callback unredacted (AF-05); no test asserts absence of langsmith as a transitive dep (AF-06) |
| 3 | **Migration integrity** | HR-3 SHA-256 check is the best-tested architectural property in the codebase (4 tests: create, idempotent, hash-match, tamper-reject); forward-only runner enforced in both `db.py` and test suite | No test exercises `ON CONFLICT DO NOTHING` for `bill_hash` UNIQUE constraint; `bill_store.find_by_hash` (Task 1.4) does not yet exist |
| 4 | **Observability** | `DuckDBAuditCallback` is the LangSmith substitute for local tool-call tracing; every tool start/end/error writes to `tool_calls`; `TokenBudgetCallback` emits WARNING logs at 50% and raises at 100% | 80% budget warning path has no test; audit callback drops end/error events silently when `call_id is None` (Lane 1 Open Question 4, no Lane 2 test) |
| 5 | **Testability** | 53 tests; TDD discipline enforced; domain functions are explicitly separated from LangChain wrappers (ADR-002); `run_example` uses lazy import of GRAPH so evals don't execute LLM code at import time | Eager `_llm = ChatAnthropic(...)` at module scope in `nodes.py` forces `load_dotenv()` to precede every import from `energia.chat.graph` — hidden tax on every new test module (TD-007); no import-topology fitness function prevents regression (AF-03) |
| 6 | **Maintainability** | Package separation by sprint (`bill/`, `tariff/`, `solar/` empty stubs pre-populate the planned structure); `models.py` has zero framework imports (verified by grep); `evals/scorers.py` is a pure-function module with no side effects | `chat/nodes.py` has highest efferent coupling per LOC in the codebase (37 LOC, 8 dependencies including three third-party packages); `ALL_TOOLS` hand-maintained list (CC-04) multiplies merge risk linearly with each new tool |
| 7 | **Deployability / Simplicity** | Single-process Streamlit; embedded DuckDB (no server); `uv sync && streamlit run` is the full quickstart (ADR-003); no FastAPI, no Docker required for v1 | Module-scope LLM construction (CC-01) ties startup to `ANTHROPIC_API_KEY` being present before any import; future multi-user requirement (post-v1) requires PostgreSQL migration (ADR-003 anticipated, not designed for) |
| 8 | **Performance** | DuckDB chosen over SQLite for analytical query performance (ADR-003); `pvlib` + pandas chosen for solar calculations | No benchmarks or load tests; Streamlit single-process model limits concurrency; no caching layer for ANEEL API calls yet |

---

## 3. Fitness Function Audit

A fitness function is an executable assertion that an architectural property holds. Status: ✅ Asserted,
⚠️ Partially asserted, ❌ Not asserted (convention only).

| Property claimed | Source | Fitness function | Status |
|-----------------|--------|-----------------|--------|
| Applied migration files are immutable (SHA-256 check) | CLAUDE.md HR-3 | `tests/db/test_migrations.py::test_migrate_rejects_modified_applied_migration` — tampers a file post-apply, asserts `MigrationIntegrityError` | ✅ |
| Migration runner is idempotent | ADR-003 | `tests/db/test_migrations.py::test_migrate_is_idempotent` | ✅ |
| All 6 expected tables created by migrations | ADR-003 | `tests/db/test_migrations.py::test_migrate_creates_tables` | ✅ |
| HR-7: session halts when token budget exceeded | CLAUDE.md HR-7 | `tests/chat/test_budget.py::test_budget_callback_raises_at_threshold` | ✅ |
| HR-7: budget value is 200,000 tokens | CLAUDE.md HR-7 | `tests/test_smoke.py::test_import_config` (`assert settings.session_token_budget == 200_000`) | ✅ |
| HR-6: CPF pattern is redacted before DuckDB insertion | CLAUDE.md HR-6 | `tests/chat/test_audit.py::test_audit_callback_does_not_log_pii` | ✅ |
| pass@3 ≥ 0.90 gate logic is correct | EDD discipline | `tests/evals/test_runner.py` (exercises `run_capability`, checks `passed` field) | ✅ |
| pass^3 = 1.00 gate logic is correct | EDD discipline | `tests/evals/test_runner.py` (exercises `run_regression`, checks `all_passed` field) | ✅ |
| HR-7: 80% budget warning fires exactly once | CLAUDE.md HR-7 | None — grep of `tests/` for `80%\|_warned_80\|0\.8` returned no test assertion | ❌ |
| HR-6: `installation_number` (UC) is redacted before DuckDB insertion | CLAUDE.md HR-6 | None — grep of `tests/` for `installation_number.*redact\|scrub.*install` returned no matches | ❌ |
| HR-5: system prompt contains the PT-BR no-invented-numbers instruction | CLAUDE.md HR-5 | None — grep of `tests/` for `nunca inventa\|SYSTEM_PROMPT` returned no matches | ❌ |
| HR-5: chatbot refuses to produce numeric claims when no tool has been called | CLAUDE.md HR-5 | None — no eval example tests the refusal path; convention only | ❌ |
| HR-2: v1 out-of-scope code (WhatsApp, NILM, inverter) is absent | CLAUDE.md HR-2 | None — no test asserts banned imports or modules are absent | ❌ |
| Domain models (`models.py`, planned `bill/parser.py`) import nothing from LangChain/LangGraph/DuckDB | ADR-002 ("Domain functions stay pure") | None — `models.py` is currently clean (verified by grep); no test enforces this for `models.py` or any future inner-ring module | ❌ |
| `langchain` meta-package and `langsmith` are absent from runtime dependencies | ADR-002 (LGPD: langsmith rejected) | None — `pyproject.toml` is clean today; no test asserts `importlib.util.find_spec("langsmith") is None` | ❌ |
| ADR-002 concurrent tool call safety: `DuckDBAuditCallback` is re-entrant-safe | ADR-002 ("LangGraph's parallel-tool-call execution… The DuckDB connection helper… sidesteps the issue") | None — grep of `tests/` for `concurrent\|thread\|parallel\|asyncio` returned no matches | ❌ |
| `conversations.total_tokens_in` is populated with actual input token counts | Schema design (`total_tokens_in`, `total_tokens_out` columns) | None — `update_token_totals(tokens_in=0, ...)` always writes zero; no test asserts column value after call | ❌ |
| Eval gate (`pass@3`, `pass^3`) blocks shipping when grade fails | EDD discipline | Logic is unit-tested; but `_check_api_key()` exits code 2 (skipped) when `ANTHROPIC_API_KEY` is absent, so CI without the key treats the gate as always-passing | ⚠️ |
| `bill_hash UNIQUE` prevents duplicate bill rows (`ON CONFLICT DO NOTHING`) | Schema design (HR-3 spirit applied to bill data) | Schema column exists and is tested in `test_bill_schema_adds_all_new_columns`; but no test exercises the `ON CONFLICT` code path | ⚠️ |

---

## 4. Findings

Finding schema: Location, Lens, Evidence, Smell, Why it matters now, Recommended fix, Cost,
Priority. Prefix `AF-`. Lane 1 findings are cited by ID where the architectural lens adds a
non-overlapping perspective.

---

### AF-01: No fitness function prevents re-introduction of module-scope LLM construction

**Locations:**
- `src/energia/chat/nodes.py:13-14`
- `src/energia/chat/graph.py:24`

**Lens:** Fitness function gap (Evolvability + Testability)

**Evidence:**
```python
# nodes.py:13-14
_llm = ChatAnthropic(model_name=settings.anthropic_model, max_tokens_to_sample=4096)
GRAPH = build_graph()  # graph.py:24 — fires on every import
```
`tests/chat/test_graph.py:30` patches `energia.chat.nodes._llm_with_tools` at the attribute level,
which works but requires the module-scope construction to have already occurred. Grep of `tests/`
for `test.*import.*graph.*no.*llm|importing.*graph.*should.*not` → no matches. No test asserts
"importing `energia.chat.graph` without `ANTHROPIC_API_KEY` set should not trigger LLM
construction."

**Smell (architectural, not craft):** Lane 1's CC-01 documented the Dependency Rule violation. The
fitness-function gap here is distinct: even after CC-01 is fixed (lazy factory), nothing prevents a
future developer — or a future tool module — from re-introducing module-scope construction. The
current test suite cannot detect the regression because it always imports with the key present (CI
sets it) or patches the attribute (tests use mocker). TD-007 (ruff E402 suppression) exists
specifically because this coupling forces `load_dotenv()` to appear before the import in both
entry-point files — a visible downstream cost of the absent fitness function.

**Why it matters now:** Task 1.3 adds a vision-capable LLM call. If vision requires different
`ChatAnthropic` parameters (beta headers, higher `max_tokens`), the likely path is to construct a
second module-scope instance in `nodes.py` — compounding CC-01 rather than fixing it.

**Recommended fix:** Write `tests/test_architecture.py::test_importing_chat_graph_without_api_key_does_not_raise`
that temporarily unsets `ANTHROPIC_API_KEY`, imports `energia.chat.graph` in a subprocess (or
uses `importlib.reload` after patching), and asserts no `AuthenticationError` or constructor call
fires. This test fails today (confirming the gap) and passes after CC-01's refactor lands.

**Cost:** S (test writing only; the CC-01 refactor is the real L-cost and belongs to that finding)

**Priority:** should-fix — pre-Task 1.3, to gate the refactor

---

### AF-02: `build_graph() -> Any` erases static type safety at all GRAPH invocation sites

**Locations:**
- `src/energia/chat/graph.py:10` (`def build_graph() -> Any`)
- `src/energia/ui/streamlit_app.py:80` (`result = GRAPH.invoke(graph_state, ...)`)
- `src/energia/evals/runner.py:159` (`state: Any = GRAPH.invoke(...)`)

**Lens:** Fitness function gap (Correctness via static analysis)

**Evidence:**
```python
# graph.py:10 — Any propagates to every call site
def build_graph() -> Any:
    ...
GRAPH = build_graph()
```
TD-002 explains why: langgraph has no published type stubs, so pyright cannot resolve
`CompiledGraph`. The consequence is that `GRAPH` is typed `Any` everywhere it is used. Pyright
reports zero errors on any `GRAPH.invoke(...)` call regardless of the argument shape, because
`Any.invoke` accepts all argument shapes. Grep of `typings/` or `src/` for a Protocol-based stub
for `CompiledGraph` → directory `typings/` does not exist.

**Smell:** The two `GRAPH.invoke()` call sites (`streamlit_app.py:80`, `runner.py:159`) pass a
`dict` with four keys (`messages`, `user_id`, `conversation_id`, `tokens_used`). If either call
site omits a key or misspells one, pyright is silent — the type hole is complete. This is a direct
consequence of TD-002, but the fitness gap is at the call-site layer: a Protocol stub costing ~10
lines would restore type visibility without requiring upstream langgraph stubs.

**Why it matters now:** Task 1.3 will add at least one new `GRAPH.invoke()` call (in the eval
runner's test for `parse_bill_image`). Each new invocation widens the unguarded surface. If `ChatState`
gains a new required field (e.g., `image_bytes`) in a future sprint, existing call sites that omit
it will not be caught by pyright.

**Recommended fix:** Create `typings/langgraph/__init__.pyi` with a minimal stub:
```python
from typing import Any
class CompiledGraph:
    def invoke(self, input: dict[str, Any], config: Any = ...) -> dict[str, Any]: ...
```
Then update `graph.py`: `def build_graph() -> CompiledGraph`. This anchors the return type without
requiring full langgraph stubs. Narrows but does not fully resolve TD-002.

**Cost:** S (stub + one annotation change)

**Priority:** nice-to-have — narrows TD-002 incrementally; low urgency but zero risk

---

### AF-03: No fitness function asserts the Dependency Rule for inner-ring modules

**Locations:**
- `src/energia/models.py` (currently clean — confirmed by grep)
- Planned: `src/energia/bill/parser.py`, `src/energia/solar/*.py`, `src/energia/tariff/*.py`

**Lens:** Fitness function gap (Maintainability + Evolvability)

**Evidence:**
- Grep of `src/energia/models.py` for `langchain|langgraph|langsmith|duckdb|streamlit` → no
  matches. The module is currently framework-pure.
- ADR-002 states: "Domain functions stay pure. Tests for `solar.sizing.estimate_solar_system` do
  not import LangChain."
- Grep of `tests/` for any architectural import-topology assertion → no matches. No test enforces
  this property.

**Smell:** The "domain functions stay pure" claim in ADR-002 is true today by convention, not by
enforcement. `models.py` has zero framework imports; this will remain true until a developer (or
an agent following PLAN.md's `@tool` decorator example) adds an import to the domain module
instead of keeping it in the wrapper. Without a test, the regression would not be caught at PR
review time — only at runtime when a test of `solar/sizing.py` suddenly requires a LangChain import.

**Why it matters now:** Task 1.3 creates `src/energia/bill/parser.py` — the first real inner-ring
domain module. The ADR-002 boundary (domain function in `bill/parser.py`, LangChain wrapper in
`chat/tools/bill.py`) is architecturally correct and testability-enabling. But the natural
temptation when writing `parse_bill_image` is to use `@tool` directly in `parser.py` to avoid a
two-file setup. A fitness function that runs at `pytest -q` would prevent this.

**Recommended fix:** Add `tests/test_architecture.py::test_inner_ring_modules_have_no_framework_imports`:
```python
import ast, pathlib
INNER_RING = ["src/energia/models.py"]  # extend as bill/parser.py etc. land
BANNED = {"langchain_core", "langchain_anthropic", "langgraph", "duckdb", "streamlit"}

def test_inner_ring_modules_have_no_framework_imports() -> None:
    for path in INNER_RING:
        tree = ast.parse(pathlib.Path(path).read_text())
        imports = {n.names[0].name.split(".")[0]
                   for n in ast.walk(tree) if isinstance(n, ast.Import)}
        imports |= {n.module.split(".")[0]
                    for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert imports.isdisjoint(BANNED), f"{path}: banned imports found: {imports & BANNED}"
```
Extend `INNER_RING` as each new domain module lands. Zero false positives against current clean state.

**Cost:** S (≤1 hr; maintain list as new inner-ring modules are added)

**Priority:** must-fix before Task 1.3 ships `bill/parser.py`

---

### AF-04: HR-5 "no invented numbers" has no executable fitness function at any layer

**Locations:**
- CLAUDE.md HR-5; `src/energia/chat/prompts.py` (Protected Path); `src/energia/__init__.py`

**Lens:** Fitness function gap (Correctness — the project's #1 ranked architectural characteristic)

**Evidence:**
- Grep of `tests/` for `nunca inventa|SYSTEM_PROMPT|HR-5|quantitativ|invented.*number` → no matches
- `src/energia/__init__.py` line 5 references HR-5 in its docstring; `prompts.py` contains the
  PT-BR system prompt. Neither has a test.
- The eval suite tests *tool routing* (which tool was called, what input it received). No eval
  example tests the negative path: "when no tool has been called, does the model refuse to
  invent a number?"

**Smell:** HR-5 is the most frequently cited rule in the project (CLAUDE.md, `__init__.py`, ADR-002,
KICKOFF.md references). It is the core correctness guarantee of the chatbot. Yet there is no
executable check at any layer: no unit test confirms the prompt contains the required PT-BR
instruction; no eval tests the refusal behavior; no scorer penalizes a response that produces a
number without a preceding tool call. The property is entirely convention-enforced.

**Why it matters now:** Task 1.3 ships the first numeric tool (`parse_bill_image` returns
`consumption_kwh`, `total_brl`, `confidence`). If the eval file for `parse_bill_image` does not
include a refusal case — a prompt asking "quanto eu gastei?" without a bill image attached — HR-5
will remain completely untested after Sprint 1. The absence is architectural: the eval design gate
(EDD) has no scorer concept for "model did NOT invent a number."

**Recommended fix (two layers):**
1. Unit test in `tests/chat/test_prompts.py` (new file): assert `"nunca inventa números"` (or the
   exact contracted phrase) appears in `SYSTEM_PROMPT`. This is a one-line assertion on a string
   constant. Fragile only if the phrase changes deliberately — which is exactly the change that
   should require Daniel's explicit sign-off.
2. Eval example for `parse_bill_image` capability file: one case with `expected_tool: null` and
   user prompt "Quanto eu paguei no último mês?" (no image). The scorer asserts no tool was called
   and the response does not match `\d+[\.,]\d{2}` (a currency pattern). This is an EDD concern
   but the fitness gap is architectural: the scorer infrastructure (`scorers.py`) currently has no
   `output_not_matches_pattern` function.

**Cost:** S for the prompt assertion; M for the eval design (new scorer needed)

**Priority:** should-fix — HR-5 is rank-1 correctness, currently completely unasserted

---

### AF-05: HR-6 LGPD PII redaction gap — `installation_number` traverses audit callback unredacted

**Locations:**
- `src/energia/chat/audit.py:20-22` (`_scrub_pii`)
- `tests/chat/test_audit.py` (covers CPF only)

**Lens:** Fitness function gap (Security/LGPD compliance — rank-2 architectural characteristic)

**Evidence:**
```python
# audit.py:20-22
_CPF_RE = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")

def _scrub_pii(text: str) -> str:
    return _CPF_RE.sub("[CPF-REDACTED]", text)
```
Grep of `tests/` for `installation_number.*redact|scrub.*install|uc.*redact` → no matches.
`test_audit_callback_does_not_log_pii` passes `"cpf": "123.456.789-00"` and asserts `[CPF-REDACTED]`
appears in `tool_calls.input_json`. No analogous test exists for `installation_number`.

ADR-003 states: "bill PII (CPF, address, installation number) stays on the user's machine (HR-6)."
`installation_number` is explicitly named as PII. When `parse_bill_image` invokes the LangChain
tool wrapper, the tool's output JSON (`{"installation_number": "30012345"}`) flows through
`on_tool_end`, which calls `_scrub_pii` on `output_str`. The current regex does not match
installation number formats (typically 4–13 digits, distributor-dependent, no dashes).

**Why it matters now:** Task 1.3 is the first code path that will write `installation_number` into
`tool_calls.output_json`. After Task 1.3 ships, every bill parse will persist the UC identifier
in unredacted form in the local DuckDB. While the database stays on-device (satisfying the data
residency requirement), it violates the spirit of HR-6: if a user shares their `energia.duckdb`
file for debugging, or if a future export feature is added, the UC identifier leaks.

**Recommended fix:**
1. Extend `_scrub_pii` to redact by key name rather than by value pattern (the value format
   varies by distributor):
   ```python
   _INSTALL_NUM_RE = re.compile(r'"installation_number"\s*:\s*"[^"]*"')
   # in _scrub_pii:
   text = _INSTALL_NUM_RE.sub('"installation_number": "[UC-REDACTED]"', text)
   ```
2. Add `test_audit_callback_does_not_log_installation_number` to `tests/chat/test_audit.py` —
   passes `'{"installation_number": "30012345"}'` as `input_str`, asserts `[UC-REDACTED]` in
   stored `input_json`. (This requires HR-4 approval since it edits an existing test file —
   flag for Daniel.)

**Cost:** S (code change ≤30 min; test requires HR-4 approval)

**Priority:** must-fix — HR-6 compliance; LGPD is non-negotiable; Task 1.3 is the trigger

---

### AF-06: ADR-002's "no langchain / no langsmith in runtime" constraint has no automated guard

**Location:** `pyproject.toml` (runtime deps); ADR-002

**Lens:** Fitness function gap (Security/LGPD compliance)

**Evidence:**
- Grep of `pyproject.toml` for `langsmith|^langchain\b` → no matches. Currently clean.
- ADR-002: "Adopting any of the above [langchain, langchain-community, langsmith] post-v1 requires
  a new ADR." The LGPD rationale for rejecting langsmith is explicit: it would send bill PII to a
  third-party endpoint.
- Grep of `tests/` for any assertion on installed packages (`find_spec|pkg_resources|importlib`) →
  no matches.

**Smell:** `uv add langsmith` is a one-command operation. If a langchain ecosystem update pulls
langsmith as a transitive dependency, or if a future agent adds it as a "helpful tracing tool,"
the LGPD constraint is violated with no runtime indication. The constraint exists only in ADR-002
prose, not in any executable check.

**Why it matters now:** Task 1.3 will process bill images. If langsmith is present and default
tracing is enabled, it silently sends tool inputs (which now include base64-encoded bill images or
extracted bill text containing CPF/UC) to LangSmith's cloud. The combination of langchain-core
and langsmith can enable tracing automatically via environment variables — no explicit code change
required.

**Recommended fix:**
```python
# tests/test_dependencies.py (new file)
import importlib.util

def test_langsmith_not_installed() -> None:
    assert importlib.util.find_spec("langsmith") is None, (
        "langsmith must not be installed — LGPD: would send bill PII to third-party cloud. "
        "See ADR-002."
    )

def test_langchain_metapackage_not_installed() -> None:
    assert importlib.util.find_spec("langchain") is None, (
        "langchain meta-package must not be installed — see ADR-002 for rationale."
    )
```
Zero false positives against the current dependency set. Fails immediately on `uv add langsmith`.

**Cost:** XS (5–10 min)

**Priority:** should-fix — the cost is near-zero and the protection is high-value given LGPD

---

### AF-07: ADR-002 concurrent tool-call safety claim has no executable test

**Location:** ADR-002 ("LangGraph's parallel-tool-call execution means our audit callback must be
thread-safe / re-entrant-safe"); `src/energia/chat/audit.py`

**Lens:** Fitness function gap (Correctness)

**Evidence:**
- ADR-002 explicitly names the risk and states the mitigation: connection-per-call sidesteps the
  thread-safety issue.
- Grep of `tests/` for `concurrent|thread|parallel|asyncio|ThreadPool` → no matches.
- `DuckDBAuditCallback._run_to_call_id` is a mutable instance dict (`dict[str, str]`) written by
  `on_tool_start` and read by `on_tool_end`/`on_tool_error`. Two concurrent `on_tool_start` calls
  on the same instance write to this dict without any locking.

**Smell:** The connection-per-call pattern (one `connect()` + `close()` per event) does correctly
sidestep DuckDB connection thread-safety. But the in-memory `_run_to_call_id` dict is not
thread-safe. Two simultaneous `on_tool_start` calls could interleave their writes; a subsequent
`on_tool_end` for call A could read the `call_id` written by call B's `on_tool_start`, updating
the wrong row in `tool_calls`. This would produce silent data corruption in the audit log — no
exception, wrong association.

**Why it matters now:** Task 1.3 is the first real tool. When two tools are called in parallel by
the LangGraph `ToolNode` (e.g., `parse_bill_image` and a future `current_bandeira_tool` in the
same turn), both will invoke `on_tool_start` on the same `DuckDBAuditCallback` instance with
different `run_id` values. The current test suite never exercises this path — all tests invoke
one tool event at a time (sequentially).

**Recommended fix:** A test using `concurrent.futures.ThreadPoolExecutor` (≤20 lines):
```python
import concurrent.futures, uuid
def test_audit_callback_handles_concurrent_tool_starts(tmp_db):
    cb = DuckDBAuditCallback(conversation_id=tmp_db["conversation_id"],
                             db_path=tmp_db["db_path"])
    run_ids = [uuid.uuid4() for _ in range(3)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(cb.on_tool_start,
                             serialized={"name": f"tool_{i}"},
                             input_str=f'{{"i": {i}}}',
                             run_id=run_ids[i]) for i in range(3)]
        for f in futures: f.result()
    # assert 3 distinct rows with distinct tool_names exist
```
If this test reveals a race (likely on the `_run_to_call_id` dict), the fix is to guard the dict
with `threading.Lock()`. The architectural claim in ADR-002 becomes testably true only after this
test passes.

**Cost:** S (test writing + potential threading.Lock addition in audit.py)

**Priority:** should-fix — ADR-002 asserts this property; the assertion should be executable

---

### AF-08: `tokens_in=0` call-site vs. two-column schema contract; no asserting test

**Location:** `src/energia/ui/streamlit_app.py:95`; `conversations` table schema

**Lens:** Fitness function gap (schema-vs-contract mismatch; Correctness)

**Evidence:**
```python
# streamlit_app.py:95
update_token_totals(
    conversation_id=st.session_state["conversation_id"],
    tokens_in=0,               # always zero
    tokens_out=tokens_used,    # actually the combined input+output count
    db_path=db_path,
)
```
The `conversations` table has both `total_tokens_in` and `total_tokens_out` columns (confirmed in
`test_bill_schema.py`; schema added in `20260510_0001_initial_schema.sql`). Grep of `tests/` for
any assertion that `total_tokens_in > 0` or that `total_tokens_out` reflects output-only tokens →
no matches. The `ChatState.tokens_used` field accumulates `usage_metadata["total_tokens"]` (input +
output combined), so the call site cannot separate them without the raw `input_tokens` /
`output_tokens` values from `usage_metadata`.

**Smell:** Two distinct architectural interpretations are currently valid: (a) intentional
single-column design where `total_tokens_out` holds the combined total and `total_tokens_in` is
deprecated but not yet removed, or (b) a bug where input tokens are never recorded because
`ChatState` does not carry them separately. Both interpretations are consistent with the current
code. The schema promises two-column tracking; the call site implements one-column tracking. Without
a fitness function (a test asserting specific values in both columns), the interpretation cannot be
determined mechanically, and future developers will reason about it differently.

**Why it matters now:** HR-7 tracks cumulative tokens for the cost guardrail. The `TokenBudgetCallback`
tracks combined tokens correctly (it reads `usage_metadata["total_tokens"]`). But the `conversations`
table analytics — intended for session cost auditing — will report zero input token consumption for
every session. Task 1.3's bill image parsing will consume substantial input tokens; the audit trail
will under-report by the full input-token count.

**Recommended fix:** Resolve the interpretation first (Daniel's call). Two options:
- **Option A (fix call site):** Pass real input/output separately. This requires `ChatState` to
  carry `tokens_in` and `tokens_out` as separate fields, or `streamlit_app.py` to accumulate them
  from callback data rather than from state.
- **Option B (simplify schema):** Acknowledge single-column design is intentional. Create a new
  migration that drops `total_tokens_in` (forward-only per HR-3) and renames `total_tokens_out`
  to `total_tokens`. Add an ADR entry noting the decision.
  
Whichever option is chosen, add a test asserting the column(s) contain expected values after a
`GRAPH.invoke()` call followed by `update_token_totals`.

**Cost:** S (test) + M (if schema change or state refactor is chosen)

**Priority:** should-fix — the unresolved ambiguity will silently compound with every new tool call

---

## 5. Coupling Hotspots

The five modules with the highest combined afferent (fan-in) + efferent (fan-out) coupling, and
which of them are on the critical path for Task 1.3:

| Module | Afferent (who depends on me) | Efferent (who I depend on) | Task 1.3 touched? |
|--------|------------------------------|----------------------------|-------------------|
| `chat/nodes.py` | 1 (graph.py) | 5 first-party + 3 third-party (ChatAnthropic, langchain_core, langgraph) = 8 | **Yes** — vision parameters likely require LLM reconfiguration |
| `db.py` | 5 first-party + 2 test files = 7 | 2 (config, duckdb) | Indirectly — `bill_store.py` will call `connect()` |
| `ui/streamlit_app.py` | 0 (script) | 6 first-party + 3 third-party = 9 | Indirectly — GRAPH change propagates here |
| `chat/tools/__init__.py` | 3 (nodes.py + 2 test files) | 2 (BaseTool, hello) | **Yes** — `parse_bill_image_tool` must be registered here |
| `chat/audit.py` | 2 (streamlit_app.py + test_audit.py) | 2 (db.connect, langchain_core) | **Yes** — bill image data will flow through `on_tool_end`; AF-05 PII gap activates |

`chat/nodes.py` has the highest efferent coupling *per line of code* (37 LOC, 8 dependencies),
making it the highest-risk change surface for Task 1.3. Any modification to LLM parameters
(e.g., adding a `betas=["interleaved-thinking"]` parameter for vision) must be made inside
`nodes.py`, where the coupling is already at its densest. This compounds CC-01's architectural
debt: the module that owns the most framework coupling is also the module that will need to change
first to support vision. `db.py` has the highest fan-in (7 direct dependents) — a breaking change
to `connect()` or `migrate()` touches more modules than any other single change in the codebase.

---

## 6. Forward-Looking Notes (Task 1.3 Pressure Points — Architectural Angle)

For each of Lane 0's four pressure points, the architectural shape implied and the fitness
function that would catch a regression.

**Vision tool placement (`parse_bill_image_tool` in `chat/tools/bill.py`).**

Architectural shape: `bill/parser.py` (pure domain function, inner ring) ← called by →
`chat/tools/bill.py` (LangChain `@tool` wrapper, outer ring). The boundary is architecturally
correct per ADR-002 and is the premise of AF-03's proposed fitness function. The fitness function
that would prevent `parser.py` from re-acquiring orchestration responsibilities is
`test_inner_ring_modules_have_no_framework_imports` (AF-03): once `bill/parser.py` is added to
that test's `INNER_RING` list, any `from langchain_core import ...` in the parser will fail CI.
A separate fitness function specific to retry logic: a test that asserts
`inspect.getsource(energia.bill.parser)` does not import `tenacity`, `httpx`, or `time.sleep` —
retry policy belongs in the wrapper, not the domain. This is a corollary of AF-03 but targets a
specific orchestration concern.

**Hash-based idempotency (`sha256(image_bytes)`).**

Architectural shape: three-layer contract. (1) DB constraint: `bill_hash TEXT NOT NULL UNIQUE` —
enforced by DuckDB on every INSERT. (2) Application-level: `bill_store.find_by_hash()` (Task 1.4)
returns existing row or `None`. (3) Orchestration: the tool wrapper checks before parsing.

Fitness function proposals:
- Layer 1 (already partially asserted): a test that attempts two INSERTs with the same
  `bill_hash` and asserts a unique-constraint violation is raised by DuckDB. The
  `test_bill_schema_defaults_are_applied` test does a plain INSERT but never exercises the
  UNIQUE constraint. This test belongs in Task 1.4's `test_bill_store.py`.
- Layer 3 (parse_bill_image ownership risk from Lane 1): if the parser owns the idempotency
  check, the fitness function that catches the SRP violation is AF-03 — `bill/parser.py` should
  not import from `energia.db` or `energia.bill.store`. Adding `energia.db` and `energia.bill.store`
  to the banned imports in AF-03's test would enforce the boundary mechanically.

**Five failure modes (PLAN.md lines 655–664).**

Each failure mode is a fitness function candidate. Listed as proposals for Task 1.3's TDD RED step:

| Failure mode | Fitness function proposal | Where it lives |
|-------------|--------------------------|----------------|
| Anthropic 5xx → one retry | Mock `ChatAnthropic.invoke` to raise `anthropic.APIStatusError` (5xx); assert tool wrapper retries once and succeeds on second call | `tests/bill/test_parser.py` or `tests/chat/tools/test_bill.py` |
| Pydantic validation failure → error in `tool_calls.error` | Inject a malformed model response; assert `tool_calls.error` column is non-null and contains `ValidationError` | `tests/chat/test_audit.py` (HR-4 approval) or new `tests/bill/` |
| Confidence < 0.85 → `needs_user_confirmation=True` | Pass a mock extraction with `confidence=0.80`; assert returned `Bill.needs_user_confirmation is True` | `tests/bill/test_parser.py` |
| Duplicate hash → `ON CONFLICT DO NOTHING` | Insert a bill with a known hash; call `bill_store.insert` again; assert exactly one row in `bills` for that hash | `tests/bill/test_bill_store.py` (Task 1.4) |
| Image too large / format unsupported | Pass a 21 MB file; assert tool wrapper raises a typed exception (not an opaque HTTP error) | `tests/chat/tools/test_bill.py` |

These are fitness functions for Task 1.3's architectural properties. Lane 3 should verify
which of these are already in PLAN.md Task 1.3's seven test functions; any that are absent are
gaps between the plan and the architecture.

**Installation_number redaction (HR-6).**

Fitness function that would catch a future regression: `test_audit_callback_does_not_log_installation_number`
(proposed in AF-05). The test should be added to `tests/chat/test_audit.py` under HR-4 approval
*before* Task 1.3 ships, not after. A post-Task-1.3 addition means at least one CI run has already
persisted an unredacted UC identifier. The fitness function must predate the data flow it guards.

The broader architectural observation: `_scrub_pii` is a point function that will need to grow as
new PII fields are identified (CNPJ, CEP, meter serial number). The CC-05 finding (Lane 1)
proposed an `AuditRepository` separation. From the fitness angle: if `_scrub_pii` is extracted to
a standalone `pii.py` module (or `audit_scrubber.py`), a dedicated test suite can enumerate every
known PII field independently of the callback machinery. The current design colocates the policy
(what counts as PII) and the mechanism (how to scrub it) in the callback class, making both harder
to test in isolation and harder to extend.

---

## 7. Open Questions for Synthesis (and Lane 3)

1. **Eval gate in CI:** `_check_api_key()` exits with code 2 (skipped) when `ANTHROPIC_API_KEY` is
   absent. CI without the key treats the gate as always-passing. The fitness-function table marks
   this ⚠️ Partially asserted. Lane 3 should answer: is a stub-response eval path (using cached
   or fixture responses) feasible, or is the current "skip in CI" posture acceptable for a
   single-user prototype? The architectural implication is that the EDD gate claimed in CLAUDE.md
   does not currently block CI merges.

2. **`run_example` synthetic IDs and audit callback:** Lane 1 Open Question 2 asked whether the
   eval runner wires `DuckDBAuditCallback`. Lane 3 should confirm. If it does, the
   `"eval-runner"` / `"eval-{example.name}"` synthetic IDs will violate the FK constraint on
   `tool_calls.message_id → messages.id`. This is a correctness gap that only manifests when both
   the audit callback and the eval runner are active simultaneously — exactly the configuration
   that Task 1.3's evals will use.

3. **`tokens_in=0` resolution (AF-08):** Two architecturally different resolutions are available
   (fix call site vs. simplify schema). Resolution (b) requires a new migration under HR-3 rules.
   The choice has downstream implications for any analytics query on the `conversations` table.
   Daniel should decide before Task 1.3 ships, because the bill parsing tool will be the first
   high-input-token operation.

4. **`chat/nodes.py` LLM singleton and Task 1.3 vision parameters:** If `parse_bill_image`
   requires a different `ChatAnthropic` configuration (e.g., `betas=["interleaved-thinking-2025-01-20"]`
   for vision), the CC-01 refactor (lazy factory accepting LLM as argument) is a pre-condition,
   not a nice-to-have. Lane 3 should confirm whether the existing `claude-sonnet-4-6` model
   configuration handles base64-encoded images without additional beta headers — if it does,
   Task 1.3 can proceed with the current `nodes.py` shape, deferring CC-01. If it does not,
   CC-01 and AF-01 become must-fix for Task 1.3.

---

## 8. Non-Findings (Properties Already Well-Covered)

Honest accounting of architectural properties that already have strong fitness functions:

- **HR-3 migration immutability:** 4 tests cover create, idempotency, hash-match verification,
  and tamper rejection. The best-tested single architectural property in the codebase. No gap.

- **HR-7 token budget halt mechanism:** `test_budget_callback_raises_at_threshold` asserts the
  mechanism works end-to-end. Budget constant independently checked in smoke test. The 80% warning
  path (AF) is a secondary gap; the primary halt mechanism is solid.

- **Eval gate logic (pass@3 / pass^3):** The mathematical implementations in `runner.py` are
  unit-tested with mocked GRAPH in `tests/evals/test_runner.py`. The distinction between
  "logic tested" and "gate enforced in CI" is noted in the fitness table (⚠️ Partially asserted)
  but the implementations themselves are correct.

- **DuckDB CAP statement (ADR-003):** Structural enforcement — an embedded single-process database
  with WAL cannot have network partitions in v1. No fitness function is needed beyond "the database
  opens." The `test_migrate_creates_tables` test implicitly confirms DuckDB is reachable.

- **`models.py` framework-purity (current state):** Verified by grep during this session — zero
  framework imports. AF-03 flags the absence of enforcement; the current state is genuinely clean.

- **HR-6 CPF redaction:** `test_audit_callback_does_not_log_pii` is a concrete, specific test that
  passes the exact CPF format, confirms `[CPF-REDACTED]` appears in the stored JSON, and confirms
  the original value is absent. AF-05 is an *extension* to this (installation_number), not a
  critique of what exists.
