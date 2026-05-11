# Migration Plan

**Generated:** 2026-05-10
**Branch:** quality/migration-plan
**Inputs:** INVENTORY.md (Task 0.1), GAPS.md (Task 0.1), KICKOFF.md
**Purpose:** Maps every file in the existing `app_energia/` codebase to its fate in the target `src/energia/` package. No code moves until Daniel reviews and approves this document.

---

## 1. Executive Summary

- **100 % of executable Python targets the wrong domain or is structurally broken.** The thirteen Python files in `app_energia/` either operate on NREL US grid-flexibility data (wrong domain) or carry structural bugs (deprecated `@st.cache`, hardcoded absolute paths, `NameError` risk) that prevent safe porting. Not a single file ships intact.

- **One function body is worth carrying (PORT).** `fastapi_server.py::fetch_data_from_aneel()` (lines 7–21) carries the correct ANEEL httpx call pattern to `src/energia/tariff/aneel.py::AneelClient`. Everything else is REWRITE from scratch against the KICKOFF.md blueprint.

- **Four INVENTORY "Refactor" verdicts are upgraded here.** `calculadora.py` is upgraded from Refactor → REWRITE (NameError STRUCTURAL-BUG at lines 51–60 + hardcoded path at line 10). `tarifas.py` is upgraded from Drop → DROP-with-STRUCTURAL-BUG annotation (deprecated `@st.cache` at line 6 crashes Streamlit ≥ 1.18; module-level loads at lines 15–19 crash the app on import). `aneel_data_page.py` is upgraded from Refactor → DROP (hardcoded `localhost:8000` dependency STRUCTURAL-BUG; raw API browser not a v1 user flow). These upgrades are documented in the transformations column of Section 3.

- **The entire `src/energia/` package is greenfield REWRITE.** Thirteen target modules (config, models, db, bill×3, tariff×4, solar×4, chat×4, ui) must be written from scratch. Two functions from existing code are extracted and rehoused in those modules.

- **~170 MB of wrong-domain data files must be removed and gitignored.** Three NREL CSVs (High/Mid/Low RE 2030, ~158 MB total), `cleaned_energy_data.csv` (~677 KB), four RAR academic blobs (~65 MB), and a duplicate tariff CSV (`(1).csv`, 64 MB) belong in `.gitignore`, not in the repo.

- **Key data assets survive.** `Dados/calculadora.json` moves to `notebooks/legacy/calculadora.json` as REFERENCE-MATERIAL — its 104-row snapshot retains reference value but is never imported by `src/`. Sprint 2 Task 2.1 builds `data/tariff_fallback_b1.csv` fresh from ANEEL homologation API values; the legacy JSON may optionally sanity-check those numbers. The full ANEEL tariff CSV (`Dados/tarifas-homologadas-distribuidoras-energia-eletrica.csv`) becomes a filtered offline fallback. INMETRO appliance XLSXes move to `docs/reference/` for future tool development.

- **File-count summary:**

  | Verdict | Count | Notes |
  |---------|-------|-------|
  | DROP | 23 | 8 Python files + 2 requirements.txt + 1 notebook + 4 RAR + 3 NREL CSVs + 1 cleaned CSV + 1 DOCX + 1 duplicate CSV + 2 empty/dead files |
  | PORT | 1 | `fastapi_server.py::fetch_data_from_aneel()` → `tariff/aneel.py` |
  | REWRITE | 2 | `app.py` → `ui/streamlit_app.py`; `calculadora.py` logic → `tariff/aneel.py` + `bill/analysis.py` |
  | KEEP-AS-DOCS | 14 | 2 notebooks + 1 BMC PDF + 1 description TXT + 1 XLSX national data + 8 PDFs/XLSXes in Dados/ + 1 CSV generation data |
  | All new `src/energia/` modules | 13 | Greenfield REWRITE; no existing file contributes structure |

---

## 2. Target Structure

The destination blueprint from KICKOFF.md. Every PORT and REWRITE item in Section 3 targets a specific path in this tree.

```
src/energia/
├── __init__.py
├── config.py               # Pydantic Settings — reads ANTHROPIC_API_KEY, ANEEL_BASE_URL,
│                           #   DUCKDB_PATH, SESSION_TOKEN_BUDGET, TARIFF_FALLBACK_PATH
├── models.py               # Pydantic models: Bill, User, Installation, SolarSite,
│                           #   TariffSnapshot, TariffRate, ToolCall, Conversation, Message
├── db.py                   # DuckDB session manager + forward-only migration runner
│
├── bill/
│   ├── __init__.py
│   ├── parser.py           # parse_bill_image(image_bytes) → Bill  [Claude vision]
│   ├── store.py            # store_bill(), list_user_bills(), get_bill_by_hash()
│   └── analysis.py         # compare_bill_periods(), detect_consumption_anomaly(),
│                           #   estimate_device_cost()  [cost formula from calculadora.py]
│
├── tariff/
│   ├── __init__.py
│   ├── aneel.py            # AneelClient (httpx + requests-cache);
│                           #   get_tariff(distributor, modality) → TariffRate
│                           #   [PORT of fetch_data_from_aneel(); logic from calculadora.py]
│   ├── bandeira.py         # current_bandeira() → BandeiraStatus; bandeira_history()
│   ├── branca.py           # simulate_tarifa_branca(profile, tariff) → BrancaComparison
│   └── distributors.py     # Per-distributor quirks (Enel RJ ICMS substituição, etc.)
│
├── solar/
│   ├── __init__.py
│   ├── irradiance.py       # NASA POWER API client; get_tmy(lat, lon) → TMYData
│   ├── sizing.py           # estimate_solar_system() tool (pvlib ModelChain)
│   ├── payback.py          # solar_payback() tool; Lei 14.300 Fio B schedule
│   └── catalog.py          # Common BR panel / inverter defaults for sizing math
│
├── chat/
│   ├── __init__.py
│   ├── orchestrator.py     # Anthropic SDK tool-use loop; HR-7 token guardrail
│   ├── tools.py            # ToolRegistry decorator (exact blueprint from KICKOFF.md)
│   ├── prompts.py          # SYSTEM_PROMPT in PT-BR; HR-5 discipline  [PROTECTED]
│   └── memory.py           # Conversation history → DuckDB conversations/messages tables
│
└── ui/
    ├── __init__.py
    └── streamlit_app.py    # st.chat_message chatbot; bill upload; session ID;
                            #   sidebar (session info, reset)
```

Supporting directories (also new):

```
migrations/                 # Timestamped DuckDB schema SQL files (HR-3 immutable once applied)
tests/                      # pytest suite — mirrors src/ structure
evals/
├── capability/             # Per-tool capability JSONL fixtures
└── regression.jsonl        # Regression suite
data/
├── energia.duckdb          # Runtime DB (gitignored)
├── aneel-cache.sqlite      # requests-cache store (gitignored)
└── tariff_fallback_b1.csv  # Built in Sprint 2 Task 2.1 from ANEEL homologation API; committed; small
notebooks/                  # Scratch / docs notebooks (never imported by src/)
docs/
├── adr/                    # Architecture Decision Records (ADR-001 … ADR-005)
├── agentic-engineering/    # ROLES, PROTECTED-PATHS, etc.
├── reference/              # Moved PDFs, XLSXes, description TXT
├── lgpd-log.md
└── tech-debt.md
```

---

## 3. Per-File Migration Table

Columns: **Source path** | **INVENTORY verdict** | **MIGRATION verdict** | **Target module** | **Sprint** | **Required transformations** | **Justification**

`PORT` = carry the function body, fix the surface (types, config, error handling).
`REWRITE` = start from scratch; existing code does not survive structurally.
`DROP` = delete; do not move.
`KEEP-AS-DOCS` = move to `notebooks/` or `docs/reference/`; never imported by `src/`.
`REFERENCE-MATERIAL` = move to `notebooks/legacy/`; never imported by `src/`; retained only as a sanity-check reference for future work.
`MOVE-TO-NOTEBOOKS` = not used (no Python file is exploratory enough to warrant it).

### Python files

| Source | INVENTORY | MIGRATION | Target | Sprint | Required transformations | Justification |
|--------|-----------|-----------|--------|--------|--------------------------|---------------|
| `app_energia/app.py` | Refactor | REWRITE | `src/energia/ui/streamlit_app.py` | Sprint 0 | Drop 7-page sidebar nav; add `st.chat_message` + `st.chat_input` loop; add `st.file_uploader` for bill images; add `st.session_state['session_id']` minting (UUID); integrate `chat.orchestrator.chat()`; absolute imports `from energia.*`; sidebar: session token counter, reset button | Router concept survives; entire UI structure changes from multi-page nav to chatbot |
| `app_energia/data_processing.py` | Drop | DROP | — | — | WRONG-DOMAIN | All 8 functions target NREL US grid regions/scenarios; `efficiency = total_profit / energy` measures US grid service value, not Brazilian residential consumption; no business logic carries |
| `app_energia/fastapi_server.py` | Refactor | PORT | `src/energia/tariff/aneel.py` | Sprint 2 | `fetch_data_from_aneel()` → `AneelClient.fetch()`; add `httpx.Timeout(10.0)`; replace hardcoded URL (line 9) with `settings.ANEEL_BASE_URL`; replace bare `Exception` (line 21) with `AneelAPIError(status_code, message)`; wrap in `httpx.TimeoutException` handler; add `@cached(expire=86400)` (requests-cache); type return `list[dict[str, Any]]`; FastAPI route `fetch_data()` → DROP (no FastAPI in v1) | ANEEL httpx call pattern correct; only FastAPI wrapper discarded |
| `app_energia/load_excel_data.py` | Drop | DROP | — | — | OBSOLETE-DEPENDENCY | One-liner `pd.ExcelFile` wrapper; no business logic; superseded by direct `pd.read_excel()` calls inside `tariff/` data loaders |
| `app_energia/news_scraper.py` | Drop | DROP | — | — | DEAD-CODE | File contains only three import statements and no functions |
| `app_energia/pages/__init__.py` | Drop | DROP | — | — | DEAD-CODE | Empty init for a directory structure that does not survive migration |
| `app_energia/pages/home.py` | Drop | DROP | — | — | WRONG-DOMAIN | Static info page + decorative word cloud; replaced by chatbot UI in `streamlit_app.py`; `wordcloud` not in v1 stack |
| `app_energia/pages/data_analysis.py` | Drop | DROP | — | — | WRONG-DOMAIN | Wraps NREL US data visualizations; hardcoded path transitive from `data_processing.py:8` |
| `app_energia/pages/upload_download.py` | Drop | DROP | — | — | WRONG-DOMAIN | Downloads NREL cleaned CSV; bill upload concept rewritten as `st.file_uploader` in `streamlit_app.py`; no code carries |
| `app_energia/pages/settings.py` | Drop | DROP | — | — | DEAD-CODE | Two-line stub: title + static string; no implementation |
| `app_energia/pages/calculadora.py` | Refactor | REWRITE ↑ | `src/energia/tariff/aneel.py` (lines 33–35) + `src/energia/bill/analysis.py` (lines 41–43) | Sprint 2 + Sprint 1 | **Upgrade reason:** NameError STRUCTURAL-BUG at lines 51–60 (`cost_formatted` / `electrical_consumption` undefined if user clicks "Adicionar" without first clicking "Calcular"); hardcoded absolute path at line 10 (`D:\\Pastas\\...`). Extract `get_tariff()` (lines 33–35) to `tariff/aneel.py::get_tariff(distributor: str, modality: str) -> TariffRate` with Pydantic return; extract cost formula (lines 41–43) to `bill/analysis.py::estimate_device_cost(power_w, quantity, hours_per_day, days, tariff_brl_per_kwh)`; replace hardcoded JSON path with `settings.TARIFF_FALLBACK_PATH`; Streamlit UI dropped entirely | Correct domain logic (Brazilian tariffs + device energy math); two structural bugs prevent port as-is |
| `app_energia/pages/tarifas.py` | Drop | DROP ↑ | — | — | WRONG-DOMAIN + STRUCTURAL-BUG | **Upgrade annotation:** `@st.cache` (line 6) raises `StreamlitAPIException` on Streamlit ≥ 1.18 (breaking); module-level `load_excel_data()` calls (lines 15–19) crash the entire app on startup if the Excel file is missing, not deferred to page selection; national aggregate consumption statistics are not a v1 user flow |
| `app_energia/pages/aneel_data_page.py` | Refactor | DROP ↑ | — | — | STRUCTURAL-BUG | **Upgrade reason:** hardcoded `http://localhost:8000/fetch_data/` (line 21) requires the FastAPI sidecar to be separately started with no orchestration; raw ANEEL resource-ID query UI is not a v1 user feature; ANEEL fetch concept migrates to `tariff/aneel.py` directly, not via any Streamlit page |

### Notebooks

| Source | INVENTORY | MIGRATION | Target | Sprint | Required transformations | Justification |
|--------|-----------|-----------|--------|--------|--------------------------|---------------|
| `app_energia/CRISP_DM_&_TDSP.ipynb` | Keep (docs) | KEEP-AS-DOCS | `notebooks/CRISP_DM_TDSP.ipynb` | Sprint 0 | Rename (remove `&`); add a top markdown cell noting that the data-source section (cell-2) reflects the pre-pivot NREL state | All-markdown; valuable CRISP-DM / TDSP methodology context |
| `app_energia/data.ipynb` | Drop | DROP | — | — | WRONG-DOMAIN + DUPLICATED | All 29 code cells target NREL US data; `remove_outliers_iqr()` (cell-15) is a character-for-character duplicate of `data_processing.py:11–18`; 442 KB of embedded DataFrame outputs bloat the file |
| `app_energia/problema_de_negocio.ipynb` | Keep (docs) | KEEP-AS-DOCS | `notebooks/problema_de_negocio.ipynb` | Sprint 0 | Add top markdown cell noting that "dados em tempo real" framing (cell-1) reflects the pre-chatbot state | All-markdown; core business problem statement valid for v1 |

### Data and reference files

| Source | INVENTORY | MIGRATION | Target | Sprint | Required transformations | Justification |
|--------|-----------|-----------|--------|--------|--------------------------|---------------|
| `app_energia/cleaned_energy_data.csv` | Drop | DROP | — | — | WRONG-DOMAIN | Generated NREL artifact committed to git; gitignore `app_energia/cleaned_energy_data.csv` |
| `app_energia/Dados_abertos_Consumo_Mensal.xlsx` | Keep (ref) | KEEP-AS-DOCS | `Dados/Dados_abertos_Consumo_Mensal.xlsx` | Sprint 0 | Move from `app_energia/` to `Dados/`; add to `.gitignore` (5 MB) | National monthly consumption reference; too large and too aggregate for production import |
| `app_energia/High_RE_2030_efficiency1_dissipation0.5_value.csv` | Drop | DROP | — | — | WRONG-DOMAIN | NREL US data; 56 MB; add to `.gitignore`; consider `git filter-repo` for history (see Open Question 5) |
| `app_energia/MidCase_2030_efficiency1_dissipation0.5_value.csv` | Drop | DROP | — | — | WRONG-DOMAIN | NREL US data; 51 MB; gitignore |
| `app_energia/Low_RE_2030_efficiency1.25_dissipation0.5_value.csv` | Drop | DROP | — | — | WRONG-DOMAIN | NREL US data; 51 MB; gitignore |
| `app_energia/Daniel_Moreira_PB_AT.rar` | Drop | DROP | — | — | DEAD-CODE | Academic submission binary blob; not product code |
| `app_energia/Daniel_Moreira_PB_TP1.rar` | Drop | DROP | — | — | DEAD-CODE | Academic submission binary blob |
| `app_energia/Daniel_Moreira_PB_TP2.rar` | Drop | DROP | — | — | DEAD-CODE | Academic submission binary blob |
| `app_energia/Daniel_Moreira_PB_TP3.rar` | Drop | DROP | — | — | DEAD-CODE | Academic submission; same file size as PB_AT — likely duplicate |
| `app_energia/Python App - Business Model Canvas.pdf` | Keep (docs) | KEEP-AS-DOCS | `docs/reference/business-model-canvas.pdf` | Sprint 0 | Move and rename | Business context; not product code |
| `app_energia/TP1 - questões escritas.docx` | Drop | DROP | — | — | DEAD-CODE | Academic assignment questions; not product documentation |
| `app_energia/Data description.txt` | Keep (ref) | KEEP-AS-DOCS | `docs/reference/nrel-dataset-description.txt` | Sprint 0 | Move and rename | Documents the dropped NREL datasets for historical context |
| `Dados/calculadora.json` | Refactor | REFERENCE-MATERIAL | `notebooks/legacy/calculadora.json` | Sprint 0 | Move to `notebooks/legacy/`; never imported by `src/`; Sprint 2 Task 2.1 may cross-check freshly fetched ANEEL homologation values against these numbers | 104-row ANEEL tariff snapshot; retains reference value but is not the source for `data/tariff_fallback_b1.csv` — that file is built fresh from the ANEEL API in Sprint 2 |
| `Dados/tarifas-homologadas-distribuidoras-energia-eletrica.csv` | Keep (ref) | KEEP-AS-DOCS (filtered) | `data/tariff_fallback_b1.csv.gz` (new filtered file) | Sprint 2 | Filter to B1/B2 Convencional + Branca; `DatFimVigencia >= 2024-01-01`; re-encode to UTF-8 (source appears Windows-1252); compress; original 64 MB file → gitignore | 259,085-row full ANEEL dump; too large to commit; create a small filtered subset |
| `Dados/tarifas-homologadas-distribuidoras-energia-eletrica (1).csv` | Drop | DROP | — | — | DUPLICATED | Exact duplicate of sibling CSV (same row count 259,085, same file size 64 MB) |
| `Dados/daily_eletricity_generation_by_source_brazil.csv` | Keep (ref) | KEEP-AS-DOCS | `Dados/` (stays) | — | Note provenance in `docs/data-sources.md` when created; filename typo ("eletricity") documented | Brazilian generation-mix context; not referenced in production code |
| `Dados/*.pdf` (8 files) | Keep (ref) | KEEP-AS-DOCS | `docs/reference/` | Sprint 0 | Move all PDFs from `Dados/` to `docs/reference/`; note categories in `docs/data-sources.md` | Appliance efficiency + CPFL sample bill + grid reports; reference material for tool development |
| `Dados/*.xlsx` (4 files: AC, refrigerator, fan×2) | Keep (ref) | KEEP-AS-DOCS | `docs/reference/` | Sprint 1–2 | Move to `docs/reference/`; extract key columns (model, power_w, efficiency_class) to `data/appliances/*.csv` when implementing efficiency tool | INMETRO appliance ratings; machine-readable; needed for an efficiency recommendation tool |
| `requirements.txt` (repo root) | Drop | DROP | — | — | OBSOLETE-DEPENDENCY | UTF-16 LE encoded; missing all v1 deps (no anthropic, pvlib, duckdb, pydantic); superseded by `pyproject.toml` + `uv.lock` |
| `app_energia/requirements.txt` | Drop | DROP | — | — | OBSOLETE-DEPENDENCY | UTF-16 LE encoded; includes scrapy, selenium not in v1 scope; superseded by `pyproject.toml` + `uv.lock` |

---

## 4. Per-Function Table (PORT items only)

Only `app_energia/fastapi_server.py` carries the PORT verdict. Its two functions:

---

### Function 1 — `fetch_data_from_aneel()`

| Field | Detail |
|-------|--------|
| **Source** | `app_energia/fastapi_server.py:7` |
| **Existing signature** | `async def fetch_data_from_aneel(resource_id: str, limit: int, query: Optional[str] = None)` |
| **New signature** | `class AneelClient:` → `async def fetch(self, resource_id: str, limit: int = 10, query: str \| None = None) -> list[dict[str, Any]]` |
| **Target module** | `src/energia/tariff/aneel.py` |
| **Required transformations** | (1) Replace hardcoded URL `"https://dadosabertos.aneel.gov.br/pt_BR/api/3/action/datastore_search"` (line 9) with `f"{self._base_url}/datastore_search"` where `self._base_url = settings.ANEEL_BASE_URL` (default `"https://dadosabertos.aneel.gov.br/api/3/action"`). Note: `/pt_BR/` path is locale-specific; canonical API path drops it. (2) Add `timeout=httpx.Timeout(10.0)` to `async with httpx.AsyncClient(timeout=...)` (line 13). (3) Replace bare `raise Exception("Failed to fetch data from ANEEL API")` (line 21) with `raise AneelAPIError(status_code=response.status_code, detail=response.text)` — custom exception defined in `tariff/aneel.py`. (4) Add outer `try: ... except httpx.TimeoutException: raise AneelTimeoutError(resource_id=resource_id)`. (5) Decorate with `requests-cache` session (TTL: 86 400 s for tariff endpoints, 3 600 s for bandeira endpoints — passed via `CachedSession`). (6) Return `list[dict[str, Any]]`; caller validates each record against `TariffRecord` Pydantic model in `models.py`. |
| **Test plan** | Using `pytest-respx`: mock `httpx.AsyncClient.get` to return `{"result": {"records": [...]}}` on 200; assert `AneelClient.fetch()` returns a non-empty list; mock a 503 response and assert `AneelAPIError` is raised with the correct `status_code`; mock `httpx.TimeoutException` and assert `AneelTimeoutError` is raised. |

---

### Function 2 — `fetch_data()` FastAPI route

| Field | Detail |
|-------|--------|
| **Source** | `app_energia/fastapi_server.py:23` |
| **Migration verdict** | **DROP** |
| **Reason** | FastAPI is not in the v1 stack. The route is a thin wrapper around `fetch_data_from_aneel()`; once that function becomes `AneelClient.fetch()`, there is nothing left to keep. |

---

### Functions extracted from REWRITE files (not PORT, but listed for traceability)

These functions are extracted from `calculadora.py` (REWRITE verdict) and housed in new target modules. They appear here for completeness because INVENTORY.md flagged them as reusable.

#### `get_tariff()` — from `app_energia/pages/calculadora.py:33–35`

| Field | Detail |
|-------|--------|
| **Existing signature** | `def get_tariff(distributor_name)` — nested inside `calculadora()`, line 33 |
| **New signature** | `def get_tariff(distributor: str, modality: str = "Convencional") -> TariffRate` |
| **Target module** | `src/energia/tariff/aneel.py` |
| **Required transformations** | (1) Promote from nested function to module-level function. (2) Replace `data[data['sigDistribuidora'] == distributor_name].iloc[0]` (no null check) with a safe lookup that raises `DistributorNotFoundError` if the distributor is absent. (3) Add `modality` parameter to support both `"Convencional"` and `"Branca"` tariffs. (4) Return a `TariffRate` Pydantic model with fields `te_brl_kwh`, `tusd_brl_kwh`, `total_brl_kwh`, `branca_ponta_brl_kwh`, `branca_intermediaria_brl_kwh`, `branca_fora_ponta_brl_kwh`, `valid_from`, `distributor`. (5) First attempt live ANEEL API (`AneelClient.fetch()`); on `AneelAPIError` or `AneelTimeoutError`, fall back to `settings.TARIFF_FALLBACK_PATH`. |
| **Test plan** | Load `data/tariff_fallback_b1.csv` as fixture; assert `get_tariff("ENEL RIO", "Convencional")` returns a `TariffRate` with `total_brl_kwh > 0`; assert `DistributorNotFoundError` raised for unknown distributor; mock API failure and assert fallback CSV is used. |

#### Cost formula — from `app_energia/pages/calculadora.py:41–43`

| Field | Detail |
|-------|--------|
| **Existing code** | Lines 41–43: `power_electric_kW = power_electric / 1000; electrical_consumption = amount_devices * power_electric_kW * use_duration * period; cost = electrical_consumption * tariff` |
| **New signature** | `def estimate_device_cost(power_w: float, quantity: int, hours_per_day: float, days: int, tariff_brl_per_kwh: float) -> DeviceCostResult` |
| **Target module** | `src/energia/bill/analysis.py` |
| **Required transformations** | (1) Extract inline math to a standalone typed function. (2) Return `DeviceCostResult` Pydantic model with fields `device_kwh_month`, `cost_brl_month`, `assumptions` (dict of inputs for audit). (3) Validate `power_w > 0`, `quantity >= 1`, `hours_per_day` in (0, 24], `days` in [1, 31], `tariff_brl_per_kwh > 0` — raise `ValueError` on invalid input. (4) This function does not call the tariff API directly; the caller (`chat/orchestrator.py`) passes the tariff value obtained from `get_tariff()`. |
| **Test plan** | Assert `estimate_device_cost(1000, 1, 8, 30, 0.85)` returns `device_kwh_month == 240.0` and `cost_brl_month == 204.0`; assert `ValueError` raised when `power_w <= 0`. |

---

## 5. Drop List

All items in the table below are deleted from the working tree. Items marked with a gitignore note must also be added to `.gitignore` to prevent re-introduction.

| File | Category | Justification |
|------|----------|---------------|
| `app_energia/data_processing.py` | WRONG-DOMAIN | All 8 functions target NREL US grid regions; `efficiency = total_profit / energy` measures US grid service value, not Brazilian residential energy |
| `app_energia/load_excel_data.py` | OBSOLETE-DEPENDENCY | One-liner `pd.ExcelFile` wrapper with no business logic; superseded by direct `pd.read_excel()` |
| `app_energia/news_scraper.py` | DEAD-CODE | File contains only 3 import statements and zero functions; web scraping out of v1 scope |
| `app_energia/pages/__init__.py` | DEAD-CODE | Empty init for a directory that does not survive migration |
| `app_energia/pages/home.py` | WRONG-DOMAIN | Static page + hardcoded word cloud; no content relevant to Brazilian energy chatbot |
| `app_energia/pages/data_analysis.py` | WRONG-DOMAIN | Pure wrapper for NREL US visualizations; hardcoded path transitive from `data_processing.py:8` |
| `app_energia/pages/upload_download.py` | WRONG-DOMAIN | Downloads NREL cleaned CSV; not a bill upload feature |
| `app_energia/pages/settings.py` | DEAD-CODE | Two-line stub: title + static string; zero implementation |
| `app_energia/pages/tarifas.py` | WRONG-DOMAIN + STRUCTURAL-BUG | National aggregate stats; `@st.cache` line 6 crashes Streamlit ≥ 1.18; module-level loads lines 15–19 crash app on startup |
| `app_energia/pages/aneel_data_page.py` | STRUCTURAL-BUG | Hardcoded `localhost:8000`; requires FastAPI sidecar; raw API query UI not a v1 user flow |
| `app_energia/data.ipynb` | WRONG-DOMAIN + DUPLICATED | All code cells target NREL US data; `remove_outliers_iqr()` duplicates `data_processing.py`; 442 KB embedded outputs |
| `app_energia/cleaned_energy_data.csv` | WRONG-DOMAIN | Generated NREL artifact committed to git; gitignore |
| `app_energia/High_RE_2030_efficiency1_dissipation0.5_value.csv` | WRONG-DOMAIN | NREL US grid flexibility data; 56 MB; gitignore |
| `app_energia/MidCase_2030_efficiency1_dissipation0.5_value.csv` | WRONG-DOMAIN | NREL US grid flexibility data; 51 MB; gitignore |
| `app_energia/Low_RE_2030_efficiency1.25_dissipation0.5_value.csv` | WRONG-DOMAIN | NREL US grid flexibility data; 51 MB; gitignore |
| `app_energia/Daniel_Moreira_PB_AT.rar` | DEAD-CODE | Academic submission binary blob; not product code |
| `app_energia/Daniel_Moreira_PB_TP1.rar` | DEAD-CODE | Academic submission binary blob |
| `app_energia/Daniel_Moreira_PB_TP2.rar` | DEAD-CODE | Academic submission binary blob |
| `app_energia/Daniel_Moreira_PB_TP3.rar` | DEAD-CODE | Academic submission; same file size as PB_AT — likely duplicate |
| `app_energia/TP1 - questões escritas.docx` | DEAD-CODE | Academic assignment questions; not product documentation |
| `Dados/tarifas-homologadas-distribuidoras-energia-eletrica (1).csv` | DUPLICATED | Exact duplicate of sibling CSV (259,085 rows, 64 MB); gitignore pattern `* (1).csv` |
| `requirements.txt` (repo root) | OBSOLETE-DEPENDENCY | UTF-16 LE encoded; missing all v1 deps; superseded by `pyproject.toml` + `uv.lock` |
| `app_energia/requirements.txt` | OBSOLETE-DEPENDENCY | UTF-16 LE encoded; scrapy/selenium not in v1 scope; superseded by `pyproject.toml` + `uv.lock` |

---

## 6. Sprint Mapping

Groups every PORT and REWRITE item (existing code → target module) plus all greenfield REWRITE modules that have no existing precursor. Items are listed in recommended implementation order within each sprint.

---

### Sprint 0 — Foundation + Chat Spine

**Goal:** Repo cleanly structured; `uv sync` works; chatbot loop runs end-to-end with a single stub tool.

**From existing files (REWRITE / MOVE):**

| Action | Source | Target |
|--------|--------|--------|
| REWRITE | `app_energia/app.py` | `src/energia/ui/streamlit_app.py` |
| KEEP-AS-DOCS | `app_energia/CRISP_DM_&_TDSP.ipynb` | `notebooks/CRISP_DM_TDSP.ipynb` |
| KEEP-AS-DOCS | `app_energia/problema_de_negocio.ipynb` | `notebooks/problema_de_negocio.ipynb` |
| KEEP-AS-DOCS | `app_energia/Dados_abertos_Consumo_Mensal.xlsx` | `Dados/` |
| KEEP-AS-DOCS | `app_energia/Python App - Business Model Canvas.pdf` | `docs/reference/` |
| KEEP-AS-DOCS | `app_energia/Data description.txt` | `docs/reference/nrel-dataset-description.txt` |
| KEEP-AS-DOCS | `Dados/*.pdf` (8 files) | `docs/reference/` |

**Greenfield REWRITE (no existing precursor):**

| New module | Key content |
|-----------|-------------|
| `pyproject.toml` + `uv.lock` | anthropic, pydantic, pydantic-settings, pvlib, duckdb, streamlit, httpx, requests-cache, pandas, python-dotenv, pytest, ruff |
| `.gitignore` | `*.pyc`, `__pycache__/`, `.venv/`, `data/energia.duckdb`, `data/aneel-cache.sqlite`, all dropped CSVs and RARs |
| `ruff.toml` | `line-length = 100`, `target-version = "py311"` |
| `pyrightconfig.json` | `"strict": true`, `"pythonVersion": "3.11"` |
| `.env.example` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANEEL_BASE_URL`, `DUCKDB_PATH`, `SESSION_TOKEN_BUDGET`, `TARIFF_FALLBACK_PATH` |
| `migrations/` directory | Empty dir + `README.md` explaining naming convention |
| `src/energia/__init__.py` | Package marker |
| `src/energia/config.py` | `pydantic-settings` `Settings`; eliminates all 4 hardcoded paths; `TARIFF_FALLBACK_PATH` default points to `data/tariff_fallback_b1.csv` (file does not need to exist until Sprint 2 — `config.py` does not validate file existence at import time) |
| `src/energia/models.py` | `Bill`, `User`, `Installation`, `SolarSite`, `TariffSnapshot`, `TariffRate`, `DeviceCostResult`, `BandeiraStatus`, `ToolCall`, `Conversation`, `Message` |
| `src/energia/db.py` | `DuckDBSession`; `run_migrations()` scans `migrations/*.sql` in timestamp order |
| `src/energia/chat/tools.py` | `ToolRegistry` — exact implementation from KICKOFF.md |
| `src/energia/chat/orchestrator.py` | Anthropic SDK tool loop; HR-7 token counter + budget halt at 200 000 tokens |
| `src/energia/chat/prompts.py` | `SYSTEM_PROMPT` PT-BR; HR-5 "nunca inventa números" rule — PROTECTED PATH |
| `src/energia/chat/memory.py` | `save_message()`, `load_history()` → DuckDB `conversations` / `messages` tables |
| `docs/adr/ADR-001-streamlit-only-v1.md` … `ADR-005-pvlib-with-nasa-power.md` | Five ADRs from README |

---

### Sprint 1 — Bill Spine

**Goal:** Chatbot can accept a bill image, parse it, store it, and answer "why was my bill higher last month?"

**Tariff dependency note:** Sprint 1 has no tariff-lookup dependency. `compare_bill_periods()` uses tariff values already embedded in the two `Bill` objects being compared (parsed from the bills themselves). `estimate_device_cost()` accepts `tariff_brl_per_kwh` as a caller-supplied parameter; the chatbot may ask the user for it or leave it unregistered as a tool until Sprint 2 wires `get_tariff()`.

**From existing files (logic extracted from REWRITE):**

| Action | Source | Logic extracted | Target |
|--------|--------|-----------------|--------|
| Logic carried from REWRITE | `calculadora.py:41–43` | `estimate_device_cost()` cost formula | `src/energia/bill/analysis.py` |

**Greenfield REWRITE (no existing precursor):**

| New module | Key tools registered |
|-----------|---------------------|
| `src/energia/bill/parser.py` | `parse_bill_image` — Claude vision → validated `Bill` |
| `src/energia/bill/store.py` | `store_bill`, `list_user_bills`, `get_bill_by_hash` |
| `src/energia/bill/analysis.py` | `compare_bill_periods`, `detect_consumption_anomaly`, `estimate_device_cost` |
| `migrations/20260510_001_initial_schema.sql` | `users`, `installations`, `bills`, `conversations`, `messages`, `tool_calls` tables |
| `tests/test_bill_parser.py` | Mock Anthropic vision; assert `Bill` model populated |
| `tests/test_bill_analysis.py` | Unit tests for `estimate_device_cost()` and `compare_bill_periods()` |
| `evals/capability/parse_bill_image.jsonl` | Capability eval fixtures for bill parser |

---

### Sprint 2 — Tariff Awareness

**Goal:** Chatbot can answer "what is the Bandeira this month doing to my bill?" and "should I switch to Tarifa Branca?"

**From existing files (PORT + REWRITE logic):**

| Action | Source | Logic extracted | Target |
|--------|--------|-----------------|--------|
| PORT | `fastapi_server.py:7–21` | `AneelClient.fetch()` | `src/energia/tariff/aneel.py` |
| Logic carried from REWRITE | `calculadora.py:33–35` | `get_tariff()` | `src/energia/tariff/aneel.py` |

Task 2.1 builds `data/tariff_fallback_b1.csv` by fetching current B1 Convencional + Branca homologation records directly from the ANEEL open-data API and writing them to CSV. `notebooks/legacy/calculadora.json` (REFERENCE-MATERIAL) may be used to sanity-check individual distributor values against the API result but is not the data source.

**Greenfield REWRITE:**

| New module | Key tools registered |
|-----------|---------------------|
| `src/energia/tariff/aneel.py` | `get_tariff` |
| `src/energia/tariff/bandeira.py` | `current_bandeira`, `bandeira_history` |
| `src/energia/tariff/branca.py` | `simulate_tarifa_branca` |
| `src/energia/tariff/distributors.py` | Per-distributor quirks; no tool registration (called internally) |
| `tests/test_tariff_aneel.py` | Mock httpx; assert `AneelAPIError` on failure; assert fallback CSV used |
| `evals/capability/get_tariff.jsonl` | Capability evals for tariff retrieval |
| `evals/capability/simulate_tarifa_branca.jsonl` | Capability evals for Tarifa Branca simulation |

---

### Sprint 3 — Solar Feasibility

**Goal:** Chatbot can answer "should I get solar?" with grounded kWp sizing and year-by-year payback.

**From existing files:** No existing code contributes to Sprint 3. All solar modules are greenfield.

**Greenfield REWRITE:**

| New module | Key tools registered |
|-----------|---------------------|
| `src/energia/solar/irradiance.py` | `get_tmy` (internal); no direct tool registration |
| `src/energia/solar/sizing.py` | `estimate_solar_system` |
| `src/energia/solar/payback.py` | `solar_payback` (Lei 14.300 Fio B schedule baked in) |
| `src/energia/solar/catalog.py` | No tool; provides defaults to `sizing.py` |
| `data/appliances/` | Extracted from `Dados/*.xlsx` INMETRO ratings |
| `tests/test_solar_sizing.py` | pvlib integration test with mocked NASA POWER response |
| `evals/capability/estimate_solar_system.jsonl` | Capability evals |
| `evals/capability/solar_payback.jsonl` | Capability evals; regression suite extended |

---

## 7. Open Questions

These must be resolved by Daniel before code in the affected sprint begins. Each question cites where the ambiguity lives.

---

**Q1 — `estimate_device_cost` sprint placement**

Context: The cost formula from `calculadora.py:41–43` is valid domain logic and easy to implement, but it needs a tariff value — which comes from `get_tariff()` in Sprint 2.

- **Option A (Sprint 1):** Implement `estimate_device_cost()` in Sprint 1 using the `data/tariff_fallback_b1.csv` offline tariff. Users get the feature earlier; the tariff value may be stale until Sprint 2 wires in the live API.
- **Option B (Sprint 2):** Defer `estimate_device_cost()` to Sprint 2, placing it in `bill/analysis.py` only after `get_tariff()` is live. Avoids stale tariff values; delays the capability by one sprint.
- **Option C (Sprint 1, internal only):** Implement in Sprint 1 as a non-tool utility — callable by the orchestrator but not registered with `ToolRegistry`. Upgrade to a registered tool in Sprint 2 when live tariffs are available.

Trade-offs: A ships value sooner at the cost of temporary staleness. B ensures data freshness. C is a clean separation but adds a refactor step in Sprint 2.

---

**Q2 — `app_energia/` directory fate after migration**

Context: Once all files are moved or deleted, `app_energia/` will be empty (or contain only `__pycache__/`). Three options:

- **Option A:** Delete the directory entirely once the migration commit lands. Clean; no ambiguity about which directory runs the app.
- **Option B:** Leave `app_energia/` with a single `README.md`: "Superseded by `src/energia/`. See MIGRATION.md." Provides a breadcrumb for anyone with an old bookmark or shell alias.
- **Option C:** Keep `app_energia/app.py` as a one-line shim: `from energia.ui.streamlit_app import main; main()`. Maintains compatibility with anyone running `streamlit run app_energia/app.py`; creates a permanent debt item.

Trade-offs: A is cleanest. B is polite to old users. C is a maintenance liability.

---

**Q3 — `Dados/calculadora.json` → fallback CSV timing** — RESOLVED

`calculadora.json` is REFERENCE-MATERIAL (`notebooks/legacy/calculadora.json`); it is never the source for the production fallback CSV and is never imported by `src/`.

`data/tariff_fallback_b1.csv` is built fresh from ANEEL homologation API values in Sprint 2 Task 2.1, once `TariffRate` is defined in `models.py`. Sprint 0 `config.py` defines `TARIFF_FALLBACK_PATH` with a default of `"data/tariff_fallback_b1.csv"`; the file does not need to exist at import time. Sprint 1 has no tariff-lookup dependency (bill comparison uses tariff values embedded in parsed bills; device cost function accepts tariff as a caller parameter).

---

**Q4 — CRISP_DM notebook rename strategy**

Context: `app_energia/CRISP_DM_&_TDSP.ipynb` — the `&` character in the filename is problematic in some shells and git operations.

- **Option A:** Rename to `notebooks/CRISP_DM_TDSP.ipynb` on move. Clean filename; loses the exact original name.
- **Option B:** Rename to `notebooks/CRISP_DM_and_TDSP.ipynb`. Readable; preserves intent.
- **Option C:** Omit from `notebooks/` entirely. The document's content has already been superseded by `CLAUDE.md`, `KICKOFF.md`, and `PLAN.md`.

Trade-offs: A or B preserve the context cheaply. C is defensible since the content is stale (references NREL data as primary source).

---

**Q5 — Large NREL CSV files in git history**

Context: The three NREL CSVs total ~158 MB and are in the git commit history. Adding them to `.gitignore` and deleting from the working tree stops growth, but the history bloat remains, increasing clone times.

- **Option A (gitignore only):** Delete from working tree; add to `.gitignore`. Simple; history stays; ~158 MB in every future clone.
- **Option B (`git filter-repo`):** Expunge the three files from all history. Clean clone; history is rewritten; requires `git push --force` to `origin/main` (destructive — requires Daniel to explicitly approve).
- **Option C (new orphan branch):** Start a clean-history branch from the current tree, set as main. Nuclear; loses all commit messages and context.

Trade-offs: A is safe and reversible. B is permanent, requires force-push, but yields a clean repo. C is disproportionate. B is the right long-term call if Daniel approves the force-push; otherwise A is the default.
