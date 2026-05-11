# Production Gaps

**Generated:** 2026-05-10
**Branch:** quality/inventory-notebooks
**Purpose:** Exhaustive list of what is missing between the current codebase and a production-ready v1. File paths and line numbers are cited; no generalities.

---

## 1. Package Structure

**Current state:** There is no `src/energia/` package. The app lives entirely in `app_energia/` as a flat collection of Streamlit page modules with relative imports.

| Gap | Details |
|-----|---------|
| No `src/energia/` package | `src/`, `src/energia/`, `src/energia/__init__.py` do not exist. All target module paths (`energia.chat.orchestrator`, `energia.tariff.aneel`, etc.) are absent. |
| No `pyproject.toml` | No build system declaration, no dependency manifest, no entry points. `uv sync` (referenced in README) will fail — there is no `pyproject.toml` for `uv` to read. |
| No `uv.lock` | Package manager lock file does not exist. |
| No `ruff.toml` | Linter configuration absent. `uv run ruff check .` will use ruff defaults, not the project's target settings (line-length 100, target-version py311). |
| No `pyrightconfig.json` | Type-checker configuration absent. Strict mode not enforced. |
| No `.env.example` | Secrets contract not documented. No placeholder for `ANTHROPIC_API_KEY`, `ANEEL_BASE_URL`, `DUCKDB_PATH`, `SESSION_TOKEN_BUDGET`. |
| No `src/energia/config.py` | `pydantic-settings` Settings class does not exist. Every hardcoded path in the codebase (`data_processing.py:8`, `calculadora.py:10`, `tarifas.py:8`, `data.ipynb` cell-20) is a symptom of this gap. |
| Relative imports everywhere | `app_energia/pages/data_analysis.py:5` — `from data_processing import ...`; `app_energia/pages/upload_download.py:3` — `from data_processing import ...`. Only work when CWD is `app_energia/`. |
| Two conflicting `requirements.txt` | Root `requirements.txt` and `app_energia/requirements.txt` are both UTF-16 LE encoded, have different dep sets, and neither matches the v1 target stack. No single source of truth for dependencies. |

---

## 2. Tests

**Current state:** Zero test files exist anywhere in the repository. No `tests/` directory. No pytest configuration. No coverage tooling.

| Gap | Details |
|-----|---------|
| No `tests/` directory | `tests/__init__.py`, `tests/test_bill_parser.py`, `tests/test_solar_sizing.py`, `tests/test_tariff_aneel.py` (referenced in KICKOFF.md) do not exist. |
| No pytest config | `pyproject.toml` section `[tool.pytest.ini_options]` absent (file doesn't exist). `pytest --cov` will error. |
| No test for `calculadora.py::get_tariff()` | `get_tariff()` (`calculadora.py:33-35`) is defined inside `calculadora()` — not importable, not testable. |
| No test for `fastapi_server.py::fetch_data_from_aneel()` | Zero test coverage on the ANEEL API proxy. No mock of `httpx.AsyncClient`. |
| No test for `data_processing.py::remove_outliers_iqr()` | The only reusable algorithm in the codebase has no unit test; the function is duplicated (`data.ipynb` cell-15) with no test coverage in either location. |
| No eval fixtures | `evals/` directory does not exist. No `evals/capability/`, no `evals/regression.jsonl`. EDD gate (capability pass@3 ≥ 0.90, regression pass^3 = 1.00) cannot be run. |
| No bill parsing test | No sample bill image, no mock Anthropic vision call, no Pydantic `Bill` model to assert against. |

---

## 3. Type Annotations

**Current state:** Zero type annotations anywhere in the codebase. Every function signature is untyped. Pyright strict would report hundreds of errors.

| Gap | File | Lines |
|-----|------|-------|
| `load_cleaned_data()` untyped return | `data_processing.py` | Line 8 |
| `remove_outliers_iqr()` untyped params and return | `data_processing.py` | Lines 12-18 |
| `clean_data()` untyped | `data_processing.py` | Lines 21-28 |
| All `plot_*()` functions — `st` param typed as implicit `Any` | `data_processing.py` | Lines 32, 41, 58, 79 |
| `fetch_data_from_aneel()` — `Optional[str]` present but no return type | `fastapi_server.py` | Line 7 |
| `load_excel_sheets()` untyped return | `load_excel_data.py` | Line 7 |
| `calculadora.py::load_data()`, `get_tariff()` — no types | `calculadora.py` | Lines 9, 33 |
| `aneel_data_page.py::fetch_data_from_api()` — no return type | `aneel_data_page.py` | Line 20 |
| No `Bill`, `User`, `SolarSite`, `TariffSnapshot` Pydantic models | `src/energia/models.py` does not exist | — |
| No `SolarSizingInput`, `BillParseInput` Pydantic input models | Required by tool registry (KICKOFF.md) | — |

---

## 4. Error Handling

**Current state:** Errors are either swallowed silently, exposed as bare `Exception`, or cause unhandled crashes.

| Gap | File | Line | Issue |
|-----|------|------|-------|
| `fetch_data_from_aneel()` raises bare `Exception` with no HTTP status | `fastapi_server.py` | 21 | Caller gets no status code, no retry hint |
| No timeout on `httpx.AsyncClient` | `fastapi_server.py` | 13 | Hangs indefinitely if ANEEL doesn't respond |
| `fetch_data_from_api()` silently returns `None` on HTTP failure | `aneel_data_page.py` | 25-27 | Error is shown via `st.error()` but the exception is not re-raised or logged |
| `get_tariff()` uses `.iloc[0]` without checking if distributor exists | `calculadora.py` | 35 | `IndexError` if distributor name not found in JSON |
| `NameError` risk on "Adicionar Resultado" button | `calculadora.py` | 51-60 | `cost_formatted` / `electrical_consumption` undefined if "Calcular" not clicked first |
| Module-level `load_excel_data()` calls on import | `tarifas.py` | 15-19 | App crashes on startup if Excel file is missing; error is not caught |
| No ANEEL fallback when API is down | `aneel_data_page.py`, `fastapi_server.py` | — | Zero fallback logic to cached or static tariff data |
| No Anthropic API error handling | `src/energia/chat/orchestrator.py` does not exist | — | When implemented, must handle `anthropic.APIError`, rate limits, timeouts |
| No HR-7 cost guardrail | `src/energia/chat/orchestrator.py` does not exist | — | Token budget enforcement (200,000 tokens/session) not implemented |

---

## 5. Logging

**Current state:** Zero structured logging. `print()` statements only, and only in `data_processing.py:109` (`describe_data()` calls `print(df.describe())`).

| Gap | Details |
|-----|---------|
| No logging configuration | No `logging.basicConfig`, no `structlog`, no log levels, no log format. |
| No ANEEL API call logging | Every ANEEL request/response is invisible — no way to debug cache hits, slow endpoints, or data quality issues. |
| No tool call audit log | HR-5 requires: every tool call + result logged to audit trail. `src/energia/chat/orchestrator.py` does not exist; when created it must log `{user_message, tool_name, tool_input, tool_output, tokens_in, tokens_out, timestamp}`. |
| No session token tracking | HR-7 requires warning at 50% and 80% of the 200,000-token budget. No token counter exists. |
| `describe_data()` uses `print()` | `data_processing.py:109` — `print()` in production Streamlit code does nothing visible to the user; output goes to terminal only. |

---

## 6. CI / CD

**Current state:** No CI configuration exists. The `.github/` directory does not exist.

| Gap | Details |
|-----|---------|
| No `.github/workflows/` | No GitHub Actions pipelines. No automated lint, type-check, test, or eval runs on PR. |
| No lint step | `uv run ruff check .` not automated. |
| No type-check step | `uv run pyright` not automated. |
| No test step | `uv run pytest` not automated. Nothing would catch regressions. |
| No coverage gate | No minimum coverage threshold enforced. |
| No eval gate on PRs | Capability pass@3 / regression pass^3 not gated on chatbot feature PRs. |
| No `pre-commit` hooks | Hooks referenced in `CLAUDE.md` (`hooks/pre-commit.json`, `hooks/post-tool.json`) do not exist. |
| No branch protection rules | `main` branch has no required status checks. Direct pushes to `main` are possible. |

---

## 7. Deployment

**Current state:** No deployment configuration of any kind.

| Gap | Details |
|-----|---------|
| No `Dockerfile` | No containerization. `src/energia/` (which doesn't exist) needs a working Dockerfile before any cloud deploy. |
| No `docker-compose.yml` | Local dev requires manually starting `fastapi_server.py` on port 8000 and `app.py` separately — no orchestration. |
| No cloud platform config | No Vercel, Railway, or Streamlit Cloud config files. |
| No health check endpoint | No `/health` route. Required for container orchestration and load balancers. |
| No `migrations/` directory | DuckDB schema migrations directory does not exist. `uv run python -m energia.db migrate` (README quickstart step 4) will fail. |
| No `data/` directory gitignored | `data/energia.duckdb` is expected at runtime but `data/` does not exist and is not gitignored. |
| FastAPI as a sidecar | `fastapi_server.py` must be started separately from the Streamlit app — no process manager, no health check, no restart policy. Target architecture eliminates the FastAPI layer entirely. |

---

## 8. Missing Data Integrations

### 8.1 ANEEL Open Data (live tariff + bandeira)

| Gap | Details |
|-----|---------|
| No `src/energia/tariff/aneel.py` | The `AneelClient` class (httpx + requests-cache) does not exist. |
| No `src/energia/tariff/bandeira.py` | `current_bandeira()` and `bandeira_history()` functions do not exist. |
| No `src/energia/tariff/branca.py` | `simulate_tarifa_branca()` tool does not exist. |
| No `src/energia/tariff/distributors.py` | Per-distributor quirks (Enel RJ ICMS substituição tributária, etc.) not documented or implemented. |
| No ANEEL cache | `data/aneel-cache.sqlite` (requests-cache store) does not exist. No TTL policy implemented. |
| ANEEL base URL hardcoded | `fastapi_server.py:9` hardcodes the ANEEL URL instead of reading from `ANEEL_BASE_URL` env var. |
| ANEEL `/pt_BR/api/3/` path | `fastapi_server.py:9` uses locale-specific path `/pt_BR/api/3/`. Canonical path is `/api/3/action/`. Needs validation. |
| Tariff fallback CSV not created | `Dados/calculadora.json` and the large `Dados/tarifas-homologadas-distribuidoras-energia-eletrica.csv` are not processed into a clean `data/tariff_fallback_b1.csv` for offline use. |

### 8.2 NASA POWER (solar irradiance)

| Gap | Details |
|-----|---------|
| No `src/energia/solar/irradiance.py` | NASA POWER API client does not exist. |
| No `src/energia/solar/sizing.py` | `estimate_solar_system()` tool (pvlib-based) does not exist. |
| No `src/energia/solar/payback.py` | `solar_payback()` tool does not exist. No Lei 14.300 Fio B schedule implemented. |
| No `src/energia/solar/catalog.py` | Panel/inverter defaults for sizing math do not exist. |
| pvlib not in any requirements | `pvlib` is listed in README target stack but absent from both `requirements.txt` files. Not installed in the environment. |
| NASA POWER API not called anywhere | Zero code references `power.larc.nasa.gov`. No cache for weather data. |

### 8.3 Bill Parser (Claude vision)

| Gap | Details |
|-----|---------|
| No `src/energia/bill/parser.py` | `parse_bill_image()` tool (Claude vision → Pydantic Bill) does not exist. |
| No `src/energia/bill/store.py` | `store_bill()`, `list_user_bills()` tools do not exist. |
| No `src/energia/bill/analysis.py` | `compare_bill_periods()`, `detect_consumption_anomaly()` tools do not exist. |
| No sample bill for testing | No test fixture in `tests/` with a sample Brazilian energy bill image. No mock Anthropic vision response. |
| No bill hash deduplication | `Bill.bill_hash` (SHA-256 of image) not implemented. |
| Anthropic SDK not in any requirements | `anthropic` package absent from both `requirements.txt` files. Not installed. |

---

## 9. Chat / LLM Gaps

| Gap | Details |
|-----|---------|
| No `src/energia/chat/orchestrator.py` | The Anthropic SDK tool-use loop (KICKOFF.md) does not exist. |
| No `src/energia/chat/tools.py` | The `ToolRegistry` decorator pattern (KICKOFF.md) does not exist. Zero tools registered. |
| No `src/energia/chat/prompts.py` | `SYSTEM_PROMPT` (PT-BR, HR-5 discipline) does not exist. |
| No `src/energia/chat/memory.py` | Conversation history persistence to DuckDB does not exist. |
| No `src/energia/db.py` | DuckDB session manager and migration runner do not exist. |
| No `src/energia/models.py` | `Bill`, `User`, `Installation`, `SolarSite`, `TariffSnapshot`, `ToolCall`, `Conversation`, `Message` Pydantic models do not exist. |
| No `src/energia/config.py` | `pydantic-settings` Settings class (env var → typed config) does not exist. |
| HR-5 not enforced | The "never invent numbers" rule has no technical enforcement mechanism. No system prompt. No tool registry. |
| HR-7 not enforced | Token budget (200,000/session, warn at 50%/80%) has no implementation. |
| No Anthropic API key management | `.env.example` does not exist. `ANTHROPIC_API_KEY` is not loaded anywhere. |

---

## 10. UX Gaps (Streamlit)

| Gap | Details |
|-----|---------|
| No `src/energia/ui/streamlit_app.py` | The v1 Streamlit UI (chatbot via `st.chat_message`, bill upload widget, sidebar) does not exist. |
| No chatbot interface | `app_energia/app.py` has no chat UI. No `st.chat_message`, no `st.chat_input`. |
| No bill upload widget | No `st.file_uploader` for bill image (JPEG/PNG/PDF). |
| No session ID management | No `st.session_state['session_id']` minting. User identity (keyed by session) not implemented. |
| No persistent user state | DuckDB doesn't exist; conversation history is in-memory only (would be lost on page refresh). |
| `st.cache` deprecated in `tarifas.py:6` | `@st.cache` raises `StreamlitAPIException` in Streamlit ≥ 1.18. Breaks at runtime. |
| Module-level load in `tarifas.py:15-19` | Five `load_excel_data()` calls at import time crash the app if the Excel file is missing — not deferred to user interaction. |
| `home.py:50-51` duplicate figure | `plt.figure(figsize=(8,4))` creates an unused matplotlib Figure object on every home page render (memory leak). |
| No loading spinners | No `st.spinner()` on heavy operations (Excel reads, ANEEL API calls, Anthropic API calls). |
| No error boundaries | Any exception in a page function propagates to a Streamlit red error box with full traceback — exposes internal paths. |

---

## 11. Security / LGPD Gaps

| Gap | Details |
|-----|---------|
| No `docs/lgpd-log.md` | LGPD activity log (HR-6) does not exist. |
| No `.env` / `.env.example` | Secrets contract not documented; no `.gitignore` entry for `.env`. If an API key is added to code, it would be committed. |
| No bill data storage policy | Bills contain CPF/CNPJ (PII). No documented retention policy, no encryption at rest. DuckDB file is gitignored by convention (per `CLAUDE.md`) but `.gitignore` itself is not in the repo. |
| No `.gitignore` in repo | `git status` shows no `.gitignore`. Large binary files (`*.rar`, `*.csv` >50MB) and data files (`cleaned_energy_data.csv`) are committed to git. |
| ANEEL proxy has no auth | `fastapi_server.py::fetch_data()` is an unauthenticated public endpoint on localhost — not an immediate risk in dev but must not be exposed in any deployment. |

---

## 12. gitignore Gaps

**Current state:** No `.gitignore` in the repository.

Files that should be gitignored but are currently tracked or will be created:

```
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Data (large / generated / PII risk)
data/energia.duckdb
data/aneel-cache.sqlite
app_energia/cleaned_energy_data.csv
app_energia/High_RE_2030_efficiency1_dissipation0.5_value.csv
app_energia/MidCase_2030_efficiency1_dissipation0.5_value.csv
app_energia/Low_RE_2030_efficiency1.25_dissipation0.5_value.csv
Dados/tarifas-homologadas-distribuidoras-energia-eletrica*.csv  # 64MB each

# Secrets
.env

# Binary blobs (academic, not product)
app_energia/*.rar
app_energia/*.docx
```

---

## Gap Priority Order (recommended Sprint 1 sequence)

1. **`.gitignore`** — stop accumulating binary blobs and large CSVs in git.
2. **`pyproject.toml` + `uv.lock`** — single source of truth for deps; enables `uv sync`.
3. **`src/energia/config.py`** — eliminates all 4 hardcoded absolute paths immediately.
4. **`src/energia/models.py`** — Pydantic models for `Bill`, `User`, etc.; unblocks parser and DB.
5. **`src/energia/db.py` + `migrations/`** — DuckDB schema; unblocks bill storage and conversation history.
6. **`src/energia/chat/tools.py` + `orchestrator.py` + `prompts.py`** — chatbot loop; satisfies HR-5 and HR-7.
7. **`src/energia/tariff/aneel.py`** — live tariff data; satisfies `get_tariff` tool.
8. **`src/energia/bill/parser.py`** — bill parsing; first real user value.
9. **`tests/`** — TDD RED for each module above.
10. **`.github/workflows/`** — CI gate for lint, typecheck, tests, evals.
