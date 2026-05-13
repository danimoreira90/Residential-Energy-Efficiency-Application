# Lane 0 — Inventory & Context
**Audit date:** 2026-05-13
**Branch audited:** `chore/sprint-1-audit`
**Scope:** `src/energia/` (full) + `tests/` (file→module mapping only)
**Out of scope:** `migrations/`, `notebooks/`, `data/`, `evals/`, `app_energia/`, `Dados/`

---

## 1. Module Map

Ordered by directory, then alphabetically within each directory.
LOC = raw `wc -l` output; no blank/comment lines subtracted.

---

### `src/energia/__init__.py` — 7 LOC

**Purpose:** Package-level module docstring establishing project identity and stating the HR-5 quantitative discipline rule.

**Public surface:** *(none — no classes or top-level functions defined)*

**Outbound dependencies:**
- Third-party: *(none)*
- First-party: *(none)*

**Inbound dependencies:**
- `tests/test_smoke.py` (`import energia`)

---

### `src/energia/config.py` — 53 LOC

**Purpose:** Pydantic Settings class that loads all application configuration from environment variables and an optional `.env` file, exposing a module-level singleton `settings`.

**Public surface:**
- `Settings` (class — BaseSettings subclass)
- `settings` (module-level Settings instance)

**Outbound dependencies:**
- Third-party: `pydantic` (Field), `pydantic_settings` (BaseSettings, SettingsConfigDict)
- First-party: *(none)*

**Inbound dependencies:**
- `src/energia/db.py` (lazy import inside `connect()`)
- `src/energia/chat/budget.py`
- `src/energia/chat/nodes.py`
- `src/energia/evals/runner.py`

---

### `src/energia/db.py` — 145 LOC

**Purpose:** DuckDB connection helper (`connect`) and forward-only migration runner (`migrate`) that enforces HR-3 hash-based immutability of applied migrations.

**Public surface:**
- `MigrationIntegrityError` (exception class)
- `connect` (function)
- `migrate` (function)

**Outbound dependencies:**
- Third-party: `duckdb`
- Stdlib: `hashlib`, `logging`, `sys`, `pathlib.Path`
- First-party: `energia.config` (lazy import of `settings` inside `connect()`)

**Inbound dependencies:**
- `src/energia/chat/audit.py`
- `src/energia/chat/memory.py`
- `src/energia/ui/streamlit_app.py`
- `tests/chat/conftest.py`
- `tests/db/test_migrations.py`
- `tests/db/test_bill_schema.py`

---

### `src/energia/models.py` — 55 LOC

**Purpose:** Pydantic v2 domain models for a parsed Brazilian energy bill (`Bill`) and its charge breakdown (`BillComposition`), including a `PeriodStr` type alias with a YYYY-MM regex constraint.

**Public surface:**
- `PeriodStr` (TypeAlias — `Annotated[str, StringConstraints(...)]`)
- `BillComposition` (class — BaseModel)
- `Bill` (class — BaseModel)

**Outbound dependencies:**
- Third-party: `pydantic` (BaseModel, Field, StringConstraints)
- Stdlib: `datetime.date`, `decimal.Decimal`, `typing` (Annotated, TypeAlias)
- First-party: *(none)*

**Inbound dependencies:**
- `tests/test_models.py`

---

### `src/energia/bill/__init__.py` — 7 LOC

**Purpose:** Package-level docstring placeholder listing the three Sprint 1 sub-modules (`parser.py`, `store.py`, `analysis.py`) that do not yet exist on disk.

**Public surface:** *(none)*

**Outbound dependencies:** *(none)*

**Inbound dependencies:**
- `tests/test_smoke.py` (`from energia import bill`)

---

### `src/energia/chat/__init__.py` — 12 LOC

**Purpose:** Package-level docstring enumerating all Sprint 0 chat sub-modules and their roles.

**Public surface:** *(none)*

**Outbound dependencies:** *(none)*

**Inbound dependencies:** *(none — sub-modules are imported by full path, not via `energia.chat`)*

---

### `src/energia/chat/audit.py` — 116 LOC

**Purpose:** `BaseCallbackHandler` subclass (`DuckDBAuditCallback`) that writes a row to the `tool_calls` DuckDB table on every tool start/end/error event, with CPF pattern redaction to satisfy HR-5 and HR-6.

**Public surface:**
- `DuckDBAuditCallback` (class — BaseCallbackHandler subclass)

**Outbound dependencies:**
- Third-party: `langchain_core.callbacks.base` (BaseCallbackHandler)
- Stdlib: `logging`, `re`, `typing.Any`, `uuid.UUID`
- First-party: `energia.db` (connect)

**Inbound dependencies:**
- `src/energia/ui/streamlit_app.py`
- `tests/chat/test_audit.py`

---

### `src/energia/chat/budget.py` — 83 LOC

**Purpose:** `BaseCallbackHandler` subclass (`TokenBudgetCallback`) that accumulates cumulative token usage from `on_llm_end` events, emits WARNING logs at 50% and 80% of budget, and raises `TokenBudgetExceeded` when the per-session budget is exceeded (HR-7).

**Public surface:**
- `TokenBudgetExceeded` (exception class)
- `TokenBudgetCallback` (class — BaseCallbackHandler subclass)

**Outbound dependencies:**
- Third-party: `langchain_core.callbacks.base` (BaseCallbackHandler), `langchain_core.messages` (AIMessage), `langchain_core.outputs` (ChatGeneration, LLMResult)
- Stdlib: `logging`, `typing.Any`, `uuid.UUID`
- First-party: `energia.config` (settings)

**Inbound dependencies:**
- `src/energia/ui/streamlit_app.py`
- `tests/chat/test_budget.py`

---

### `src/energia/chat/graph.py` — 24 LOC

**Purpose:** Assembles and compiles the LangGraph `StateGraph` (agent node → conditional edge → tools node → back to agent) and exports a module-level `GRAPH` singleton that is instantiated at import time.

**Public surface:**
- `build_graph` (function)
- `GRAPH` (module-level compiled StateGraph instance)

**Outbound dependencies:**
- Third-party: `langgraph.graph` (END, START, StateGraph)
- Stdlib: `typing.Any`
- First-party: `energia.chat.nodes` (agent_node, route_after_agent, tool_node), `energia.chat.state` (ChatState)

**Inbound dependencies:**
- `src/energia/ui/streamlit_app.py`
- `src/energia/evals/runner.py` (lazy import inside `run_example()`)
- `tests/chat/test_graph.py`
- `tests/evals/test_runner.py`

---

### `src/energia/chat/memory.py` — 82 LOC

**Purpose:** Thin DuckDB helper functions for creating users and conversations, inserting message rows, and incrementing conversation token totals; each function opens and closes its own connection.

**Public surface:**
- `mint_user` (function)
- `mint_conversation` (function)
- `save_message` (function)
- `update_token_totals` (function)

**Outbound dependencies:**
- Third-party: *(none)*
- First-party: `energia.db` (connect)

**Inbound dependencies:**
- `src/energia/ui/streamlit_app.py`

---

### `src/energia/chat/nodes.py` — 37 LOC

**Purpose:** Defines the two LangGraph node functions (`agent_node`, `tool_node`) and the conditional edge function (`route_after_agent`); also constructs module-level `_llm` (`ChatAnthropic`) and `_llm_with_tools` (LLM with all tools bound) at import time.

**Public surface:**
- `tool_node` (module-level ToolNode instance)
- `agent_node` (function)
- `route_after_agent` (function)

**Outbound dependencies:**
- Third-party: `langchain_anthropic` (ChatAnthropic), `langchain_core.messages` (AIMessage, SystemMessage), `langgraph.prebuilt` (ToolNode)
- Stdlib: `typing.Any`
- First-party: `energia.chat.prompts` (SYSTEM_PROMPT), `energia.chat.state` (ChatState), `energia.chat.tools` (ALL_TOOLS), `energia.config` (settings)

**Inbound dependencies:**
- `src/energia/chat/graph.py`

---

### `src/energia/chat/prompts.py` — 13 LOC

**Purpose:** Contains the PT-BR system prompt as a single module-level string constant; designated a PROTECTED PATH (HR-4).

**Public surface:**
- `SYSTEM_PROMPT` (str constant)

**Outbound dependencies:** *(none)*

**Inbound dependencies:**
- `src/energia/chat/nodes.py`

---

### `src/energia/chat/state.py` — 12 LOC

**Purpose:** Defines the `ChatState` TypedDict with the LangGraph `add_messages` reducer annotation on the `messages` field, plus `user_id`, `conversation_id`, and `tokens_used`.

**Public surface:**
- `ChatState` (TypedDict class)

**Outbound dependencies:**
- Third-party: `langchain_core.messages` (BaseMessage), `langgraph.graph.message` (add_messages)
- Stdlib: `typing` (Annotated, TypedDict)
- First-party: *(none)*

**Inbound dependencies:**
- `src/energia/chat/graph.py`
- `src/energia/chat/nodes.py`
- `tests/chat/test_state.py`

---

### `src/energia/chat/tools/__init__.py` — 19 LOC

**Purpose:** Assembles `ALL_TOOLS` as a hand-maintained list of `BaseTool` instances imported from domain-specific tool sub-modules; currently contains only `hello_world_tool`.

**Public surface:**
- `ALL_TOOLS` (list[BaseTool])

**Outbound dependencies:**
- Third-party: `langchain_core.tools` (BaseTool)
- First-party: `energia.chat.tools.hello` (hello_world_tool)

**Inbound dependencies:**
- `src/energia/chat/nodes.py`
- `tests/test_smoke.py`
- `tests/chat/test_tools.py`

---

### `src/energia/chat/tools/hello.py` — 17 LOC

**Purpose:** Sprint 0 stub `@tool`-decorated function (`hello_world_tool`) that returns a greeting dict; scheduled for removal in Sprint 1 when real bill-analysis tools ship.

**Public surface:**
- `HelloInput` (BaseModel class — args schema)
- `hello_world_tool` (decorated function / StructuredTool instance)

**Outbound dependencies:**
- Third-party: `langchain_core.tools` (tool decorator), `pydantic` (BaseModel, Field)
- First-party: *(none)*

**Inbound dependencies:**
- `src/energia/chat/tools/__init__.py`
- `tests/chat/test_tools.py`
- `tests/chat/test_graph.py`

---

### `src/energia/evals/__init__.py` — 1 LOC

**Purpose:** Minimal package marker with a one-line docstring.

**Public surface:** *(none)*

**Outbound dependencies:** *(none)*

**Inbound dependencies:** *(none — sub-modules imported by full path)*

---

### `src/energia/evals/run.py` — 105 LOC

**Purpose:** CLI entrypoint (`python -m energia.evals.run`) dispatching to `run_capability` or `run_regression`; exits with code 0 (gate passed), 1 (gate failed), or 2 (skipped — API key absent). Calls `load_dotenv()` at module level before other imports.

**Public surface:**
- `main` (function)

**Outbound dependencies:**
- Third-party: `dotenv` (load_dotenv — called at module level)
- Stdlib: `argparse`, `sys`
- First-party: `energia.evals.runner` (EvalSkipped, run_capability, run_regression — lazy imports inside functions)

**Inbound dependencies:** *(none — script entrypoint, not imported by other modules)*

---

### `src/energia/evals/runner.py` — 282 LOC

**Purpose:** Core eval execution engine: loads JSONL examples, invokes `GRAPH`, collects tool calls and final message text, scores attempts with scorers, and computes pass@3 (capability) and pass^3 (regression) reports.

**Public surface:**
- `EvalSkipped` (exception class)
- `MessageInput` (Pydantic BaseModel)
- `EvalExample` (Pydantic BaseModel)
- `ExampleReport` (Pydantic BaseModel)
- `CapabilityReport` (Pydantic BaseModel)
- `RegressionReport` (Pydantic BaseModel)
- `load_eval` (function)
- `run_example` (function)
- `score_attempt` (function)
- `run_capability` (function)
- `run_regression` (function)

**Outbound dependencies:**
- Third-party: `langchain_core.messages` (AIMessage, HumanMessage), `pydantic` (BaseModel, ValidationError)
- Stdlib: `json`, `math.ceil`, `pathlib.Path`, `typing.Any`
- First-party: `energia.config` (settings), `energia.evals.scorers` (ExampleResult, ToolCallRecord, tool_called, input_matches, output_matches_pattern), `energia.chat.graph` (GRAPH — lazy import inside `run_example()`)

**Inbound dependencies:**
- `src/energia/evals/run.py` (lazy imports)
- `tests/evals/test_runner.py`

---

### `src/energia/evals/scorers.py` — 55 LOC

**Purpose:** Pure-function scoring primitives (`tool_called`, `input_matches`, `output_matches_pattern`) plus the `ToolCallRecord` and `ExampleResult` Pydantic models used as the shared result type between runner and scorers.

**Public surface:**
- `ToolCallRecord` (Pydantic BaseModel)
- `ExampleResult` (Pydantic BaseModel)
- `tool_called` (function)
- `input_matches` (function)
- `output_matches_pattern` (function)

**Outbound dependencies:**
- Third-party: `pydantic` (BaseModel)
- Stdlib: `re`, `typing.Any`
- First-party: *(none)*

**Inbound dependencies:**
- `src/energia/evals/runner.py`
- `tests/evals/test_runner.py`
- `tests/evals/test_scorers.py`

---

### `src/energia/solar/__init__.py` — 8 LOC

**Purpose:** Package-level docstring placeholder listing the four Sprint 3 sub-modules (`irradiance.py`, `sizing.py`, `payback.py`, `catalog.py`) that do not yet exist on disk.

**Public surface:** *(none)*

**Outbound dependencies:** *(none)*

**Inbound dependencies:**
- `tests/test_smoke.py`

---

### `src/energia/tariff/__init__.py` — 8 LOC

**Purpose:** Package-level docstring placeholder listing the four Sprint 2 sub-modules (`aneel.py`, `bandeira.py`, `branca.py`, `distributors.py`) that do not yet exist on disk.

**Public surface:** *(none)*

**Outbound dependencies:** *(none)*

**Inbound dependencies:**
- `tests/test_smoke.py`

---

### `src/energia/ui/__init__.py` — 5 LOC

**Purpose:** Package-level docstring describing the Streamlit chat shell entrypoint and how to run it.

**Public surface:** *(none)*

**Outbound dependencies:** *(none)*

**Inbound dependencies:**
- `tests/test_smoke.py`

---

### `src/energia/ui/streamlit_app.py` — 95 LOC

**Purpose:** Streamlit chat UI entrypoint — bootstraps session (mints user + conversation via `memory.py`), renders chat history, processes user input, invokes `GRAPH` with audit and budget callbacks, and persists the assistant response. Calls `load_dotenv()` at module level before other imports.

**Public surface:** *(none — script, not imported as a module)*

**Outbound dependencies:**
- Third-party: `dotenv` (load_dotenv — called at module level), `streamlit` (st), `langchain_core.messages` (HumanMessage — inline import inside `if` block)
- Stdlib: `uuid`, `typing.Any`
- First-party: `energia.chat.audit` (DuckDBAuditCallback), `energia.chat.budget` (TokenBudgetCallback, TokenBudgetExceeded), `energia.chat.graph` (GRAPH), `energia.chat.memory` (mint_conversation, mint_user, save_message, update_token_totals), `energia.db` (migrate)

**Inbound dependencies:** *(none — script entrypoint)*

---

## 2. Dependency Graph

First-party imports only. Nodes use abbreviated module names (prefix `energia.` omitted for readability).

```mermaid
graph LR
    subgraph pkg [" "]
        config
        db
        models
        bill["bill/__init__"]
        tariff["tariff/__init__"]
        solar["solar/__init__"]
    end

    subgraph chat
        chat_init["chat/__init__"]
        state["chat/state"]
        prompts["chat/prompts"]
        nodes["chat/nodes"]
        graph["chat/graph"]
        audit["chat/audit"]
        budget["chat/budget"]
        memory["chat/memory"]
        tools_init["chat/tools/__init__"]
        hello["chat/tools/hello"]
    end

    subgraph evals
        evals_init["evals/__init__"]
        scorers["evals/scorers"]
        runner["evals/runner"]
        run["evals/run"]
    end

    subgraph ui
        streamlit_app["ui/streamlit_app"]
    end

    db --> config
    nodes --> config
    nodes --> prompts
    nodes --> state
    nodes --> tools_init
    graph --> nodes
    graph --> state
    audit --> db
    budget --> config
    memory --> db
    tools_init --> hello
    runner --> config
    runner --> scorers
    runner -.->|lazy| graph
    run -.->|lazy| runner
    streamlit_app --> audit
    streamlit_app --> budget
    streamlit_app --> graph
    streamlit_app --> memory
    streamlit_app --> db
```

*Dashed arrows indicate lazy imports (inside function bodies).*

**Cycle check:** No cycles detected. The graph is a DAG. The lazy import from `runner` to `graph` does not create a cycle because `graph` (and its transitive deps) does not import from `evals.*`.

---

## 3. Test Coverage Map

| Test file | Covers |
|-----------|--------|
| `tests/__init__.py` | Package marker — no coverage |
| `tests/test_smoke.py` | `energia.__init__`, `energia.config`, `energia.db`, `energia.bill.__init__`, `energia.tariff.__init__`, `energia.solar.__init__`, `energia.chat.tools.__init__`, `energia.ui.__init__` |
| `tests/test_models.py` | `energia.models` (Bill, BillComposition) |
| `tests/chat/__init__.py` | Package marker — no coverage |
| `tests/chat/conftest.py` | Shared fixture using `energia.db.migrate` — not a test file |
| `tests/chat/test_state.py` | `energia.chat.state` (ChatState, add_messages integration) |
| `tests/chat/test_tools.py` | `energia.chat.tools.__init__` (ALL_TOOLS), `energia.chat.tools.hello` (HelloInput, hello_world_tool) |
| `tests/chat/test_graph.py` | `energia.chat.graph` (GRAPH), `energia.chat.nodes` (agent_node, route_after_agent via mock), `energia.chat.tools.hello` |
| `tests/chat/test_audit.py` | `energia.chat.audit` (DuckDBAuditCallback — on_tool_start, on_tool_end, on_tool_error, CPF redaction) |
| `tests/chat/test_budget.py` | `energia.chat.budget` (TokenBudgetCallback, TokenBudgetExceeded) |
| `tests/db/__init__.py` | Package marker — no coverage |
| `tests/db/test_migrations.py` | `energia.db` (migrate, MigrationIntegrityError) |
| `tests/db/test_bill_schema.py` | `energia.db` (migrate) + Sprint 1 bill schema migration column/default/index assertions |
| `tests/evals/__init__.py` | Package marker — no coverage |
| `tests/evals/test_runner.py` | `energia.evals.runner` (load_eval, run_example, score_attempt, run_capability, run_regression, EvalSkipped) |
| `tests/evals/test_scorers.py` | `energia.evals.scorers` (tool_called, input_matches, output_matches_pattern) |

**Modules with no dedicated test file:**
- `energia.chat.memory` — used indirectly via `conftest.py` fixtures but `mint_user`, `mint_conversation`, `save_message`, `update_token_totals` have no direct unit test assertions.
- `energia.evals.run` — CLI entrypoint; `main()` is not exercised by any test in `tests/evals/`.
- `energia.ui.streamlit_app` — no test file exists; `tests/ui/` directory does not exist.
- `energia.chat.prompts` — Protected Path; no test file exists.

---

## 4. Architectural Quanta

The entire application is a single deployable quantum: one Python package (`src/energia/`) backed by one local DuckDB file (`data/energia.duckdb`). The primary entry point is the Streamlit process (`uv run streamlit run src/energia/ui/streamlit_app.py`). Two additional CLI entry points share the same package and DuckDB file: the migration runner (`python -m energia.db migrate`) and the eval runner (`python -m energia.evals.run capability|regression`). There are no separate processes, no network services, no message queues, and no shared external state. The natural split points visible in the code are package boundaries (`chat/`, `bill/`, `tariff/`, `solar/`, `evals/`) and the `__init__.py` docstrings make the intended Sprint-by-Sprint population of each package explicit — but these are code-organisation boundaries, not process boundaries. Post-v1, the architecture doc (ADR-003) explicitly anticipates a move to PostgreSQL if multi-user access is required, which would introduce a separate server process.

---

## 5. Conventions Digest

### Hard Rules (HR-1 through HR-7)

- **HR-1:** All git commits executed manually by Daniel. Agents may not run `git add`, `git commit`, `git push`, or `gh pr create/merge`.
- **HR-2:** v1 scope is locked. No WhatsApp channel, live inverter integration, NILM, smart-home control, multi-tenant auth, or Group A tariffs.
- **HR-3:** Applied migrations are immutable. Changes to behaviour require a new timestamped SQL file, never an edit to an existing one. Enforced by SHA-256 hash stored in `schema_migrations`.
- **HR-4:** Agents may create new test files but may not edit existing `tests/**/test_*.py` without explicit Daniel approval plus a `docs/tech-debt.md` entry.
- **HR-5:** The chatbot never invents numbers. Every quantitative claim in a response must originate from a tool call. Numeric computation lives inside tool functions, never in the system prompt or free-text post-processing.
- **HR-6:** Brazilian bill PII (CPF, address, installation number) must not appear in logs, stdout, or external services. Store only in `data/energia.duckdb` (gitignored). A one-line entry in `docs/lgpd-log.md` is required whenever bill data is touched.
- **HR-7:** Every session has a 200,000-token budget. The orchestrator must warn at 50% and 80% and halt with a graceful error at 100%. Budget value lives in `src/energia/config.py`.

### Tech Stack

| Concern | Technology |
|---------|------------|
| Runtime | Python 3.11+ |
| Package manager | uv (uv.lock committed) |
| Package layout | `src/energia/` single package |
| LLM provider | Anthropic (`langchain-anthropic >= 0.2`, `anthropic >= 0.40`) |
| LLM model | `claude-sonnet-4-6` (default), `claude-haiku-4-5-20251001` (fallback) |
| Orchestration | LangGraph >= 0.2, langchain-core >= 0.3 |
| Data validation | Pydantic 2 / pydantic-settings 2 |
| Database | DuckDB >= 1.0 (local file) |
| UI | Streamlit >= 1.36 |
| HTTP / caching | requests >= 2.32, requests-cache >= 1.2 |
| Solar PV | pvlib >= 0.11, pandas >= 2.2 |
| Env config | python-dotenv >= 1.0 |
| Dev tools | pytest >= 8, pytest-mock >= 3, ruff >= 0.6, pyright >= 1.1 |

**Explicitly excluded from v1:** `langchain` meta-package, `langchain-community`, `langsmith`.

### Workflow Norms

- **TDD:** RED (failing test first, output shown) → GREEN (minimum implementation) → REFACTOR → commit pair (`test:` then `feat:`).
- **EDD:** Eval file defined before any AI code; BASELINE confirms failure; pass@3 ≥ 0.90 (capability) and pass^3 = 1.00 (regression) gates before ship.
- **Conventional commits:** `feat/fix/chore/docs/refactor/test/perf/ci` with scope in parentheses.
- **Branch naming:** `feature/*`, `data/*`, `quality/*`, `infra/*`, `bugfix/issue-<n>-<short>`, `chore/*`.
- **Migrations:** forward-only, lexicographic order, SHA-256 immutability check on every runner invocation.
- **No LangSmith:** LGPD constraint; local DuckDB audit trail via `DuckDBAuditCallback` is the substitute.
- **Protected Paths:** `migrations/2026*.sql`, `docs/adr/0*.md`, `tests/**/test_*.py` (edit-forbidden), `evals/**/*.jsonl` (append-only), `src/energia/chat/prompts.py` (SPEC + Daniel approval required).

### Language Conventions

- **PT-BR:** system prompt (`chat/prompts.py`), all chatbot responses, user-facing UI strings, tool docstrings that appear in LLM context.
- **English:** all Python identifiers, function names, class names, DB schema field names, docstrings in non-tool modules, test names, ADRs, PLAN.md, tech-debt entries.

---

## 6. Forward-Looking Constraints

What Task 1.3 (`parse_bill_image`) needs to support, and the open question each raises.

**Vision tool (`parse_bill_image` function in `src/energia/bill/parser.py`).**
This file does not yet exist. Per ADR-002, the tool wrapper belongs in `src/energia/chat/tools/bill.py` (a new file), and the domain function lives in `src/energia/bill/parser.py`. Open: `src/energia/chat/tools/__init__.py` currently hand-lists tools via explicit imports. The `__init__.py` comment enumerates Sprint 1–3 tools but contains no registry abstraction. The PLAN.md outline (`registry.register(...)`) and KICKOFF.md reference a decorator-based registry pattern that does not appear in the current code — which pattern governs how `parse_bill_image_tool` gets added to `ALL_TOOLS`?

**Hash-based idempotency (`sha256(image_bytes)`).**
The `bills.bill_hash TEXT NOT NULL UNIQUE` column exists in the DB (both migrations). The idempotency path (`SELECT … WHERE bill_hash = ?` → return existing if found) depends on a `bill_store` lookup function that does not yet exist (`src/energia/bill/store.py` is Task 1.4). Open: `parse_bill_image` (Task 1.3) depends on `bill_store.find_by_hash` from Task 1.4, but Task 1.3 precedes Task 1.4 in the Sprint 1 dependency graph — the PLAN.md outline shows `parse_bill_image` calling `bill_store.insert` and `bill_store.find_by_hash`. How the parser module sources these functions before Task 1.4 ships is not defined in the current code.

**Five failure modes (PLAN.md lines 655–664).**
Steps 2 (Anthropic 5xx → one retry with exponential backoff), 3 (Pydantic validation failure → log to `tool_calls.error`), 4 (confidence < 0.85 → `needs_user_confirmation = true`), and 5 (duplicate hash → `ON CONFLICT DO NOTHING`) all require code in `parser.py` that does not exist. Open: `ON CONFLICT DO NOTHING` on `bills.bill_hash` — DuckDB supports this syntax, but no existing test or code in the repo confirms it works with the current DuckDB version. The test `test_bill_schema_defaults_are_applied` does a plain `INSERT` without a conflict clause.

**Audit logging for hashed `installation_number` (LGPD posture).**
`DuckDBAuditCallback._scrub_pii` uses a regex (`\d{3}\.\d{3}\.\d{3}-\d{2}`) that matches CPF format only. The `installation_number` field (UC — Unidade Consumidora) is a numeric string whose format varies by distributor and is not covered by this pattern. When `parse_bill_image` stores a bill containing `installation_number`, the `tool_calls.input_json` written by the audit callback may contain the installation number unredacted. Open: which module is responsible for redacting `installation_number` before it reaches the audit log — the callback, the parser, or the tool wrapper?

**Real-bills-only test fixture strategy.**
PLAN.md Task 1.3 specifies `tests/bill/fixtures/` containing three sample bill PNGs (fictitious data). Neither `tests/bill/` nor `tests/bill/fixtures/` exists on disk. The `tests/chat/conftest.py` pattern (shared `tmp_db` fixture) is the only test fixture infrastructure currently present. Open: Task 1.3 requires creating a new test directory tree; the seven specified test functions in Task 1.3 all use `tmp_db` and `mocker` — does the new `tests/bill/conftest.py` reuse the same `tmp_db` fixture from `tests/chat/conftest.py`, or does it define its own?

---

## 7. Open Architecture Questions

Flags for Lanes 1–3. No answers or recommendations — questions only.

- Is `GRAPH = build_graph()` in `chat/graph.py` a module-level call that triggers `ChatAnthropic(...)` in `nodes.py` at import time? If so, does any code path import from `energia.chat.graph` without `load_dotenv()` having been called first — and is the TD-007 suppression the only guard against this?

- `nodes.py` constructs `_llm` and `_llm_with_tools` unconditionally at module scope. The `# type: ignore[call-arg]` comment on line 13 suppresses a pyright error on `ChatAnthropic(model_name=..., max_tokens_to_sample=...)`. What is the pyright complaint being suppressed, and does it indicate a parameter name mismatch with the current `langchain-anthropic` version?

- `chat/memory.py` has no dedicated unit test file. `mint_user`, `mint_conversation`, `save_message`, and `update_token_totals` are exercised indirectly via `conftest.py` seeding and `test_audit.py` inserts, but none of the four functions has a direct assertion against their return values or error paths in the test suite.

- `energia.evals.run` (the CLI module) has no test file. The `main()` function, argument parsing, and exit-code logic are untested by the current suite.

- `src/energia/ui/streamlit_app.py` has no test file, and `tests/ui/` does not exist. PLAN.md Task 1.6 introduces `tests/ui/test_streamlit_smoke.py`. Is there an implicit decision to defer all UI testing to Task 1.6, or is Sprint 0's UI coverage considered complete by the existing `test_import_ui` smoke test?

- `update_token_totals` in `memory.py` is called in `streamlit_app.py` at line 95 with `tokens_in=0, tokens_out=tokens_used`, where `tokens_used` is the combined input + output count from `ChatState`. This means `conversations.total_tokens_in` is never incremented by the current UI code. Is this intentional (single-column token tracking) or a gap between the DB schema's two-column design and the current call site?

- `DuckDBAuditCallback` opens a new DuckDB connection per `on_tool_start`, `on_tool_end`, and `on_tool_error` invocation. ADR-002 notes that LangGraph's `ToolNode` executes parallel tool calls and that the per-call connection pattern is the chosen mitigation for thread safety. Is there a test that exercises concurrent tool call execution, or is this only a stated design intention?

---

## 8. Methodology Notes

**What was read in this session:**
- All 23 `.py` files under `src/energia/` — each opened individually.
- All 16 `.py` files under `tests/` — each opened individually.
- `CLAUDE.md`, `docs/PLAN.md` (lines 1–995, covering Sprint 0 and Sprint 1 including Task 1.3 spec), `docs/architecture-plain.md`, `docs/adr/ADR-001-streamlit-only-v1.md`, `docs/adr/ADR-002-langgraph-orchestration.md`, `docs/adr/ADR-003-duckdb-local-file.md`, `docs/tech-debt.md`.
- Directory listings for `src/energia/`, `tests/`, `docs/`, `migrations/`.
- Import grep output across `src/energia/` for all first-party and third-party imports.

**What was not read (and why):**
- `docs/PLAN.md` beyond line 995 (Sprints 2–3) — out of scope for a Sprint 1 audit.
- `migrations/20260510_0001_initial_schema.sql` and `migrations/20260511_0001_bill_schema.sql` — content is visible through PLAN.md specifications and test assertions; files noted by name only per scope constraint.
- `evals/capability/hello_world.jsonl` and `evals/regression.jsonl` — out of scope per brief.
- `docs/KICKOFF.md`, `docs/CONTEXT.md`, `docs/INVENTORY.md`, `docs/MIGRATION.md`, `docs/GAPS.md` — outside the six required reads; noted as potentially relevant context for Lanes 1–3 (especially KICKOFF.md for the registry decorator pattern question in Section 6).
- `pyproject.toml` — not inventoried as a module; dependency versions confirmed via import grep across source files.
- Everything under `docs/reference/` (PDFs, XLSXes, CSVs), `notebooks/`, `data/`, `app_energia/`, `Dados/` — explicitly out of scope per brief.
- `data/energia.duckdb` — gitignored binary file; not readable.

**Limits:**
- LOC counts are raw `wc -l` output including blank lines and comment lines.
- Inbound dependency lists are derived from a grep of `from energia.` and `import energia.` across `src/energia/`; they may not reflect indirect imports that arise at runtime through dynamic loading.
- The `evals/capability/hello_world.jsonl` example content (cited in PLAN.md) was not verified against the actual file on disk.
