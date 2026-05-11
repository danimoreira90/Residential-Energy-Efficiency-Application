# Residential Energy Efficiency Application

A Brazilian-first chatbot that helps residential customers understand their `conta de luz`, identify habit-based savings, and evaluate whether installing solar panels would pay back at their location. v1 is Streamlit-only with Claude as the conversation engine; every quantitative claim is grounded in a typed Python tool call.

Aligned with UN Sustainable Development Goal 7 (Clean and Affordable Energy).

## Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ |
| Package manager | uv (uv.lock committed) |
| UI | Streamlit + `st.chat_message` |
| LLM | Anthropic Python SDK + `claude-sonnet-4-6` |
| Solar PV | pvlib + NASA POWER weather data |
| Tariff data | ANEEL Open Data REST API (cached) |
| Validation | Pydantic 2 + pydantic-settings |
| Data | pandas + DuckDB (local file) |
| Tests | pytest + pytest-mock + responses |
| Lint/format | ruff |
| Type-check | pyright (strict) |

## Prerequisites

- **Python** 3.11+ — [python.org](https://www.python.org)
- **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh` ([docs](https://docs.astral.sh/uv/))
- **Git**
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/danimoreira90/Residential-Energy-Efficiency-Application.git
cd Residential-Energy-Efficiency-Application

# 2. Install dependencies with uv
uv sync

# 3. Copy environment variables and fill in values
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY

# 4. Run database migrations (creates data/energia.duckdb)
uv run python -m energia.db migrate

# 5. Start the Streamlit app
uv run streamlit run src/energia/ui/streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501).

## Repository Structure

```
Residential-Energy-Efficiency-Application/
├── README.md                       # this file
├── CLAUDE.md                       # Claude Code project instructions
├── AGENTS.md                       # Multi-model agent instructions
├── pyproject.toml                  # uv-managed dependencies (created in Sprint 0)
├── .gitignore
│
├── src/energia/                    # Python package
│   ├── config.py                   # Pydantic Settings
│   ├── models.py                   # Bill, User, SolarSite, etc.
│   ├── db.py                       # DuckDB session + migrations runner
│   ├── bill/                       # Bill parsing, storage, analysis
│   ├── tariff/                     # ANEEL client, bandeira, tarifa branca, distributors
│   ├── solar/                      # pvlib wrappers, sizing, payback
│   ├── chat/                       # LangGraph orchestrator + LangChain tools
│   │   ├── state.py                # ChatState TypedDict
│   │   ├── graph.py                # StateGraph + GRAPH singleton
│   │   ├── nodes.py                # agent_node, tool_node, routing
│   │   ├── tools/                  # LangChain @tool wrappers per domain
│   │   ├── prompts.py              # PT-BR system prompt (PROTECTED)
│   │   ├── audit.py                # DuckDBAuditCallback — HR-5
│   │   └── budget.py               # TokenBudgetCallback — HR-7
│   └── ui/                         # Streamlit app
│
├── migrations/                     # Timestamped DuckDB schema migrations (immutable once applied)
├── tests/                          # pytest suite — mirrors src/ structure
├── evals/                          # Capability + regression evals (JSONL)
├── notebooks/                      # Scratch notebooks (not imported by src/)
│
└── docs/
    ├── KICKOFF.md                  # Architecture blueprint
    ├── PLAN.md                     # Sprint-by-sprint execution plan
    ├── CONTEXT.md                  # Domain glossary
    ├── INVENTORY.md                # Codebase audit (Task 0.1 output)
    ├── GAPS.md                     # Production-readiness gaps (Task 0.1 output)
    ├── MIGRATION.md                # Legacy → new layout mapping (Task 0.2 output)
    ├── architecture-plain.md       # Plain-language architecture overview
    ├── lgpd-log.md                 # LGPD activity log
    ├── tech-debt.md                # Known debt
    ├── adr/                        # Architecture Decision Records
    ├── agentic-engineering/        # ROLES, PROTECTED-PATHS, ANTI-CHEAT, etc.
    └── sessions/                   # Session-by-session work logs
```

## Scripts

| Command | Description |
|---------|-------------|
| `uv sync` | Install dependencies from `uv.lock` |
| `uv run streamlit run src/energia/ui/streamlit_app.py` | Start the dev app on `:8501` |
| `uv run pytest` | Run the test suite |
| `uv run pytest --cov=energia` | Run with coverage |
| `uv run ruff check .` | Lint |
| `uv run ruff format .` | Format |
| `uv run pyright` | Type-check (strict) |
| `uv run python -m energia.db migrate` | Apply pending DuckDB migrations |
| `uv run python -m energia.evals.run capability` | Run capability evals |
| `uv run python -m energia.evals.run regression` | Run regression evals |

## Environment Variables

See `.env.example` for all required variables. The key ones:

| Variable | Where to find it |
|----------|-----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `ANTHROPIC_MODEL` | Default `claude-sonnet-4-6` |
| `ANEEL_BASE_URL` | Default `https://dadosabertos.aneel.gov.br/api/3/action` |
| `DUCKDB_PATH` | Default `data/energia.duckdb` |
| `SESSION_TOKEN_BUDGET` | Default `200000` (HR-7 cost guardrail) |

## Conversation Flow

1. User opens the Streamlit app — a session ID is minted.
2. User uploads a photo of their `conta de luz`.
3. The chatbot calls `parse_bill_image` (Claude vision) → structured Bill stored in DuckDB.
4. Chatbot asks clarifying questions if extraction is uncertain ("li R$ 487,30 — está correto?").
5. User can ask about anomalies, habit changes, switching to Tarifa Branca, or solar feasibility.
6. Every numeric claim the chatbot makes is sourced from a logged tool call (HR-5).

## Disciplines

- **TDD** — failing test before production code. Red → Green → Refactor.
- **EDD** — chatbot capabilities ship only when capability pass@3 ≥ 0.90 and regression pass^3 = 1.00.
- **SDD** — non-trivial features get a SPEC.md before PLAN.md before code.
- **Anti-Cheat** — no skipping, softening, or mocking-the-world. See `docs/agentic-engineering/ANTI-CHEAT.md`.

## Contributing

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) — `feat`, `fix`, `chore`, `docs`, `refactor`, `test`. Owner-only.
- **Branches:** prefixed by Role — `feature/<name>`, `data/<name>`, `quality/<name>`, `infra/<name>`, `bugfix/issue-<n>-<name>`, `chore/<name>`. See `docs/agentic-engineering/ROLES.md`.
- **PRs:** require passing lint, pyright, pytest, and (for chatbot features) eval gates.
- **AI agents:** read `AGENTS.md` (or `CLAUDE.md` for Claude Code) before doing anything in this repo.

## Architecture Decisions

| ADR | Decision |
|-----|---------|
| [ADR-001](docs/adr/ADR-001-streamlit-only-v1.md) | Streamlit-only for v1; defer WhatsApp + native mobile |
| [ADR-002](docs/adr/ADR-002-langgraph-orchestration.md) | LangGraph for chat orchestration; custom HR-5 audit; no LangChain core |
| [ADR-003](docs/adr/ADR-003-duckdb-local-file.md) | DuckDB local file over Postgres for single-user MVP |
| [ADR-004](docs/adr/ADR-004-aneel-as-tariff-source.md) | ANEEL Open Data as authoritative tariff source |
| [ADR-005](docs/adr/ADR-005-pvlib-with-nasa-power.md) | pvlib + NASA POWER for solar feasibility math |

ADRs 001-005 are written in Sprint 1 alongside the corresponding scaffold. See PLAN.md.

## Honest caveats

- **Bill OCR is ~90% reliable on first pass.** The chatbot confirms numeric extractions before using them.
- **Tariff data is cached.** When ANEEL is stale or down, the chatbot answers from the last good cache and discloses the data date.
- **Payback math is conservative.** Year-by-year simulation accounting for Lei 14.300 Fio B schedule, tariff inflation, and credit expiration. Don't promise users IRR figures we can't back up.
- **Single-user, local data only.** v1 stores bills in `data/energia.duckdb` on the user's machine. No cloud, no multi-tenant, no auth (HR-2).
