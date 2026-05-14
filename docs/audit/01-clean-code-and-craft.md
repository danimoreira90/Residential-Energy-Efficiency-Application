# Lane 1 — Clean Code & Craft Audit
**Audit date:** 2026-05-13
**Branch audited:** `chore/sprint-1-audit`
**Lane:** 1 of 4 (sequential audit series)
**Predecessor:** `docs/audit/00-context.md` (Lane 0 — Inventory & Context)

---

## 1. Methodology

**Lenses applied:** Clean Code (naming, function length, single-level-of-abstraction, comment quality, output channels), SOLID (SRP and DIP as primary; OCP where genuinely applicable), Clean Architecture (Dependency Rule: source-code dependencies point inward toward higher-level policy).

**Natural rings for this project, outermost to innermost:**
- Framework / UI: `ui/streamlit_app.py`, `db.py` (migration CLI), `chat/audit.py`, `evals/run.py`
- Orchestration / use-cases: `chat/graph.py`, `chat/nodes.py`, `evals/runner.py`
- Domain adapters / tool wrappers: `chat/tools/`, `chat/memory.py`, `chat/budget.py`
- Domain models: `models.py`

**Bar applied:** Open-source-ready. Findings are the kind a future external contributor would notice or appreciate seeing addressed — not stylistic nits, but real craft issues.

**Files re-read in this session with the Uncle Bob lens** (Lane 0 inventory was the map; Lane 1 read the code itself):
`db.py`, `config.py`, `models.py`, `chat/audit.py`, `chat/budget.py`, `chat/graph.py`, `chat/memory.py`, `chat/nodes.py`, `chat/tools/__init__.py`, `chat/tools/hello.py`, `evals/run.py`, `evals/runner.py`, `evals/scorers.py`, `ui/streamlit_app.py`

**Skipped (trivial placeholders, no logic to lens):** `energia/__init__.py`, `bill/__init__.py`, `tariff/__init__.py`, `solar/__init__.py`, `ui/__init__.py`, `evals/__init__.py`, `chat/__init__.py`, `chat/state.py` (12 LOC TypedDict definition), `chat/prompts.py` (13 LOC string constant, Protected Path).

**TD log:** TD-007 (E402 ruff suppression), TD-003 (N818 global suppression), TD-002 (pyright langgraph stubs) are cross-referenced where they connect to a finding but are **not re-flagged as new findings**. TD-006, TD-005, TD-004, TD-001 are out of scope for this lens.

**What this lane does NOT produce:** architectural fitness function analysis (Lane 2), testability analysis beyond direct call-graph observations (Lane 3), synthesis or prioritization across lanes (Daniel post-audit), no code edits, no commits.

---

## 2. Findings

### CC-01: Eager LLM and GRAPH construction at module scope — `chat/nodes.py:13-14` and `chat/graph.py:24`

**Locations:**
- `src/energia/chat/nodes.py:13-14`
- `src/energia/chat/graph.py:24`

**Lens(es):** Clean Architecture + SOLID:DIP

**Evidence:**
```python
# nodes.py:13-14
_llm = ChatAnthropic(model_name=settings.anthropic_model, max_tokens_to_sample=4096)  # type: ignore[call-arg]
_llm_with_tools = _llm.bind_tools(ALL_TOOLS)

# graph.py:24
GRAPH = build_graph()
```

**The smell:** `nodes.py` constructs a concrete `ChatAnthropic` instance at module load time, and `graph.py` compiles the full `StateGraph` at import time. The Dependency Rule says outer rings depend on inner ones — not the reverse. Here, the LangChain/Anthropic client (a framework-layer concern, outermost ring) is constructed inside `nodes.py` (orchestration ring), which means the framework is wired at the wrong layer. Any file that `import`s from `energia.chat.graph` or `energia.chat.nodes` silently triggers both LLM construction and graph compilation as a side effect of the import. This is what forced `load_dotenv()` to be called before those imports in both entry-point files (the visible symptom is TD-007). DIP is violated because `nodes.py` depends on the concrete `ChatAnthropic` rather than any `BaseChatModel` abstraction.

**Why it matters now:** Task 1.3 adds a vision-capable model call (`parse_bill_image`). If that call requires different model parameters (e.g., beta header for vision, a higher `max_tokens`), the current shape forces another module-scope mutation or a second `ChatAnthropic` instance — both in `nodes.py`, again at the wrong layer. The eager GRAPH also means that any future test that imports `energia.chat.graph` must have `ANTHROPIC_API_KEY` set or be patched, which will grow as a hidden tax on every new test module.

**Recommended fix:** Convert to a lazy factory: rename `build_graph()` to accept the LLM as an argument (`def build_graph(llm: BaseChatModel) -> CompiledGraph:`), call it from the entry points (`streamlit_app.py`, `evals/run.py`, test fixtures) after `load_dotenv()`. `nodes.py` exports `make_agent_node(llm)` and `make_tool_node()` rather than module-level instances. This simultaneously resolves TD-007 (ruff suppression can be removed because `load_dotenv()` no longer needs to precede the import chain).

**Cost:** L (≥ half day — touches nodes, graph, streamlit_app, evals/run, test fixtures)

**Priority:** should-fix

---

### CC-02: `ui/streamlit_app.py` is a flat 95-line script with no function boundaries

**Location:** `src/energia/ui/streamlit_app.py` (whole file)

**Lens(es):** Clean Architecture + Clean Code:single-level-of-abstraction

**Evidence:**
```python
# Lines 22-95 — a single flat script block, no functions defined anywhere:
migrate()
st.set_page_config(...)
st.title(...)
if "session_id" not in st.session_state:
    ...
if user_input := st.chat_input(...):
    save_message(...)
    result = GRAPH.invoke(graph_state, ...)
    update_token_totals(...)
```

**The smell:** The file does five distinct things at a single flat level of abstraction: infrastructure bootstrap (`migrate()`), page configuration, session state initialisation, chat history rendering, and message event handling. Clean Code's single-level-of-abstraction rule says a function body should contain steps that are all at the same level; here the entire script reads as one giant function body mixing all five levels simultaneously. From the Dependency Rule, a UI framework script is the outermost ring and *may* call inward — but it should not embed the orchestration logic of what to do when a message arrives. That logic (`graph_state` construction, callback wiring, `TokenBudgetExceeded` handling, result extraction) belongs in an extracted `handle_message(user_input)` function.

**Why it matters now:** Task 1.6 adds `tests/ui/test_streamlit_smoke.py`. A flat script with no importable functions makes it structurally impossible to unit-test any individual behavior without running the entire script through `streamlit.testing`. Extracting even `_bootstrap_session()` and `_handle_message(user_input)` would make the critical path testable in isolation.

**Recommended fix:** Extract three functions: `_bootstrap_session()` (the five `if "x" not in st.session_state` blocks), `_render_history()` (the `for msg` loop), `_handle_message(user_input) -> tuple[str, int]` (GRAPH invocation, exception handling, result extraction). The top-level script becomes a 15-line readable orchestration. None of this changes runtime behavior.

**Cost:** S (≤ 30 min)

**Priority:** should-fix

---

### CC-03: `needs_user_confirmation` is an orchestration flag embedded in the domain model — `models.py:53-55`

**Location:** `src/energia/models.py:53-55`

**Lens(es):** Clean Architecture

**Evidence:**
```python
needs_user_confirmation: bool = Field(
    description="True if any field has confidence < 0.85"
)
```

**The smell:** `Bill` is the innermost-ring domain model. `needs_user_confirmation` is not a property of a Brazilian energy bill — it is a routing decision made by the orchestration layer based on the bill's `confidence` field. The rule "confidence < 0.85 → needs confirmation" is a use-case policy, not a domain invariant. Embedding it in `Bill` means the domain model must know about the chatbot's confirmation workflow, which is an outward dependency (domain knowing about orchestration). As currently defined, callers are also expected to set this field correctly at construction time — the model enforces no invariant linking `needs_user_confirmation` to `confidence`, so the two can silently diverge.

**Why it matters now:** Task 1.3's parser will construct `Bill` objects and set `needs_user_confirmation=True` when `confidence < 0.85`. At that point, the field's value is computed in `parser.py` (use-case ring) but declared as a domain field — meaning the domain carries state that only the use-case ring understands. Any future caller that constructs a `Bill` from a different source (e.g., DB retrieval in `bill_store`) must also know to set this field correctly.

**Recommended fix:** Option A (preferred): remove `needs_user_confirmation` from `Bill`; have `parser.py` return a `ParseResult(bill: Bill, needs_confirmation: bool)` dataclass that keeps the routing concern in the use-case ring. Option B: keep the field but add a `@model_validator` that derives it from `confidence` automatically, making the invariant explicit and removing the caller's responsibility to set it correctly.

**Cost:** S (≤ 30 min for Option B; M for Option A since it touches Task 1.3 design)

**Priority:** nice-to-have

---

### CC-04: `ALL_TOOLS` is a hand-maintained list; planned tools documented in a comment instead of expressed in code — `chat/tools/__init__.py:9-19`

**Location:** `src/energia/chat/tools/__init__.py:9-19`

**Lens(es):** SOLID:OCP + Clean Code (comment replacing code)

**Evidence:**
```python
"""...
Sprint 1 adds: parse_bill_image_tool, store_bill_tool, list_user_bills_tool,
               compare_bill_periods_tool, detect_consumption_anomaly_tool.
Sprint 2 adds: current_bandeira_tool, get_tariff_tool, simulate_tarifa_branca_tool.
Sprint 3 adds: estimate_solar_system_tool, solar_payback_tool.
"""
from langchain_core.tools import BaseTool
from energia.chat.tools.hello import hello_world_tool

ALL_TOOLS: list[BaseTool] = [hello_world_tool]
```

**The smell:** The docstring enumerates 9 future tools by name; `ALL_TOOLS` does the same work for 1 tool as code. This is the clearest Clean Code sign of a comment that exists because the code cannot yet say what it means. Adding each new tool requires editing `__init__.py` — a modification to a shipping module rather than an extension. OCP says a module should be open for extension (new tool files) and closed for modification (existing files). The docstring roadmap is also frozen knowledge: when a Sprint 1 tool is renamed or deferred, this comment will quietly become wrong.

**Why it matters now:** Sprint 1 adds five tools simultaneously. Five separate edits to `__init__.py`, five merges to watch for conflicts, and five opportunities for the list to drift from reality if one tool is skipped or renamed.

**Recommended fix:** Introduce a lightweight registry: a module `chat/tools/registry.py` that exposes a `register` decorator and a `get_all_tools() -> list[BaseTool]` function. Each tool file decorates its tool with `@register`. `__init__.py` imports `get_all_tools` and sets `ALL_TOOLS = get_all_tools()`. Adding a new tool requires only creating a new file and adding `@register` — `__init__.py` is untouched. The docstring roadmap then disappears: the registry is the roadmap. (If a formal registry feels heavy for now, at minimum remove the docstring roadmap and let each Sprint import be the documentation.)

**Cost:** M (1–4 hr — new registry module + updating existing tool, nodes import)

**Priority:** should-fix

---

### CC-05: `DuckDBAuditCallback` mixes event routing, state management, and data access — `chat/audit.py`

**Location:** `src/energia/chat/audit.py` (whole class)

**Lens(es):** SOLID:SRP

**Evidence:**
```python
class DuckDBAuditCallback(BaseCallbackHandler):
    def __init__(...):
        self._run_to_call_id: dict[str, str] = {}   # responsibility 1: state

    def on_tool_start(self, ...):
        con = connect(self._db_path)                 # responsibility 2: data access
        try:
            msg_row = con.execute("INSERT INTO messages ...").fetchone()
            call_row = con.execute("INSERT INTO tool_calls ...").fetchone()
            self._run_to_call_id[str(run_id)] = str(call_row[0])
        finally:
            con.close()
```

**The smell:** The class has two distinct reasons to change: (1) the LangChain callback protocol changes (event method signatures, event lifecycle), and (2) the storage schema changes (table names, SQL, connection management). These are separate concerns that currently live in the same class. An external contributor wanting to add a PostgreSQL backend in v2 would have to edit the LangChain callback class, which is not the right layer for that change. Additionally, the class directly depends on the concrete `connect()` function (`energia.db`) — no abstraction is inserted, making it impossible to test the callback logic without a real DuckDB file.

**Why it matters now:** Task 1.3 adds `parse_bill_image_tool`, which will generate `on_tool_start` events with image data in `input_str`. The audit callback's SQL shape may need to change (e.g., storing image hash instead of raw bytes). A class that mixes event routing with SQL execution makes that change riskier and harder to verify in isolation.

**Recommended fix:** Extract an `AuditRepository` (or `ToolCallStore`) class with methods `record_start(tool_name, input_json, conversation_id) -> str` and `record_end(call_id, output)` / `record_error(call_id, error)`. `DuckDBAuditCallback` holds an `AuditRepository` instance and delegates all storage calls to it. This makes the repository independently swappable and testable.

**Cost:** M (1–4 hr)

**Priority:** should-fix

---

### CC-06: Connection-per-function try/finally boilerplate repeated four times — `chat/memory.py`

**Locations:**
- `src/energia/chat/memory.py:11-26` (`mint_user`)
- `src/energia/chat/memory.py:29-41` (`mint_conversation`)
- `src/energia/chat/memory.py:44-62` (`save_message`)
- `src/energia/chat/memory.py:65-82` (`update_token_totals`)

**Lens(es):** Clean Code:DRY

**Evidence (representative — same pattern in all four):**
```python
def mint_user(session_id: str, db_path: str | None = None) -> str:
    con = connect(db_path)
    try:
        row = con.execute(...).fetchone()
        ...
    finally:
        con.close()
```

**The smell:** The acquire-use-release pattern (`con = connect(db_path)` / `try` / `finally: con.close()`) appears verbatim four times across four functions. Each function mixes connection lifecycle management with its domain operation. This is the classic primitive-obsession smell applied to connections — the connection is a resource that should be managed by an abstraction rather than repeated inline. Beyond repetition, the pattern prevents callers from batching two operations in a single transaction (e.g., `mint_user` + `mint_conversation` atomically in the future).

**Why it matters now:** Task 1.4 adds `bill_store.py` with `insert`, `find_by_hash`, and likely `list_by_user` — three more functions that will copy the same pattern if no abstraction exists. The debt compounds linearly with each new persistence function.

**Recommended fix:** A `contextlib.contextmanager` helper in `db.py`:
```python
@contextmanager
def connection(path: str | None = None):
    con = connect(path)
    try:
        yield con
    finally:
        con.close()
```
Each `memory.py` function becomes a `with connection(db_path) as con:` block. Alternatively, if a `DatabaseGateway` / repository pattern lands for CC-05, the memory functions can become methods on the same repository. Either way, the `try/finally` disappears from four places.

**Cost:** S (≤ 30 min for the context manager alone)

**Priority:** should-fix

---

### CC-07: Opaque inline sum-generator in eval runner hides which attempt failed — `evals/runner.py:220-222` and `:266-268`

**Locations:**
- `src/energia/evals/runner.py:220-222` (in `run_capability`)
- `src/energia/evals/runner.py:266-268` (in `run_regression`)

**Lens(es):** Clean Code:single-level-of-abstraction

**Evidence:**
```python
# run_capability, lines 220-222:
passing = sum(
    1 for _ in range(attempts) if score_attempt(run_example(example), example)
)

# run_regression, lines 266-268:
passing = sum(
    1 for _ in range(attempts) if score_attempt(run_example(example), example)
)
```

**The smell:** These two generator expressions pack three operations into one line: invoking `run_example` (which calls the live LLM), scoring the result, and accumulating a count. The `for _ in range(attempts)` idiom discards the iteration variable, hiding the attempt number. More importantly, if `run_example` raises an exception on attempt 2 of 3, the exception propagates out of the `sum()` with no context about which attempt failed or how many had already passed. The function's caller (`run_capability`) has no way to detect partial progress. The duplication is a secondary concern; the obscured failure mode is the primary one.

**Why it matters now:** When `parse_bill_image_tool` is live, eval attempts will make real Anthropic API calls with real images. Debugging a 429 rate-limit or a network timeout that occurs mid-generator requires knowing which attempt number failed. The current expression swallows that information.

**Recommended fix:** Extract a shared helper (used by both callers):
```python
def _count_passing_attempts(example: EvalExample, attempts: int) -> int:
    passing = 0
    for attempt_num in range(1, attempts + 1):
        try:
            result = run_example(example)
        except Exception:
            logger.warning("Attempt %d/%d failed for %s", attempt_num, attempts, example.name)
            continue
        if score_attempt(result, example):
            passing += 1
    return passing
```
Both `run_capability` and `run_regression` replace their generator with `_count_passing_attempts(example, attempts)`.

**Cost:** S (≤ 30 min)

**Priority:** should-fix

---

### CC-08: `# type: ignore[call-arg]` on `ChatAnthropic` constructor suppresses a possible parameter name mismatch without explanation — `chat/nodes.py:13`

**Location:** `src/energia/chat/nodes.py:13`

**Lens(es):** Clean Code:comments

**Evidence:**
```python
_llm = ChatAnthropic(model_name=settings.anthropic_model, max_tokens_to_sample=4096)  # type: ignore[call-arg]
```

**The smell:** The suppression silences pyright's "unexpected keyword argument" error on `model_name` and `max_tokens_to_sample`. In current `langchain-anthropic`, the constructor parameter is `model` (not `model_name`) and `max_tokens` (not `max_tokens_to_sample` — the legacy Anthropic SDK name). If these parameters are silently dropped or misrouted by `**kwargs`, the LLM is constructed with an implicit default model and a default token limit, which may differ from what the code intends. The suppress comment says only `call-arg`; it says nothing about *which* argument is wrong, what the correct name is, or whether this was verified at runtime. A future contributor who upgrades `langchain-anthropic` has no guide to determine whether the ignore is still needed or was masking a real misconfiguration. Note: TD-002 covers langgraph stubs; this is a distinct suppress on a different library (`langchain-anthropic`) with a distinct risk profile.

**Why it matters now:** Task 1.3 requires the LLM to be vision-capable. If the constructor is already not receiving intended parameters, the vision feature may silently use wrong settings (wrong model, wrong token budget). Verifying this before Task 1.3 is safer than discovering it at eval time.

**Recommended fix:** Step 1 — verify the current `langchain-anthropic` constructor signature (e.g., `from langchain_anthropic import ChatAnthropic; help(ChatAnthropic.__init__)`). Step 2 — use the correct parameter names and remove the `type: ignore`. If the ignore is still needed after using correct names, add a comment that names the open issue (e.g., `# langchain-anthropic==X.Y.Z: model= accepted but pyright reports call-arg — see GH#NNN`).

**Cost:** S (≤ 30 min)

**Priority:** should-fix

---

### CC-09: `migrate()` mixes five abstraction levels in one function body and uses `print()` inconsistently with `logger` — `db.py:62-137`

**Location:** `src/energia/db.py:62-137`

**Lens(es):** Clean Code:single-level-of-abstraction + Clean Code:output-channel consistency

**Evidence:**
```python
# Lines 129-135 — presentation logic inside the migration engine:
if applied_names:
    count = len(applied_names)
    suffix = "s" if count != 1 else ""
    names_str = ", ".join(applied_names)
    print(f"Applied {count} migration{suffix}: {names_str}")
else:
    logger.debug("No new migrations to apply.")
```

**The smell:** `migrate()` at 76 lines (lines 62–137) mixes: directory resolution, directory existence guard, glob + sort, connection management, per-file hash verification, transaction management, and result summarisation. These are at least four distinct abstraction levels in one function body. The private helpers `_sha256_file` and `_ensure_schema_migrations` are well extracted — but the main loop still contains everything else. Additionally, the success path uses `print()` while the no-op path uses `logger.debug()`. This means the migration runner produces stdout output in production (e.g., during `streamlit_app.py` startup) that cannot be silenced by adjusting log level. If `streamlit_app.py` calls `migrate()` on every page refresh (per the inline comment "idempotent and fast"), every refresh with a pending migration will print to stdout regardless of log configuration.

**Why it matters now:** When `bill_store.py` (Task 1.4) and future migrations land, `migrate()` will be called more often. stdout-in-production becomes harder to suppress after the fact.

**Recommended fix:** Extract `_apply_pending(con, sql_files)` → `list[str]` and `_report_applied(names)` → emit via `logger.info` (not `print`). The CLI entrypoint at lines 140–145 can print to stdout if desired; the library function should only log. This keeps the top-level `migrate()` body at one abstraction level (orchestration) and makes the output channel consistent.

**Cost:** S–M (30–90 min)

**Priority:** nice-to-have

---

### CC-10: Magic threshold literals `0.5` and `0.8` with boolean flags that duplicate the threshold values — `chat/budget.py:63-72`

**Location:** `src/energia/chat/budget.py:63-72`

**Lens(es):** Clean Code:naming + Clean Code:magic numbers

**Evidence:**
```python
if pct >= 0.5 and not self._warned_50:
    self._warned_50 = True
    logger.warning("Token budget 50%% used: ...")

if pct >= 0.8 and not self._warned_80:
    self._warned_80 = True
    logger.warning("Token budget 80%% used: ...")
```

**The smell:** The threshold values `0.5` and `0.8` appear as magic literals, and the flag names `_warned_50` and `_warned_80` encode the same values as names — shotgun surgery: changing 0.8 to 0.75 requires renaming `_warned_80` to `_warned_75` and updating the log message. If a third threshold (e.g., 0.95) is added for a pre-emptive warning, the pattern requires adding another `elif` block, another named boolean, and another magic literal.

**Recommended fix:**
```python
_WARN_THRESHOLDS: tuple[float, ...] = (0.5, 0.8)
# ...
self._warned_at: set[float] = set()

for threshold in _WARN_THRESHOLDS:
    if pct >= threshold and threshold not in self._warned_at:
        self._warned_at.add(threshold)
        logger.warning("Token budget %.0f%% used: ...", threshold * 100, ...)
```
Adding a new threshold is a one-token change to the tuple.

**Cost:** S (≤ 30 min)

**Priority:** nice-to-have

---

### CC-11: Hardcoded `× 3` in CLI output is not derived from the report data — `evals/run.py:33` and `:66`

**Locations:**
- `src/energia/evals/run.py:33`
- `src/energia/evals/run.py:66`

**Lens(es):** Clean Code:magic numbers

**Evidence:**
```python
# Line 33:
total_calls = report.total_examples * 3
print(f"Running {report.total_examples} examples × 3 attempts = {total_calls} calls")

# Line 66:
print(f"Running {report.total_examples} regression examples × 3 attempts each")
```

**The smell:** `_run_capability` calls `run_capability(name)` without an `attempts` argument, so the default `attempts=3` is always used. The `3` is then hardcoded again in the output string instead of being derived from `report.example_reports[0].total_attempts`. If `run_capability` is ever called with a different attempt count (e.g., `attempts=1` for a fast smoke check), the CLI output will print the wrong number silently.

**Recommended fix:** Expose `attempts` as an optional CLI argument (`--attempts`, default 3); derive the printed count from `report.example_reports[0].total_attempts` if the list is non-empty. This makes the CLI output self-consistent with the actual run.

**Cost:** S (≤ 30 min)

**Priority:** defer-as-TD (no active plan to change the default attempt count; low risk until then)

---

## 3. Non-Findings (Modules Examined, No Issues)

Honest accounting — modules opened and inspected where no finding was raised:

- **`evals/scorers.py`**: Three pure functions, each doing one thing, well-typed, no side effects. `input_matches` using `all(tc.args.get(k) == v ...)` for subset matching is idiomatic and readable.
- **`chat/state.py`**: 12-line TypedDict with correct `Annotated` reducer annotation. Nothing to flag.
- **`chat/prompts.py`**: 13-line string constant, Protected Path. No craft issue.
- **`chat/tools/hello.py`**: Stub, temporary, self-contained. Scheduled for removal.
- **`config.py`**: Clean `BaseSettings` subclass with documented defaults. The `aneel_base_url` default is a constant in a settings class (overridable via env var) — not a hardcoded URL in application logic.
- **`models.py`** (other than CC-03): `PeriodStr` TypeAlias with regex constraint, `BillComposition` decomposition, `Decimal` for monetary values — all correct domain choices. The field ordering in both models is sensible.
- **`evals/runner.py`** (other than CC-07): `load_eval` error handling (catching `json.JSONDecodeError` and `ValidationError` separately, re-raising as `ValueError` with line numbers) is correct and informative. The `__all__` list is maintained. `score_attempt` short-circuits cleanly.
- **`db.py`** (other than CC-09): The extracted helpers `_sha256_file` and `_ensure_schema_migrations` are appropriately scoped. The explicit transaction (`con.begin()` / `con.commit()` / `con.rollback()`) is correct and explicit. `MigrationIntegrityError` is properly named and has a meaningful message.

---

## 4. Forward-Looking Notes (Task 1.3 Pressure Points)

Lane 0 Section 6 flagged four concerns. From the Uncle Bob perspective:

**Vision tool placement (`parse_bill_image_tool` in `chat/tools/bill.py`).**
The current `ALL_TOOLS` pattern (CC-04) makes the tool addition mechanical but error-prone — one more explicit import in `__init__.py`. The bigger craft pressure is that the domain function (`bill/parser.py`) and the LangChain wrapper (`chat/tools/bill.py`) have a clear layer boundary per the docstring in `chat/tools/__init__.py`. If that boundary holds, the domain function can be tested without any LangChain imports, which is exactly right. The pressure point is `nodes.py` (CC-01): if the LLM stays as a module-level singleton, `parse_bill_image_tool` cannot independently configure the LLM for vision (e.g., different beta headers or model variant) without touching `nodes.py`'s module-level instantiation.

**Hash-based idempotency (`sha256(image_bytes)`).**
The `bill_hash` column exists in the schema; the lookup-and-store pattern (`find_by_hash` / `insert`) will land in `bill/store.py`. The CC-06 finding (connection-per-function boilerplate) will reproduce there unless the context-manager helper is in place first. From an SRP perspective, the parser function should not own the idempotency check — `find_by_hash` is a storage concern that the use-case layer calls before invoking the parser. The current PLAN.md outline puts both the idempotency check and the parsing in `parse_bill_image` — that is a subtle SRP violation in the plan itself. Worth flagging to Daniel separately.

**Five failure modes (retry, validation, confidence, conflict).**
All five are orchestration concerns, not domain concerns. They belong in the tool wrapper (`chat/tools/bill.py`), not in `bill/parser.py`. If they leak into the parser, the parser acquires a reason to change for both "parsing algorithm improvements" and "orchestration policy changes" — an SRP violation. The tool wrapper is the right place for retry logic, confidence thresholding, and the `ON CONFLICT` branch; the parser returns a `Bill` (or raises a typed exception) and nothing more.

**Audit logging for `installation_number` redaction.**
`_scrub_pii` at `audit.py:20-22` matches CPF format only. The `installation_number` field is a numeric string (6–11 digits, distributor-dependent) with no standard format. From a Clean Architecture perspective, the redaction policy is currently embedded in `DuckDBAuditCallback` as a module-level private function. If the policy needs to expand (add `installation_number` patterns, add CNPJ), the change touches the callback class — compounding CC-05 (SRP). The redaction function should be the extension point; the callback should delegate to it without knowing the rules.

---

## 5. Open Questions for Synthesis

These items were observed but not classified as findings because the right call depends on cross-lane input:

1. **`update_token_totals(tokens_in=0, tokens_out=tokens_used)` in `streamlit_app.py:95`** — The `conversations` table has both `total_tokens_in` and `total_tokens_out` columns, but `tokens_in=0` is always passed. This may be intentional (the combined count is what HR-7 tracks) or a logic gap. If intentional, the two-column design in the schema is over-specified. If a gap, the column is silently never incremented. This is partly a testability question (Lane 3) and partly a schema design question (Lane 2). Neither is strictly a Clean Code finding, but a reader will be confused.

2. **`run_example` hardcodes `"eval-runner"` and `"eval-{example.name}"` as `user_id` / `conversation_id`** (`runner.py:163-164`). These strings bypass the `mint_user` / `mint_conversation` logic entirely. This is correct for eval isolation, but means the eval runner writes into the `messages` table (if `DuckDBAuditCallback` is wired) with synthetic IDs that don't correspond to real DB rows. Lane 3 should verify whether the eval runner wires audit callbacks at all; if it does, the FK constraints on `tool_calls.message_id` → `messages.id` would fail with synthetic IDs. If it does not, no issue — but worth confirming.

3. **`build_graph() -> Any` erases the compiled graph's type** (`graph.py:10`). TD-002 is the root cause (langgraph stubs absent). The surface effect is that `GRAPH` is typed as `Any` everywhere it is used (`GRAPH.invoke(...)` is untyped). This is downstream of TD-002, not a new finding — but it is a distinct surface that will continue to hide type errors in the graph invocation call sites until TD-002 is resolved. Lane 2 may have a view on whether a `Protocol` stub is worth introducing now.

4. **`on_tool_end` and `on_tool_error` silently return early if `call_id is None`** (`audit.py:86-87`, `:105-106`). This happens when `on_tool_start` failed to insert the row (e.g., DB connection error). The silent return means a tool completion event is dropped with no log warning. Lane 3 should check whether the test suite covers this path.
