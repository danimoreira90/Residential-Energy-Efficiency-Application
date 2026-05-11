# PLAN.md — Residential Energy Efficiency Application

**Execution contract:** For agentic workers: REQUIRED: Use spec-driven-development for every task. Read `AGENTS.md` (or `CLAUDE.md` if Claude Code) and `CONTEXT.md` before any work. Architecture blueprint and tool-registry pattern: `KICKOFF.md`.

---

## Roadmap to v1

```
Sprint 0  Foundation               (~1 week)  ← we are here
Sprint 1  Bill Spine               (~1 week)
Sprint 2  Tariff Awareness         (~1 week)
Sprint 3  Solar Feasibility        (~1 week)
                                   ─────────
                                   v1 ships
```

After v1: inverter integration (Growatt-first), WhatsApp channel, anomaly alerts, NILM disaggregation, multi-user auth. All explicitly out of v1 scope per HR-2.

---

## Sprint 0 — Foundation

**Goal:** turn the existing notebook-heavy repo into a clean Python package with a working chatbot loop calling one stub tool. By end of Sprint 0: `uv run streamlit run` opens a chat where the user can type, the orchestrator calls a hello-world tool, and the response renders. No real features yet, but the spine is real.

---

### Dependency Graph — Sprint 0

```
Task 0.1 (Inventory existing notebooks — read-only)
  └── Task 0.2 (Migration plan — read + plan, no code changes)
        └── Task 0.3 (Scaffold src/energia/ package + tooling)
              ├── Task 0.4 (First DuckDB schema migration: users, conversations, messages, tool_calls)
              └── Task 0.5 (Tool registry + orchestrator + stub tool + Streamlit chat shell)
                    └── Task 0.6 (Capability eval scaffolding + regression eval skeleton)
```

---

## Tasks — Sprint 0

---

### Task 0.1 — Inventory existing notebooks (read-only)

**Owner:** doc-engineer
**Depends on:** nothing — repo is at HEAD, ~95% Jupyter.
**Branch:** `quality/inventory-notebooks`

#### Goal

Produce `INVENTORY.md` and `GAPS.md` at repo root. Read every `.ipynb` and `.py` file. Do not change any code.

#### Deliverables

- `INVENTORY.md` — one section per file containing: path, size, two-sentence summary, inputs (data files / APIs / env vars), outputs (data / plots / models), quality flags (dead cells, hardcoded paths, secrets, duplicated logic), reusability score (keep / refactor / drop) with justification.
- `GAPS.md` — production gaps: package structure, tests, types, error handling, logging, CI, deployment, missing data integrations (ANEEL, NASA POWER, bill parser), missing UX (chatbot, persistent state).

#### Verification

```bash
# Files exist and are non-trivial
test -f INVENTORY.md && wc -l INVENTORY.md
test -f GAPS.md && wc -l GAPS.md

# Each notebook is referenced
for nb in $(find . -name '*.ipynb' -not -path './.*'); do
  grep -q "$(basename $nb)" INVENTORY.md || echo "MISSING: $nb"
done
# Expected: no MISSING output
```

#### Anti-cheat

- Do not skip notebooks because they look duplicated. Document the duplication.
- Be specific — file paths and cell numbers, not "various cells".
- "Reusability: drop" requires a one-line justification.

---

### Task 0.2 — Migration plan (read + plan, no code changes)

**Owner:** planner
**Depends on:** Task 0.1
**Branch:** `quality/migration-plan`

#### Goal

Produce `MIGRATION.md` mapping every reusable piece of existing code to its new home in `src/energia/`. Do not move code.

#### Deliverables

`MIGRATION.md` containing:

- Per-notebook table: cell range → target module → required transformations (typing, error handling, config extraction).
- Per-function table: existing signature → new signature → notes.
- Drop list with one-line justification per item.

#### Target structure (reference)

```
src/energia/
├── __init__.py
├── config.py                # Pydantic Settings
├── models.py                # Bill, User, SolarSite, TariffSnapshot
├── db.py                    # DuckDB session + migrations runner
├── bill/
│   ├── parser.py            # Vision-based extraction (Claude)
│   ├── store.py             # Persist + retrieve bills
│   └── analysis.py          # Period comparison, anomaly detection
├── tariff/
│   ├── aneel.py             # ANEEL Open Data API client (cached)
│   ├── bandeira.py          # Current flag + 12-month history
│   ├── branca.py            # Tarifa Branca simulation
│   └── distributors.py      # Per-distributor quirks
├── solar/
│   ├── irradiance.py        # NASA POWER + Forecast.Solar clients
│   ├── sizing.py            # pvlib weather-to-power
│   ├── payback.py           # ROI given user's tariff + Lei 14.300
│   └── catalog.py           # Common panels/inverters in BR
├── chat/
│   ├── orchestrator.py      # Anthropic SDK + tool loop
│   ├── tools.py             # Registry decorator
│   ├── prompts.py           # System prompt in PT-BR (PROTECTED)
│   └── memory.py            # Conversation history persistence
└── ui/
    └── streamlit_app.py     # st.chat_message + sidebar
```

#### Verification

Plan approved by Daniel before Task 0.3 begins. No code changes in this task.

---

### Task 0.3 — Scaffold src/energia/ package + tooling

**Owner:** builder
**Depends on:** Task 0.2 approved
**Branch:** `chore/scaffold-package`

#### Goal

Bring up the package skeleton, dev tooling, and CI pre-flight. After this task `uv run pytest` exits zero (one trivial passing test per module).

#### Files to create

```
pyproject.toml                       # uv-managed
uv.lock                              # generated by uv sync
ruff.toml                            # line-length 100, target py311
pyrightconfig.json                   # strict mode
.env.example                         # ANTHROPIC_API_KEY placeholder + others
.gitignore                           # data/, *.duckdb, .env, __pycache__/
src/energia/__init__.py
src/energia/config.py                # Pydantic Settings
src/energia/db.py                    # DuckDB connection helper
src/energia/{bill,tariff,solar,chat,ui}/__init__.py
tests/__init__.py
tests/test_smoke.py                  # one assertion: import energia works
docs/agentic-engineering/README.md   # placeholder pointing to AGENTS.md
docs/adr/ADR-001-streamlit-only-v1.md
docs/adr/ADR-002-tool-registry-pattern.md
docs/adr/ADR-003-duckdb-local-file.md
docs/tech-debt.md
docs/lgpd-log.md
docs/sessions/.gitkeep
```

#### Dependencies (in pyproject.toml)

```toml
[project]
dependencies = [
  "langgraph>=0.2",
  "langchain-core>=0.3",
  "langchain-anthropic>=0.2",
  "anthropic>=0.40",
  "pydantic>=2.7",
  "pydantic-settings>=2.4",
  "pvlib>=0.11",
  "pandas>=2.2",
  "duckdb>=1.0",
  "streamlit>=1.36",
  "requests>=2.32",
  "requests-cache>=1.2",
  "python-dotenv>=1.0",
]

[tool.uv.dev-dependencies]
dev = [
  "pytest>=8",
  "pytest-mock>=3",
  "responses>=0.25",
  "ruff>=0.6",
  "pyright>=1.1",
]
```

**Explicitly NOT included:** `langchain` (the meta-package), `langchain-community`, `langsmith`. Adopting any of these later requires a new ADR.

#### Verification

```bash
uv sync
# Expected: locks dependencies, exits zero

uv run pytest -q
# Expected: 5 passed (one smoke test per top-level module)

uv run ruff check .
# Expected: All checks passed!

uv run pyright
# Expected: 0 errors, 0 warnings, 0 informations
```

#### Anti-cheat

- Do NOT skip pyright by setting `strict = false`. Strict from day one.
- Do NOT add a dependency without the corresponding ADR file.
- Test files under `tests/test_smoke.py` must actually import the modules — `assert True` is not a smoke test.

---

### Task 0.4 — First DuckDB schema migration

**Owner:** db-architect
**Depends on:** Task 0.3
**Branch:** `data/initial-schema`

#### Goal

Create the foundational tables: `users`, `conversations`, `messages`, `tool_calls`, `bills` (skeleton — full bill schema arrives in Sprint 1). After this task, `uv run python -m energia.db migrate` creates the schema in `data/energia.duckdb` and an integration test confirms the tables exist.

#### File: `migrations/20260510_0001_initial_schema.sql`

```sql
-- Migration: 20260510_0001_initial_schema
-- Foundational tables for users, conversations, message log, tool call audit, bills skeleton.
-- HR-3: this file is immutable once applied.

CREATE TABLE IF NOT EXISTS users (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  session_id      TEXT         NOT NULL UNIQUE,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  display_name    TEXT,
  -- LGPD: no PII at user level in v1; bill-level PII handled in Sprint 1
);

CREATE TABLE IF NOT EXISTS conversations (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  user_id         UUID         NOT NULL REFERENCES users(id),
  started_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  ended_at        TIMESTAMPTZ,
  total_tokens_in  INTEGER     NOT NULL DEFAULT 0,
  total_tokens_out INTEGER     NOT NULL DEFAULT 0,
);

CREATE TABLE IF NOT EXISTS messages (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  conversation_id UUID         NOT NULL REFERENCES conversations(id),
  role            TEXT         NOT NULL CHECK (role IN ('user', 'assistant')),
  content         TEXT         NOT NULL,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  message_id      UUID         NOT NULL REFERENCES messages(id),
  tool_name       TEXT         NOT NULL,
  input_json      TEXT         NOT NULL,
  output_json     TEXT,
  error           TEXT,
  duration_ms     INTEGER,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
);

CREATE TABLE IF NOT EXISTS bills (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  user_id         UUID         NOT NULL REFERENCES users(id),
  bill_hash       TEXT         NOT NULL UNIQUE,
  period          TEXT         NOT NULL,    -- YYYY-MM
  distributor     TEXT         NOT NULL,
  consumption_kwh NUMERIC(10,2) NOT NULL,
  total_brl       NUMERIC(10,2) NOT NULL,
  bandeira        TEXT,
  raw_extraction  JSON         NOT NULL,    -- full Bill model as JSON, expanded in Sprint 1
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_message ON tool_calls(message_id);
CREATE INDEX IF NOT EXISTS idx_bills_user_period ON bills(user_id, period);
```

#### Migration runner: `src/energia/db.py`

A simple forward-only runner. Reads `migrations/*.sql` in lexicographic order, tracks applied ones in a `schema_migrations` table, applies new ones in transactions. Provides `migrate()` and `connect()` functions. ~80 lines.

#### Verification

```bash
# Test FIRST (RED — must fail before implementation)
uv run pytest tests/db/test_migrations.py -q
# Expected before impl: FAIL — migrate() not implemented

# After implementation (GREEN):
uv run python -m energia.db migrate
# Expected stdout: "Applied 1 migration: 20260510_0001_initial_schema"

uv run pytest tests/db/test_migrations.py -q
# Expected: 4 passed
#   - test_migrate_creates_tables
#   - test_migrate_is_idempotent
#   - test_migrate_records_applied_migration
#   - test_migrate_rejects_modified_applied_migration

# Confirm tables exist in DuckDB
uv run python -c "
import duckdb
con = duckdb.connect('data/energia.duckdb')
print(con.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name\").fetchall())
"
# Expected: [('bills',), ('conversations',), ('messages',), ('schema_migrations',), ('tool_calls',), ('users',)]
```

#### Anti-cheat

- Migration is **immutable** after this task ships (HR-3). Bill schema gaps in Sprint 1 = new migration with new timestamp, never edit `20260510_0001_*`.
- The test `test_migrate_rejects_modified_applied_migration` exists specifically to enforce HR-3 — it computes a hash of the migration file content and refuses to apply if hash changes from what's stored.

---

### Task 0.5 — LangGraph chat spine + stub tool + Streamlit shell

**Owner:** ai-ml-engineer
**Depends on:** Task 0.4
**Branch:** `feature/chat-spine`

#### Goal

End-to-end chatbot spine using LangGraph: user types in Streamlit → `GRAPH.invoke` runs the agent/tools loop → `hello_world` tool executes → response renders. HR-5 audit trail (every tool call logged to DuckDB via `DuckDBAuditCallback`) and HR-7 token budget (enforced via `TokenBudgetCallback`) are wired from day one.

#### Files to create

```
src/energia/chat/state.py             # ChatState TypedDict
src/energia/chat/nodes.py             # agent_node, tool_node, route_after_agent
src/energia/chat/graph.py             # build_graph() + GRAPH singleton
src/energia/chat/tools/__init__.py    # ALL_TOOLS list
src/energia/chat/tools/hello.py       # Sprint 0 stub @tool
src/energia/chat/prompts.py           # System prompt in PT-BR (PROTECTED — HR-4)
src/energia/chat/audit.py             # DuckDBAuditCallback (HR-5)
src/energia/chat/budget.py            # TokenBudgetCallback + TokenBudgetExceeded (HR-7)
src/energia/chat/memory.py            # Conversation persistence helpers
src/energia/ui/streamlit_app.py       # st.chat_message + session-id minting
tests/chat/test_state.py              # State updates compose correctly via add_messages
tests/chat/test_tools.py              # @tool schema + invocation
tests/chat/test_graph.py              # Mocked ChatAnthropic, full loop
tests/chat/test_audit.py              # Callback writes to tool_calls table
tests/chat/test_budget.py             # Callback raises TokenBudgetExceeded at threshold
```

#### Stub tool

```python
# src/energia/chat/tools/hello.py
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class HelloInput(BaseModel):
    name: str = Field(description="Nome para cumprimentar")

@tool("hello_world", args_schema=HelloInput)
def hello_world_tool(name: str) -> dict:
    """Retorna um cumprimento amigável. Ferramenta de demonstração — será
    removida no Sprint 1 quando ferramentas reais de análise de conta entrarem."""
    return {"greeting": f"Olá, {name}!", "tool_version": "v0.0-stub"}
```

```python
# src/energia/chat/tools/__init__.py
from energia.chat.tools.hello import hello_world_tool

ALL_TOOLS = [hello_world_tool]
```

#### System prompt (initial — full v1 prompt arrives in Sprint 1)

```python
# src/energia/chat/prompts.py
SYSTEM_PROMPT = """\
Você é um assistente de eficiência energética residencial no Brasil.

Regras inegociáveis:
1. Você nunca inventa números. Toda afirmação quantitativa vem de uma chamada de
   ferramenta. Se não houver ferramenta disponível, diga que não sabe.
2. Sempre cite unidade (kWh, R$, %, meses) e período de referência.
3. Responda em português brasileiro, tom amigável e direto.

Esta é uma versão inicial do produto (Sprint 0). Diga ao usuário que você ainda
está sendo construído e oferece poucas funcionalidades.
"""
```

#### Tests (RED first — must fail before impl)

```python
# tests/chat/test_graph.py
def test_graph_runs_single_turn_with_no_tool_calls(mocker):
    """Mocked LLM returns plain AIMessage — graph ends after agent node."""

def test_graph_runs_tool_use_loop(mocker):
    """Mocked LLM requests hello_world; graph routes through tool_node then back."""

def test_graph_accumulates_tokens_across_turns(mocker):
    """Each agent_node call adds usage_metadata to state.tokens_used."""

def test_graph_handles_tool_error_gracefully(mocker):
    """Tool raises — ToolNode returns ToolMessage with error; agent narrates."""

# tests/chat/test_audit.py
def test_audit_callback_writes_tool_call_to_duckdb(tmp_db, mocker):
    """on_tool_end inserts a row in tool_calls with name, input, output."""

def test_audit_callback_logs_tool_error(tmp_db, mocker):
    """on_tool_error inserts a row with error column populated."""

def test_audit_callback_does_not_log_pii(tmp_db, mocker, caplog):
    """HR-6 guard: tool_calls.input_json must not contain raw image bytes."""

# tests/chat/test_budget.py
def test_budget_callback_raises_at_threshold(mocker):
    """on_llm_end with cumulative tokens > budget → TokenBudgetExceeded."""

def test_budget_callback_warns_at_50_percent(mocker, caplog):
    """on_llm_end at 50% of budget → WARNING log."""
```

#### Verification

```bash
uv run pytest tests/chat/ -q
# Expected: ≥ 11 passed (state, tools, graph×4, audit×3, budget×2)

uv run pyright
# Expected: 0 errors

# Manual smoke test
uv run streamlit run src/energia/ui/streamlit_app.py
# Open http://localhost:8501
# Type "Oi, me chama de Daniel"
# Expected: chatbot responds in PT-BR, calls hello_world, narrates result

# Confirm HR-5 audit and HR-7 token accounting
uv run python -c "
import duckdb
con = duckdb.connect('data/energia.duckdb')
print('Conversations:', con.execute('SELECT COUNT(*) FROM conversations').fetchone()[0])
print('Tool calls:', con.execute(\"SELECT tool_name, COUNT(*) FROM tool_calls GROUP BY tool_name\").fetchall())
print('Tokens:', con.execute(\"SELECT total_tokens_in + total_tokens_out FROM conversations ORDER BY started_at DESC LIMIT 1\").fetchone())
"
# Expected: ≥ 1 conversation, ≥ 1 hello_world tool call, non-zero token count
```

#### Anti-cheat

- Mock `ChatAnthropic` and `_llm_with_tools.invoke` in tests; do NOT hit the real API in CI (cost + flakiness). Evals (Task 0.6) are the one place real API calls run, gated behind `ANTHROPIC_API_KEY`.
- Do NOT short-circuit the graph in tests. Test the actual conditional-edge routing.
- The `TokenBudgetCallback` test must verify against fake `usage_metadata` with non-zero counts — `mocker.patch` that returns `{"input_tokens": 0}` is not a real test of the threshold.
- `test_audit_callback_does_not_log_pii` is non-negotiable. If your callback's `input_json` serialization includes raw image bytes, fix the callback (truncate / hash / omit), not the test.
- LangGraph 0.2+ has `langgraph.checkpoint.memory.MemorySaver` for in-process state. v1 uses this. Do NOT scaffold `SqliteSaver` or any persistent checkpointer — that's a Sprint 2 question if it comes up at all.

---

### Task 0.6 — Capability eval scaffolding + regression eval skeleton

**Owner:** qa-champion
**Depends on:** Task 0.5
**Branch:** `quality/eval-scaffolding`

#### Goal

Eval infrastructure ready before any real chatbot capability ships. After this task, `uv run python -m energia.evals.run capability` runs against the stub tool and reports pass@3.

#### Files to create

```
evals/__init__.py
evals/runner.py                      # Driver: load JSONL, send through orchestrator, score
evals/scorers.py                     # Scorers: tool_called, output_matches_pattern
evals/capability/hello_world.jsonl   # 5 examples for the stub tool
evals/regression.jsonl               # Empty — populated as tools ship
src/energia/evals/run.py             # CLI entrypoint
tests/evals/test_runner.py
tests/evals/test_scorers.py
```

#### Eval JSONL example

```jsonl
{"name": "hello_simple", "input_messages": [{"role": "user", "content": "Oi, me chama de Daniel"}], "expected_tool": "hello_world", "expected_input_match": {"name": "Daniel"}, "expected_output_pattern": "Olá.*Daniel"}
```

#### Verification

```bash
uv run python -m energia.evals.run capability hello_world
# Expected output:
#   Running 5 examples × 3 attempts = 15 calls
#   Capability pass@3: 1.00 (5/5)
#   Per-example: hello_simple OK, hello_with_typo OK, ...

uv run python -m energia.evals.run regression
# Expected: "No regression examples yet — skipping."
```

#### Anti-cheat

- Real Anthropic API calls (this is the one place we hit the API in CI — gate behind ANTHROPIC_API_KEY env). Skip cleanly when not set; do NOT mock or fake pass.
- Pass@3 means the capability passes ≥ 2 of 3 attempts (≥ 0.67 = 2 of 3 = pass per example; aggregate ≥ 0.90). Document the math in `evals/runner.py`.

---

### Execution Order — Sprint 0

```
Day 1:  Task 0.1 (Inventory)  → INVENTORY.md, GAPS.md committed by Daniel
Day 2:  Task 0.2 (Migration plan)  → MIGRATION.md committed by Daniel
Day 3:  Task 0.3 (Scaffold)  → uv sync, pytest, ruff, pyright all green
Day 4:  Task 0.4 (First migration)  → schema in DuckDB, 4 tests passing
Day 5:  Task 0.5 (Chat spine)  → end-to-end working, 8 tests passing
Day 6:  Task 0.6 (Eval scaffolding)  → 1 capability eval running
Day 7:  Integration sanity, commit baseline as v0.1.0 tag
```

---

### Sprint 0 Exit Criteria (All must pass with actual output)

- [ ] `uv sync` exits zero
- [ ] `uv run ruff check .` — All checks passed!
- [ ] `uv run pyright` — 0 errors, 0 warnings, 0 informations
- [ ] `uv run pytest -q` — all passing (≥ 12 tests)
- [ ] `uv run python -m energia.db migrate` — applies 1 migration cleanly
- [ ] DuckDB has tables: users, conversations, messages, tool_calls, bills, schema_migrations
- [ ] `uv run streamlit run src/energia/ui/streamlit_app.py` — opens chat, "hello" turn works end-to-end
- [ ] Every tool call is logged in `tool_calls` table
- [ ] `uv run python -m energia.evals.run capability hello_world` — pass@3 = 1.00
- [ ] ADRs 001, 002, 003 written and committed
- [ ] INVENTORY.md and MIGRATION.md committed
- [ ] No notebook is imported by any module under `src/energia/`

---

### Anti-Cheat Checkpoints — Sprint 0

After each task, before declaring done:

1. Run `uv run pytest -q` — paste FULL output (test count + names + timings).
2. Run `uv run pyright` — paste output (must be empty / zero errors).
3. Run `uv run ruff check .` — paste output.
4. Show `git diff --cached` — full output, not summary.
5. Show what was added to `pyproject.toml` if anything (HR per-dep ADR rule).
6. List any Protected Path touched.
7. If a test fails: STOP. Do not skip, soften, or mock-the-world. Diagnose, propose fix to PRODUCTION code, wait for Daniel.

---

### Schema Notes for Sprint 0 Implementors

1. **DuckDB UUID:** native `UUID` type with `DEFAULT uuid()` — DuckDB's `uuid()` is v4. Don't rely on Postgres-style `gen_random_uuid()`.
2. **TIMESTAMPTZ:** DuckDB stores TIMESTAMPTZ as UTC internally. Convert to `America/Sao_Paulo` only at the UI layer.
3. **JSON columns:** DuckDB has native `JSON` type since 0.9. Use it for `bills.raw_extraction` and `tool_calls.input_json/output_json`. Pydantic models serialize via `model_dump_json()`.
4. **No FK enforcement by default in older DuckDB versions:** verify your DuckDB version (≥ 1.0) honors `REFERENCES`. If not, add a CHECK or app-level validation.
5. **Migration runner stores file hash:** the `schema_migrations` table records `(name, sha256, applied_at)`. On startup, the runner refuses to proceed if a recorded migration's file content has changed. This enforces HR-3.

---

## Sprint 1 — Bill Spine

**Goal:** the chatbot can ingest a Brazilian energy bill (photo or PDF), extract structured data with vision, store it, and answer questions about it. By end of Sprint 1: a logged-in user can upload three months of bills and ask "why was last month higher?" — and get a tool-grounded answer.

---

### Architecture — Sprint 1

#### Bill data model (SDD spec)

```python
# src/energia/models.py — Bill model
from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal

class BillComposition(BaseModel):
    """Breakdown of a bill's R$ total into regulatory components."""
    tusd: Decimal = Field(description="Tarifa de Uso do Sistema de Distribuição (R$)")
    te: Decimal = Field(description="Tarifa de Energia (R$)")
    icms: Decimal = Field(description="ICMS state tax (R$)")
    pis: Decimal | None = Field(default=None, description="PIS federal tax (R$)")
    cofins: Decimal | None = Field(default=None, description="COFINS federal tax (R$)")
    cosip: Decimal | None = Field(default=None, description="Public lighting contribution (R$)")
    bandeira_surcharge: Decimal | None = Field(default=None, description="Bandeira tarifária surcharge (R$)")
    other: Decimal = Field(default=Decimal("0"), description="Anything else not classified")

class Bill(BaseModel):
    """A single monthly energy bill."""
    distributor: str = Field(description="Distribuidora name, e.g. 'Enel Rio'")
    installation_number: str = Field(description="Número da instalação / UC")
    period: str = Field(description="YYYY-MM reference month")
    issue_date: date = Field(description="Data de emissão")
    due_date: date = Field(description="Data de vencimento")
    consumption_kwh: Decimal = Field(description="Total kWh consumed in period")
    tariff_group: str = Field(description="B1, B2, B3, etc.")
    modalidade: str = Field(description="Convencional or Branca")
    bandeira: str | None = Field(default=None, description="Verde, Amarela, Vermelha 1, Vermelha 2, or null")
    total_brl: Decimal = Field(description="Total R$ to pay")
    composition: BillComposition
    confidence: float = Field(ge=0, le=1, description="Vision extraction confidence, 0-1")
    needs_user_confirmation: bool = Field(description="True if any field has confidence < 0.85")
```

#### CAP statements

| Table | CAP | Reason | Under partition |
|-------|-----|--------|-----------------|
| `bills` | **CP** | DuckDB local. Bill totals are financial data — consistency > availability. UNIQUE on `bill_hash` enforced at DB level. | Writes fail with error. Reads always succeed (local DB). |
| `bill_periods` (cached aggregations) | **AP** | Computed view, materializable. Stale reads tolerable. | Reads return last good value. |
| Vision-extracted bills | **CP** | If extraction confidence < 0.85, bill is stored with `needs_user_confirmation = true` and the chatbot MUST ask before using values. | Extraction failure = no bill stored, user is informed. |

#### Idempotency Strategy — `parse_bill_image`

**Mechanism:** `bill_hash = sha256(image_bytes)`. Two calls with the same image produce the same hash → existing bill is returned without re-calling the vision API.

```
User uploads image
   │
   ├── compute bill_hash = sha256(bytes)
   ├── SELECT * FROM bills WHERE user_id = ? AND bill_hash = ?
   │
   ├── if exists: return existing Bill (no API call, no token cost)
   ├── else:
   │     ├── call Anthropic vision with structured-extraction prompt
   │     ├── validate response against Bill Pydantic model
   │     ├── INSERT INTO bills (..., bill_hash) ON CONFLICT (bill_hash) DO NOTHING
   │     └── return Bill
   └── log every call in tool_calls
```

**Why not LLM-side caching:** the Anthropic prompt-cache helps, but image inputs aren't cached the same way text is. Hash-and-compare at our level is O(1) DB lookup and zero API cost.

#### Failure Modes — `parse_bill_image`

| Step | Failure | Consequence | Compensating Action |
|------|---------|-------------|---------------------|
| 1. SHA-256 hash | image bytes unreadable (corrupt upload) | No call. Safe. | Return error to UI; ask user to re-upload. |
| 2. Vision call | Anthropic 5xx / timeout | No bill stored. | Retry once with exponential backoff. If still failing, return error and DO NOT store partial data. |
| 3. Pydantic validation | Vision returned malformed JSON | No bill stored. | Log full response in `tool_calls.error`, return user-friendly "couldn't read your bill, can you try a clearer photo?" |
| 4. Confidence < 0.85 on key field | Extraction may be wrong | Bill stored with `needs_user_confirmation = true`. | Chatbot asks user to confirm key fields before any analysis tool runs. |
| 5. INSERT bill | Duplicate hash | Existing returned. | ON CONFLICT DO NOTHING; SELECT existing. No data loss. |

---

### Dependency Graph — Sprint 1

```
Task 1.1 (Bill schema migration)
  └── Task 1.2 (Bill + BillComposition Pydantic models)
        └── Task 1.3 (parse_bill_image — vision tool)
              ├── Task 1.4 (store_bill, list_user_bills, get_bill — CRUD tools)
              └── Task 1.5 (compare_bill_periods — analysis tool)
                    └── Task 1.6 (Streamlit upload widget + chat integration)
                          └── Task 1.7 (Capability + regression evals for bill flow)
```

---

## Tasks — Sprint 1

---

### Task 1.1 — Bill schema migration

**Owner:** db-architect
**Depends on:** Task 0.4
**Branch:** `data/bill-schema`

#### File: `migrations/<NEW_TIMESTAMP>_bill_schema.sql`

(Use a fresh timestamp at task time — never edit applied 20260510_* migration.)

Add columns and tables not present in 20260510_0001:

```sql
-- Migration: <NEW_TIMESTAMP>_bill_schema
-- Adds bill detail columns + bill_periods materialized view.

ALTER TABLE bills ADD COLUMN installation_number TEXT;
ALTER TABLE bills ADD COLUMN issue_date DATE;
ALTER TABLE bills ADD COLUMN due_date DATE;
ALTER TABLE bills ADD COLUMN tariff_group TEXT;
ALTER TABLE bills ADD COLUMN modalidade TEXT;
ALTER TABLE bills ADD COLUMN composition_json JSON NOT NULL DEFAULT '{}';
ALTER TABLE bills ADD COLUMN confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0;
ALTER TABLE bills ADD COLUMN needs_user_confirmation BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE bills ADD COLUMN confirmed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_bills_distributor_period ON bills(distributor, period);
```

#### Verification

```bash
uv run python -m energia.db migrate
# Expected: "Applied 1 migration: <NEW_TIMESTAMP>_bill_schema"

uv run pytest tests/db/test_bill_schema.py -q
# Expected: 3 passed
```

---

### Task 1.2 — Bill Pydantic models

**Owner:** backend-expert
**Depends on:** Task 1.1
**Branch:** `feature/bill-models`

Implement `Bill` and `BillComposition` exactly per the SDD spec above. Add tests for: required fields, decimal precision, period format `YYYY-MM`, confidence bounds.

#### Verification

```bash
uv run pytest tests/test_models.py::TestBill -q
# Expected: 8 passed (one per validation rule)
```

---

### Task 1.3 — `parse_bill_image` vision tool

**Owner:** ai-ml-engineer
**Depends on:** Task 1.2
**Branch:** `feature/bill-parser`

#### Goal

Vision-based extraction from a Brazilian bill image. Hash-and-cache for idempotency. Fail-closed on validation errors.

#### Files

```
src/energia/bill/parser.py           # parse_bill_image function
tests/bill/test_parser.py            # mocked Anthropic responses
tests/bill/fixtures/                 # 3 sample bill PNGs (Enel RJ, Light, CPFL — fictitious data)
```

#### Implementation outline

```python
@registry.register(
    name="parse_bill_image",
    description=(
        "Lê uma foto ou PDF de uma conta de luz brasileira e extrai os campos "
        "estruturados: distribuidora, número da instalação, período, consumo em "
        "kWh, valor total em R$, bandeira tarifária, e a composição de tributos. "
        "Use sempre que o usuário enviar uma imagem de conta. Pergunte ao usuário "
        "para confirmar valores quando confidence < 0.85."
    ),
    input_model=ParseBillInput,
)
def parse_bill_image(inp: ParseBillInput) -> dict:
    bill_hash = sha256(inp.image_bytes).hexdigest()
    existing = bill_store.find_by_hash(inp.user_id, bill_hash)
    if existing:
        return existing.model_dump()
    response = anthropic.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=2000,
        system=BILL_EXTRACTION_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": inp.media_type, "data": ...}},
                {"type": "text", "text": "Extraia os campos da conta nesta imagem em JSON."},
            ],
        }],
    )
    bill = Bill.model_validate_json(_extract_json(response))
    bill_store.insert(user_id=inp.user_id, bill=bill, bill_hash=bill_hash)
    return bill.model_dump()
```

#### Tests (RED first — must fail before impl)

```python
def test_parse_bill_returns_existing_when_hash_matches(tmp_db, mocker)
def test_parse_bill_calls_vision_when_new(tmp_db, mocker)
def test_parse_bill_validates_response_shape(tmp_db, mocker)
def test_parse_bill_sets_needs_confirmation_when_low_confidence(tmp_db, mocker)
def test_parse_bill_does_not_store_on_validation_error(tmp_db, mocker)
def test_parse_bill_handles_anthropic_5xx_with_one_retry(tmp_db, mocker)
def test_parse_bill_does_not_log_image_bytes_or_cpf(tmp_db, mocker, caplog)  # HR-6
```

#### Verification

```bash
uv run pytest tests/bill/test_parser.py -q
# Expected before impl: 7 failed
# After impl: 7 passed
```

#### Anti-cheat / HR-6

- The `caplog` test asserts no PII reaches Python logging. If you cannot make this test pass with your logging setup, the logging setup is wrong, not the test.

---

### Task 1.4 — `store_bill`, `list_user_bills`, `get_bill` CRUD tools

**Owner:** backend-expert
**Depends on:** Task 1.3
**Branch:** `feature/bill-crud`

Three tools registered. `store_bill` is internal-only (not LLM-callable, used by `parse_bill_image`). `list_user_bills` and `get_bill` are LLM-callable.

#### Verification

```bash
uv run pytest tests/bill/test_store.py -q
# Expected: 6 passed (insert, dedupe-by-hash, list-by-user, get-by-id, period-filter, time-range-filter)
```

---

### Task 1.5 — `compare_bill_periods` analysis tool

**Owner:** ai-ml-engineer
**Depends on:** Task 1.4
**Branch:** `feature/bill-comparison`

#### Goal

Given two periods, decompose the delta into: consumption change, tariff revision (TE+TUSD changed), bandeira change, tax change, other. The chatbot uses this to answer "why was my bill higher last month?"

#### Decomposition formula

```
ΔTotal = (kWh_b - kWh_a) × tariff_a            ← consumption effect
       + kWh_b × (tariff_b - tariff_a)          ← tariff effect
       + (bandeira_b_R$ - bandeira_a_R$)        ← bandeira effect
       + (tax_b - tax_a) — already partially in above
       + residual                                ← other
```

The output is a structured dict with per-component R$ contribution + a one-sentence narrative seed (NOT a full sentence — the LLM does the narration per HR-5).

#### Tests

```python
def test_compare_pure_consumption_change()
def test_compare_pure_tariff_change()
def test_compare_pure_bandeira_change()
def test_compare_combined_effects()
def test_compare_returns_components_in_brl_not_kwh()
def test_compare_handles_missing_bandeira_in_one_period()
```

#### Verification

```bash
uv run pytest tests/bill/test_analysis.py -q
# Expected: 6 passed
```

---

### Task 1.6 — Streamlit upload widget + chat integration

**Owner:** frontend-expert
**Depends on:** Task 1.5
**Branch:** `feature/streamlit-bill-flow`

#### Goal

User can drag-drop a bill image or PDF in the Streamlit sidebar. On upload, the chatbot greets the user with the extraction summary and asks for confirmation if needed. After confirmation, the user can ask comparison questions in chat.

#### Files

```
src/energia/ui/streamlit_app.py       # update with sidebar uploader
src/energia/ui/components/bill_card.py  # display parsed bill
tests/ui/test_streamlit_smoke.py      # use streamlit.testing.v1.AppTest
```

#### Verification

```bash
uv run pytest tests/ui/ -q
# Expected: 4 passed

# Manual smoke
uv run streamlit run src/energia/ui/streamlit_app.py
# Upload tests/bill/fixtures/enel_rj_sample.png
# Expected: bot summarizes "li uma conta da Enel Rio, período 2025-09, consumo 312 kWh, total R$ 287.40 — está correto?"
# Reply "sim"
# Ask "compare with the previous month"
# Expected: tool-grounded answer using compare_bill_periods
```

---

### Task 1.7 — Capability + regression evals for bill flow

**Owner:** qa-champion
**Depends on:** Task 1.6
**Branch:** `quality/bill-evals`

#### Goal

Each new tool gets a capability eval. Sprint 1 tools added to regression baseline.

#### Files

```
evals/capability/parse_bill_image.jsonl
evals/capability/list_user_bills.jsonl
evals/capability/compare_bill_periods.jsonl
evals/regression.jsonl                # appended, not replaced (HR-4)
```

#### Verification

```bash
uv run python -m energia.evals.run capability parse_bill_image
# Expected: pass@3 ≥ 0.90

uv run python -m energia.evals.run capability list_user_bills
# Expected: pass@3 ≥ 0.90

uv run python -m energia.evals.run capability compare_bill_periods
# Expected: pass@3 ≥ 0.90

uv run python -m energia.evals.run regression
# Expected: pass^3 = 1.00 across all baselined examples
```

---

### Execution Order — Sprint 1

```
Day 1:  Task 1.1 (Bill schema migration)
Day 2:  Task 1.2 (Bill Pydantic models) — RED tests → GREEN
Day 3:  Task 1.3 (parse_bill_image)     — RED tests → GREEN
Day 4:  Task 1.4 (CRUD tools)           — RED tests → GREEN
Day 5:  Task 1.5 (compare_bill_periods) — RED tests → GREEN
Day 6:  Task 1.6 (Streamlit integration) — manual smoke test
Day 7:  Task 1.7 (Evals)                 — pass@3 ≥ 0.90, pass^3 = 1.00
```

---

### Sprint 1 Exit Criteria (All must pass with actual output)

- [ ] `uv run python -m energia.db migrate` — applies 2 migrations cleanly
- [ ] DuckDB `bills` table has all Sprint 1 columns
- [ ] `uv run pytest -q` — all green (≥ 35 tests cumulative)
- [ ] `uv run pyright` — 0 errors
- [ ] `uv run ruff check .` — clean
- [ ] `parse_bill_image` capability eval pass@3 ≥ 0.90
- [ ] `compare_bill_periods` capability eval pass@3 ≥ 0.90
- [ ] Regression eval pass^3 = 1.00
- [ ] Manual: upload Enel RJ sample → chatbot summarizes + asks confirmation → user confirms → asks comparison → chatbot answers with tool-grounded numbers
- [ ] Token usage logged per session — `tool_calls` table has rows for every parse/compare call
- [ ] No PII (CPF, full address, image bytes) appears in logs (HR-6 — verified by `test_parse_bill_does_not_log_image_bytes_or_cpf`)

---

### Anti-Cheat Checkpoints — Sprint 1

After each task:

1. Run the task's test suite — paste FULL output (counts, names, timings).
2. Show `git diff --cached` — full output.
3. For chatbot capabilities: run the relevant capability eval — paste pass@3 actual number.
4. Show no Protected Path was edited (HR-3, HR-4).
5. If a test fails: STOP. Diagnose, fix PRODUCTION code, do not modify the test.

---

### Schema Notes for Sprint 1 Implementors

1. **`bill_hash` is the deduplication key.** Same image → same hash → same Bill. Don't add a separate "is_duplicate" flag.
2. **`needs_user_confirmation` defaults FALSE in DB but is SET TRUE by the parser when confidence < 0.85.** The chatbot orchestrator MUST check this flag before any tool consumes bill data. A SQL view `bills_confirmed` provides the safe subset.
3. **DECIMAL precision:** R$ amounts use `NUMERIC(10,2)`. kWh uses `NUMERIC(10,2)`. Don't use FLOAT for money.
4. **Image bytes are NEVER stored.** Only the hash + the parsed Bill JSON. If the user wants to re-view the original, they upload again.
5. **PT-BR field names in the chatbot, English in the schema.** Don't get clever — the model is comfortable translating, and English schema means our SQL stays readable for non-PT speakers.
6. **`composition_json` redundancy with composition fields:** the JSON column stores the full breakdown including any unrecognized line items the parser saw. Top-level columns are the canonical fields. SELECT prefers the JSON when downstream code needs the raw view.

---

## Sprint 2 — Tariff Awareness (outline)

**Goal:** the chatbot understands ANEEL tariff structure for the user's distributor. It can answer "should I switch to Tarifa Branca?" and "what is the bandeira this month doing to my bill?" with tool-grounded numbers from real ANEEL data.

### Architecture decisions for Sprint 2

- **ADR-006:** ANEEL Open Data REST as authoritative tariff source, with `requests-cache` SQLite at `data/aneel-cache.sqlite`. TTL: 24h tariffs, 1h bandeira current.
- **ADR-007:** Per-distributor adapter pattern — `tariff/distributors.py` defines a `Distributor` Protocol with quirks (RJ ICMS substitution, etc.). v1 ships with Enel RJ + a generic fallback.
- **ADR-008:** Tarifa Branca simulation requires a consumption shape. Default to ANEEL's typical residential curve; add a setting to override.

### Tasks

- **Task 2.1:** ANEEL client + cache (`tariff/aneel.py`)
- **Task 2.2:** `current_bandeira` + `bandeira_history` tools
- **Task 2.3:** `get_tariff` tool (per distributor + class + modalidade)
- **Task 2.4:** `simulate_tarifa_branca` tool (year-shape simulation)
- **Task 2.5:** Capability + regression evals + system prompt update with tariff vocabulary

### Sprint 2 Exit Criteria

- [ ] All Sprint 1 criteria still hold
- [ ] `current_bandeira` returns ANEEL-current value with the right surcharge
- [ ] `simulate_tarifa_branca` produces year-by-year R$ delta with assumptions block
- [ ] All Sprint 2 capability evals pass@3 ≥ 0.90
- [ ] Regression pass^3 = 1.00
- [ ] Manual: chatbot answers "vale a pena Tarifa Branca pra mim?" with grounded numbers from user's bills

---

## Sprint 3 — Solar Feasibility (outline)

**Goal:** the chatbot can answer "should I get solar panels?" with a sized system, projected generation, year-by-year payback simulation accounting for Lei 14.300, and conservative assumptions disclosed.

### Architecture decisions for Sprint 3

- **ADR-009:** pvlib + NASA POWER for solar feasibility math; PVGIS as backup. No proprietary APIs.
- **ADR-010:** Lei 14.300 Fio B schedule hardcoded in `tariff/gd.py`. Updates require a new ADR + migration of the schedule constant.
- **ADR-011:** Year-by-year simulation, never single-division payback. Default assumptions: 5% real tariff inflation, 0.5%/year degradation, 25-year horizon.

### Tasks

- **Task 3.1:** NASA POWER weather client (`solar/irradiance.py`)
- **Task 3.2:** pvlib weather-to-power chain + `estimate_solar_system` tool
- **Task 3.3:** Lei 14.300 schedule + `solar_payback` tool with year-by-year simulation
- **Task 3.4:** Catalog of common BR panels/inverters (`solar/catalog.py`)
- **Task 3.5:** Capability + regression evals + chatbot system prompt update
- **Task 3.6:** Streamlit feasibility flow — sidebar inputs (lat/lon/orientation/tilt) + chat narration

### Sprint 3 Exit Criteria

- [ ] All Sprint 1 + 2 criteria still hold
- [ ] `estimate_solar_system` returns kWp + 12-month generation series + cost estimate
- [ ] `solar_payback` returns year-by-year cash flow + IRR + payback year + assumptions block
- [ ] All Sprint 3 capability evals pass@3 ≥ 0.90
- [ ] Regression pass^3 = 1.00
- [ ] Manual: chatbot answers "vale a pena painel solar pra minha casa em Maricá?" with: recommended kWp, monthly generation, payback year, sensitivity to tariff inflation
- [ ] v1 tag created: `git tag v1.0.0`

---

## Roadmap beyond v1 (NOT in this plan)

These are tracked for context but explicitly OUT of v1 scope (HR-2):

- Inverter integration (Growatt cloud first)
- WhatsApp delivery channel
- Multi-user authentication and Postgres migration
- Anomaly detection and proactive alerts (bandeira flip notifications)
- NILM disaggregation
- Commercial / industrial customers (Group A)
- Mobile-native app

Any work toward the above MUST be a separate epic with its own PLAN.md.

---

*Residential Energy Efficiency Application — Sprints 0–3 Plan · TDD + EDD + SDD · 2026-05-10*
