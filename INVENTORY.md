# Codebase Inventory

**Generated:** 2026-05-10
**Branch:** quality/inventory-notebooks
**Scope:** All `.ipynb` and `.py` files, all data files in `app_energia/` and `Dados/`. Excludes `.git`, `__pycache__`, `.venv`, `node_modules`.

---

## Summary Table

| File | Lines / Cells | Reusability |
|------|--------------|-------------|
| `app_energia/app.py` | 33 lines | Refactor |
| `app_energia/data_processing.py` | 109 lines | Drop |
| `app_energia/fastapi_server.py` | 33 lines | Refactor |
| `app_energia/load_excel_data.py` | 11 lines | Drop |
| `app_energia/news_scraper.py` | 4 lines | Drop |
| `app_energia/pages/__init__.py` | 1 line (empty) | Drop |
| `app_energia/pages/home.py` | 53 lines | Drop |
| `app_energia/pages/data_analysis.py` | 21 lines | Drop |
| `app_energia/pages/upload_download.py` | 26 lines | Drop |
| `app_energia/pages/settings.py` | 6 lines | Drop |
| `app_energia/pages/calculadora.py` | 65 lines | Refactor |
| `app_energia/pages/tarifas.py` | 177 lines | Drop |
| `app_energia/pages/aneel_data_page.py` | 27 lines | Refactor |
| `app_energia/CRISP_DM_&_TDSP.ipynb` | 13 cells | Keep (docs) |
| `app_energia/data.ipynb` | 29 cells | Drop |
| `app_energia/problema_de_negocio.ipynb` | 10 cells | Keep (docs) |

---

## Python Files

---

### `app_energia/app.py`
**Size:** 33 lines

**Summary:** Streamlit entry-point that sets a wide-layout page config and wires seven pages to a sidebar radio nav menu. Each page is imported as a callable and invoked on selection.

**Inputs:** None directly — delegates to page callables. No env vars.

**Outputs:** Renders Streamlit page chosen by user.

**Quality flags:**
- Relative imports (`from pages.home import home`) — only works when run with `streamlit run app_energia/app.py` from inside `app_energia/`. Breaks from repo root or via `uv run`.
- No `if __name__ == "__main__"` guard needed for Streamlit, but there is also no `.env` loading or config init.

**Reusability:**
- `pages` dict + radio nav — **Refactor** → the multi-page router pattern is usable but must move to `src/energia/ui/streamlit_app.py` with absolute imports and `st.navigation` (Streamlit 1.36+).

---

### `app_energia/data_processing.py`
**Size:** 109 lines

**Summary:** Provides data loading (CSV), IQR outlier removal, and four matplotlib/seaborn visualization functions for the NREL US energy-flexibility dataset. All visualizations are scoped to US grid regions (AZNM, CAMX, NWPP, RMPA) and US-2030 scenarios — not Brazilian residential data.

**Inputs:**
- Hardcoded absolute path: `"D:/Pastas/Infnet/Infnet - 2024.2/Projeto de bloco/app_energia/cleaned_energy_data.csv"` in `load_cleaned_data()` (line 8). **Will fail on any other machine.**
- Columns expected: `energy`, `capacity`, `total_profit`, `region`, `month`.

**Outputs:**
- `plt` figures rendered via `st.pyplot(plt)` — no files written.

**Quality flags:**
- **Hardcoded absolute path** (`line 8`): `D:/Pastas/Infnet/...` — machine-specific, breaks on any other dev environment.
- No type hints on any function signature.
- `st` passed as a parameter to all plot functions (lines 32, 41, 58, 79) — unusual pattern that prevents reuse outside Streamlit.
- `describe_data()` (line 108) uses `print()` instead of returning or logging — unusable in Streamlit.
- Domain mismatch: `efficiency = total_profit / energy` measures US grid service value in $/kWh, not residential energy efficiency.

**Reusability per function:**
- `load_cleaned_data()` — **Drop.** Loads wrong-domain data with hardcoded path.
- `remove_outliers_iqr()` — **Drop.** Identical to `data.ipynb` cell-15; generic utility not needed in production pipeline.
- `clean_data()` — **Drop.** Cleans wrong-domain data.
- `plot_correlation_matrix()` — **Drop.** US grid data, wrong domain.
- `plot_efficiency_distribution()` — **Drop.** US grid data, wrong domain.
- `plot_region_efficiency()` — **Drop.** US grid data, wrong domain.
- `plot_monthly_evolution()` — **Drop.** US grid data, wrong domain. Plot pattern can be re-implemented for bill history charts.
- `describe_data()` — **Drop.** Calls `print()` — not Streamlit-safe and wrong domain.

---

### `app_energia/fastapi_server.py`
**Size:** 33 lines

**Summary:** Minimal FastAPI server with a single `/fetch_data/` GET endpoint that proxies requests to the ANEEL Open Data CKAN API (`dadosabertos.aneel.gov.br`). The endpoint accepts `resource_id`, `limit`, and optional `query` parameters.

**Inputs:**
- API calls to `https://dadosabertos.aneel.gov.br/pt_BR/api/3/action/datastore_search` (ANEEL Open Data).
- No env vars — base URL is hardcoded in `fetch_data_from_aneel()` (line 9).

**Outputs:**
- JSON response: `{"data": [...records...]}`.

**Quality flags:**
- **Hardcoded ANEEL base URL** (line 9): `https://dadosabertos.aneel.gov.br/pt_BR/api/3/action/datastore_search` — should come from env/config.
- `raise Exception("Failed to fetch data from ANEEL API")` (line 21) — bare exception with no status code or context.
- No request timeout on `httpx.AsyncClient` — will hang indefinitely if ANEEL is slow.
- No caching — calls ANEEL on every request, no TTL.
- No authentication, no rate limiting on the `/fetch_data/` endpoint itself.
- The companion page (`aneel_data_page.py`) calls `http://localhost:8000/fetch_data/` — requires this server to be separately started, with no orchestration.
- Note: ANEEL URL uses `/pt_BR/api/3/` path which may be locale-specific; the canonical path is `/api/3/action/`.

**Reusability per function:**
- `fetch_data_from_aneel()` — **Refactor.** The async httpx pattern and ANEEL endpoint knowledge migrate to `src/energia/tariff/aneel.py`. Add: env-based base URL, 10s timeout, `requests-cache` TTL (24h on tariffs, 1h on bandeira), typed return, error handling.
- `fetch_data()` FastAPI route — **Drop.** No FastAPI in v1 stack. Direct client call replaces the proxy.

---

### `app_energia/load_excel_data.py`
**Size:** 11 lines

**Summary:** Single `@st.cache_data` helper that loads all sheets from an Excel file into a `dict[str, DataFrame]`. No business logic.

**Inputs:** `filename` parameter (Excel path).

**Outputs:** `dict[str, DataFrame]` — one entry per sheet.

**Quality flags:**
- No type hints.
- Functionality is one-liner pandas: `pd.ExcelFile(f).parse(sheet)` — the abstraction adds no value.

**Reusability:**
- `load_excel_sheets()` — **Drop.** Redundant wrapper; superseded by direct `pd.read_excel()` calls in `tariff/` data loaders.

---

### `app_energia/news_scraper.py`
**Size:** 4 lines

**Summary:** Skeleton file: imports `requests`, `BeautifulSoup`, and `pandas` but contains zero functions or executable logic. No code body whatsoever.

**Inputs:** None.

**Outputs:** None.

**Quality flags:**
- **Dead file.** Contains only three import statements and a blank line.
- `bs4` and `beautifulsoup4` are not in the target v1 stack.

**Reusability:**
- Entire file — **Drop.** Web scraping is not in v1 scope (HR-2 bars unplanned integrations).

---

### `app_energia/pages/__init__.py`
**Size:** 1 line (empty)

**Summary:** Empty package init file.

**Inputs:** None. **Outputs:** None.

**Quality flags:** None beyond being an empty file.

**Reusability:** **Drop.** The `pages/` directory as a Streamlit page folder is replaced by `src/energia/ui/` in the target structure.

---

### `app_energia/pages/home.py`
**Size:** 53 lines

**Summary:** Streamlit home page rendering a project intro text and a word cloud of generic Portuguese energy keywords using the `wordcloud` library.

**Inputs:** None (hardcoded text for word cloud).

**Outputs:** `st.pyplot(fig)` — word cloud visualization.

**Quality flags:**
- **Duplicate figure creation** (lines 50-51): `plt.figure(figsize=(8,4))` creates a figure that is immediately discarded; `fig, ax = plt.subplots(...)` creates the actual used figure. The first `plt.figure` call is a dead call leaking a matplotlib Figure.
- `wordcloud` package is not in the v1 target stack (`pyproject.toml` not yet created; `requirements.txt` at root does not include it).
- Static hardcoded text string for word cloud (line 48) — not based on actual user data.
- `plot_word_cloud()` is `@st.cache_data` decorated but produces a matplotlib figure — this can cause issues because `st.cache_data` serializes return values.

**Reusability:**
- `home()` — **Drop.** Static page replaced by chatbot UI entry point in `src/energia/ui/streamlit_app.py`.
- `plot_word_cloud()` — **Drop.** Decorative; no business value in v1.

---

### `app_energia/pages/data_analysis.py`
**Size:** 21 lines

**Summary:** Streamlit page that surfaces four button-triggered visualizations (correlation matrix, efficiency distribution, regional efficiency, monthly evolution) from `data_processing.py`.

**Inputs:** Transitive hardcoded path via `load_cleaned_data()` → `data_processing.py:8`.

**Outputs:** `st.pyplot()` charts via `data_processing.py` functions.

**Quality flags:**
- Broken on any machine other than Daniel's original dev machine (transitive hardcoded path).
- All visualizations are US NREL data — wrong domain for Brazilian residential energy.
- Import `from data_processing import ...` (line 5) is a relative import that only works from inside `app_energia/`.

**Reusability:**
- `data_analysis()` — **Drop.** Wraps wrong-domain visualizations; replaced by bill history and tariff trend charts in v1.

---

### `app_energia/pages/upload_download.py`
**Size:** 26 lines

**Summary:** Streamlit page with a single download button that exports the cleaned NREL CSV to the user's browser.

**Inputs:** Transitive hardcoded path via `load_cleaned_data()` → `data_processing.py:8`.

**Outputs:** CSV download (US NREL cleaned dataset — wrong domain).

**Quality flags:**
- Hardcoded path transitive through `data_processing.py:8`.
- Wrong data domain: downloading US flexibility data, not Brazilian bill data.
- `@st.cache_data` on `convert_df_to_csv()` (line 13) is nested inside `upload_download()` — redefines the cached function on every page render (harmless but inefficient).

**Reusability:**
- `upload_download()` — **Drop.** The upload concept (bill image → parser) migrates to `src/energia/ui/streamlit_app.py` as a file uploader widget, not a download button.
- `convert_df_to_csv()` — **Drop.** Generic utility; use `df.to_csv()` directly where needed.

---

### `app_energia/pages/settings.py`
**Size:** 6 lines

**Summary:** Placeholder stub page with a title and a static "Ajustes e configurações da aplicação." string. No actual settings implemented.

**Inputs:** None. **Outputs:** Static text.

**Quality flags:**
- Completely empty implementation — placeholder only.

**Reusability:**
- `settings()` — **Drop.** Replaced by actual configuration in sidebar (model selection, session reset) in `src/energia/ui/streamlit_app.py`.

---

### `app_energia/pages/calculadora.py`
**Size:** 65 lines

**Summary:** Streamlit calculator where the user enters a device's power (W), quantity, daily hours, and period (days), selects a distributor from a JSON tariff table, and gets an estimated R$ cost. Results can be added to a session-state table.

**Inputs:**
- **Hardcoded absolute path** (line 10): `'D:\\Pastas\\Infnet\\Infnet - 2024.2\\Projeto de bloco\\Dados\\calculadora.json'` — machine-specific, breaks everywhere else.
- `Dados/calculadora.json` — 104 rows of ANEEL B1/B2 tariff data (TE, TUSD, Branca rates) per distributor.

**Outputs:**
- `st.write()` of estimated cost string.
- `st.session_state['results']` — in-memory list of calculation rows, displayed as DataFrame.

**Quality flags:**
- **Hardcoded absolute path** (line 10).
- **NameError risk** (lines 56-60): `cost_formatted` and `electrical_consumption` are only defined inside the `if st.button('Calcular Consumo'):` block (lines 38-45) but used in the `'Adicionar Resultado'` block (lines 51-60). If user clicks "Adicionar" without clicking "Calcular" first, `NameError` at runtime.
- No type hints.
- `get_tariff()` (lines 33-35) is defined inside `calculadora()` — not testable in isolation.
- Uses `vlrTotaTRFConvencional` directly without validating that the selected distributor has a valid (non-null) tariff value.

**Reusability per function:**
- `load_data()` — **Refactor.** Read path from config; return typed dict. Seed of `tariff/aneel.py` fallback loader.
- `get_tariff()` — **Refactor.** Core lookup logic: `data[data['sigDistribuidora'] == name].iloc[0]['vlrTotaTRFConvencional']`. Migrate to `tariff/aneel.py::get_tariff(distributor, modality)` with proper typing and fallback.
- Cost formula (`amount_devices * power_kW * hours * days * tariff`) — **Refactor.** Valid physics. Migrate to `solar/catalog.py` or a dedicated `bill/analysis.py::estimate_device_cost()` tool.
- `calculadora()` UI — **Drop.** Replaced by the chatbot tool `estimate_device_cost` invoked via natural language.

---

### `app_energia/pages/tarifas.py`
**Size:** 177 lines

**Summary:** Streamlit page displaying area/line charts of Brazilian national electricity consumption statistics from `Dados_abertos_Consumo_Mensal.xlsx`. Five visualization functions map to five Excel sheets (SAM consumption, UF breakdown, industrial sector, historical BEN 1970-1989, Eletrobras 1990-2003).

**Inputs:**
- **Hardcoded absolute path** (line 8): `r"D:\Pastas\Infnet\Infnet - 2024.2\Projeto de bloco\app_energia\Dados_abertos_Consumo_Mensal.xlsx"` — machine-specific.
- `Dados_abertos_Consumo_Mensal.xlsx` — ANEEL/EPE national consumption dataset.

**Outputs:**
- `st.pyplot(fig)` charts for each sheet.

**Quality flags:**
- **Hardcoded absolute path** (line 8).
- **Top-level `load_excel_data()` calls at module import time** (lines 15-19): five `load_excel_data(...)` calls execute when the module is imported, not when the page is selected. If the file is missing, the entire app crashes on startup even if the user never navigates to this page.
- **Deprecated `@st.cache`** (line 6): should be `@st.cache_data` (breaking change in Streamlit 1.18+). Running this against Streamlit ≥ 1.18 raises `StreamlitAPIException`.
- **`tarifas()` function** (line 151) calls `load_excel_data(option)` again (line 165) after already loading all sheets at module import — double load on each user interaction.
- Chart labels are in Portuguese but chart functions use `st.write()` for headers (lines 36, 53) — inconsistent pattern.
- No `st.spinner` or loading indication for heavy Excel reads.
- Data is national aggregate statistics (national/regional totals), not per-user bill data. Does not align with v1 goal of individual-level energy coaching.

**Reusability per function:**
- `load_excel_data()` — **Drop.** Replaced by `tariff/aneel.py` API client with cache.
- `plot_consumo_sam_plt()` — **Drop.** National aggregate chart, wrong domain for v1.
- `plot_consumo_sam_uf_plt()` — **Drop.** Same.
- `plot_setor_industrial_plt()` — **Drop.** Industrial sector data, out of scope (HR-2).
- `plot_consumo_ben_rg_plt()` — **Drop.** 1970-1989 historical, not actionable for residential user.
- `plot_consumo_eletrobras_plt()` — **Drop.** 1990-2003 historical, same.
- `tarifas()` — **Drop.** The entire page concept is replaced by a tariff lookup UI in v1.

---

### `app_energia/pages/aneel_data_page.py`
**Size:** 27 lines

**Summary:** Streamlit page with a form to query the local FastAPI proxy (`http://localhost:8000/fetch_data/`) which in turn calls the ANEEL Open Data API. User supplies `resource_id`, a query string, and a limit; results are shown as a DataFrame.

**Inputs:**
- `http://localhost:8000/fetch_data/` — hardcoded localhost dependency (line 21).
- No env vars.

**Outputs:**
- `st.dataframe()` of ANEEL records.

**Quality flags:**
- **Hardcoded localhost URL** (line 21): requires `fastapi_server.py` to be separately started on port 8000 with no orchestration or health check.
- `st.error("Falha ao buscar dados")` (line 25) — swallows the actual HTTP error; no status code logged.
- Default `resource_id` `3710b245-88f0-4aa6-8cfb-8b1426e9021d` hardcoded in `st.text_input` default (line 9) — no documentation of what resource this refers to.
- `fetch_data_from_api()` returns `None` on failure (line 27) but the caller does `pd.DataFrame(data)` only on truthy — logic is correct but relies on implicit `None` check.

**Reusability per function:**
- `aneel_data_page()` UI — **Drop.** Raw ANEEL query UI not part of v1 user flows.
- `fetch_data_from_api()` — **Refactor.** The concept of calling ANEEL migrates to `src/energia/tariff/aneel.py::AneelClient` using direct `httpx` (no localhost proxy). Add: env-based base URL, timeout, `requests-cache`, typed Pydantic response models.

---

## Notebooks

---

### `app_energia/CRISP_DM_&_TDSP.ipynb`
**Size:** 13 cells, ~7KB

**Summary:** Entirely markdown — no code cells. Documents the project methodology using CRISP-DM (6 phases) and TDSP (5 phases) frameworks, describing the project scope, data sources, and planned deploy steps.

**Inputs:** None (pure documentation).

**Outputs:** None.

**Quality flags:**
- No code cells — pure documentation notebook, not executable.
- References NREL datasets as primary data source — the project has since pivoted to Brazilian residential data (ANEEL, NASA POWER, bill parsing).
- Phase 4 "Modelagem" references regression models (RMSE, MAE) — these predictive models were never implemented; the actual v1 approach is LLM tool-use.

**Reusability:**
- Entire notebook — **Keep (docs).** Migrate relevant business problem framing to `docs/sessions/` or `docs/specs/`. The CRISP-DM phase outline is useful project context but must be updated to reflect the LLM-first approach.

---

### `app_energia/data.ipynb`
**Size:** 29 cells, ~442KB (large due to embedded DataFrame outputs)

**Summary:** EDA notebook that loads, combines, cleans, and visualizes the three NREL US energy-flexibility CSVs (High/Mid/Low RE 2030 scenarios). Also explores the `Dados_abertos_Consumo_Mensal.xlsx` Brazilian consumption dataset (cells 20-28, exploration only). Saves the cleaned NREL data to `cleaned_energy_data.csv`.

**Inputs:**
- `High_RE_2030_efficiency1_dissipation0.5_value.csv` (cell-1, relative path)
- `MidCase_2030_efficiency1_dissipation0.5_value.csv` (cell-1, relative path)
- `Low_RE_2030_efficiency1.25_dissipation0.5_value.csv` (cell-1, relative path)
- **Hardcoded absolute path** (cell-20): `r"D:\Pastas\Infnet\Infnet - 2024.2\Projeto de bloco\app_energia\Dados_abertos_Consumo_Mensal.xlsx"`

**Outputs:**
- `cleaned_energy_data.csv` (cell-8) — written to current working directory.
- Inline matplotlib figures (correlation matrix, boxplot, bar chart, line chart).

**Quality flags:**
- **Hardcoded absolute path** (cell-20) for Excel file.
- **Duplicate code**: `remove_outliers_iqr()` (cell-15) is character-for-character identical to `data_processing.py:11-18`. No shared module — copy-pasted.
- **Duplicate visualizations**: correlation matrix, efficiency boxplot, regional bar chart, and monthly line chart in cells 11, 16, 17, 18 are reproduced in `data_processing.py` functions. Two sources of truth for the same visualizations.
- **Cells 24-28 are repeated column-print exploratory cells** of the Excel dataset — cells 24 and 26 print the same output (column names per sheet) with slightly different code. Cell 25 calls `df.describe()` which prints a large output; cell 26 fixes a method call typo from cell 25 but doesn't supersede it.
- Embedded outputs inflate notebook to 442KB. Should be cleared before committing (`nbstripout`).
- NREL data has negative `energy` values (cell-7 output shows rows with `energy = -275`) — these represent load-shifting events, not consumption values. Misapplying this data to "energy efficiency" is semantically wrong for the Brazilian residential context.
- Cells 20-28 (Excel exploration) are orphaned — no downstream usage, no conclusions drawn.

**Reusability per cell:**
- Cells 0-1 (imports, CSV load) — **Drop.** Wrong domain data.
- Cells 2-8 (combine, clean, save) — **Drop.** Wrong domain; `cleaned_energy_data.csv` output also dropped.
- Cells 9-19 (EDA on NREL data) — **Drop.** Wrong domain; visualization patterns reusable but the specific code is not.
- Cells 20-28 (Excel EDA) — **Drop.** Orphaned exploration with no conclusions; `Dados_abertos_Consumo_Mensal.xlsx` will be accessed via `tariff/aneel.py` in production.

---

### `app_energia/problema_de_negocio.ipynb`
**Size:** 10 cells, ~5KB

**Summary:** Entirely markdown — no code cells. Defines the business problem (lack of real-time energy monitoring for residents), goals (10% consumption reduction), ODS7 alignment, success metrics, and target audience.

**Inputs:** None (pure documentation).

**Outputs:** None.

**Quality flags:**
- "Dados em tempo real" framing (cells 1-2): v1 is not real-time (no inverter integration — HR-2); chatbot is bill-based, not live telemetry.
- "Empresas de energia" in target audience (cell-9): B2B scope is out of v1 (HR-2).
- Success metric "10% consumption reduction in one year" (cell-4) is not measurable without a pre-deployment baseline — not tracked by v1.
- No code cells — pure documentation notebook, not executable.

**Reusability:**
- Entire notebook — **Keep (docs).** Core business problem statement is valid. Migrate to `docs/specs/business-problem.md`. Update the "real-time" framing to reflect the LLM tool-use, bill-parsing approach.

---

## Data Files

---

### `app_energia/cleaned_energy_data.csv`
**Size:** ~677KB

**Summary:** Output artifact of `data.ipynb` cell-8. Contains the cleaned NREL US energy-flexibility dataset after IQR outlier removal (3,433 rows from an original 4,353).

**Inputs:** Derived from `High/Mid/Low_RE_2030_*.csv`.
**Outputs:** Read by `data_processing.py::load_cleaned_data()`.

**Quality flags:** Wrong domain (US grid service values, not Brazilian residential consumption). Committed artifact that should have been gitignored.

**Reusability:** **Drop.** Remove from repo. Add `app_energia/cleaned_energy_data.csv` to `.gitignore`.

---

### `app_energia/Dados_abertos_Consumo_Mensal.xlsx`
**Size:** ~5MB (8 sheets)

**Summary:** ANEEL/EPE Brazilian national monthly electricity consumption data across 8 sheets spanning 1970-2024, broken down by region, state (UF), consumer class, and industrial sector.

**Inputs:** Manually downloaded from ANEEL/EPE portal (no script to re-fetch).
**Outputs:** Read by `tarifas.py` and `data.ipynb` (cells 20-28).

**Quality flags:** No download script or version metadata — no way to reproduce exactly. Sheets `ANALISE CONS NUMCONS SAM` and similar have unnamed columns (auto-numbered `Unnamed: 2...21`), indicating pivot tables exported from Excel that are not machine-readable.

**Reusability:** **Keep (reference).** Useful for understanding national consumption baseline. Move to `Dados/` alongside the other reference files. Do NOT import into production code; use ANEEL Open Data API instead.

---

### `app_energia/High_RE_2030_efficiency1_dissipation0.5_value.csv`
**Size:** ~56MB

**Summary:** NREL US grid service values for the high-renewable-energy 2030 scenario. Fields: region, max_pre_shift, local_datetime, energy (MWh), capacity, shifting_value, spin, reg, total_profit.

**Inputs:** NREL study download. **Outputs:** Used in `data.ipynb` cell-1.

**Quality flags:** Wrong domain (US, not Brazil). Large file committed to git — should be gitignored.

**Reusability:** **Drop.** Remove from repo. Add `*.csv` data files to `.gitignore` (except tariff fallback CSVs).

---

### `app_energia/MidCase_2030_efficiency1_dissipation0.5_value.csv`
**Size:** ~51MB

**Summary:** NREL US grid service values — mid-case (baseline) 2030 scenario. Same schema as High_RE.

**Reusability:** **Drop.** Wrong domain; large; gitignore.

---

### `app_energia/Low_RE_2030_efficiency1.25_dissipation0.5_value.csv`
**Size:** ~51MB

**Summary:** NREL US grid service values — low-renewable-energy 2030 scenario. Same schema as High_RE.

**Reusability:** **Drop.** Wrong domain; large; gitignore.

---

### `app_energia/Data description.txt`
**Size:** ~4KB

**Summary:** Plain-text README describing the three NREL datasets: field definitions for region, max_pre_shift, local_datetime, energy, capacity, shifting_value, spin, flex, reg, total_profit.

**Inputs:** None. **Outputs:** None.

**Quality flags:** Describes US datasets that are being dropped.

**Reusability:** **Keep (reference).** Move to `docs/` as `nrel-dataset-description.txt` for historical record. Not needed in production code.

---

### `app_energia/Daniel_Moreira_PB_AT.rar`
**Size:** ~14.5MB

**Reusability:** unreadable: RAR binary archive. Likely contains academic course deliverables. **Drop** — binary blob committed to git, not part of the product.

---

### `app_energia/Daniel_Moreira_PB_TP1.rar`
**Size:** ~14.1MB

**Reusability:** unreadable: RAR binary archive. Academic submission. **Drop.**

---

### `app_energia/Daniel_Moreira_PB_TP2.rar`
**Size:** ~19.2MB

**Reusability:** unreadable: RAR binary archive. Academic submission. **Drop.**

---

### `app_energia/Daniel_Moreira_PB_TP3.rar`
**Size:** ~14.5MB

**Reusability:** unreadable: RAR binary archive. Academic submission. Note: identical file size to `Daniel_Moreira_PB_AT.rar` (~14.5MB) — possible duplicate. **Drop.**

---

### `app_energia/Python App - Business Model Canvas.pdf`
**Size:** ~259KB

**Reusability:** unreadable: PDF binary format. Business Model Canvas document. **Keep (docs)** — relevant business context. Move to `docs/`.

---

### `app_energia/TP1 - questões escritas.docx`
**Size:** ~19KB

**Reusability:** unreadable: Office Open XML binary. Academic assignment questions. **Drop** — academic artifact.

---

### `Dados/calculadora.json`
**Size:** ~44KB, 104 rows

**Summary:** ANEEL tariff snapshot for 104 Brazilian energy distributors (B1/B2 residential/rural). Fields include TE, TUSD, Tarifa Convencional total, and Tarifa Branca (Fora Ponta, Ponta, Intermediária) components, with resolution date and validity start.

**Inputs:** Manually extracted from ANEEL (no fetch script). No `dthFimVigencia` field — unclear if rates are current.

**Outputs:** Read by `pages/calculadora.py::load_data()`.

**Quality flags:**
- No `dthFimVigencia` — cannot determine tariff expiry without cross-referencing ANEEL.
- No version/generation timestamp visible in the data (there is `dthProcessamento` and `dthInicioVigencia` per row, which helps).
- 104 distributors is a partial set — ANEEL has ~50+ active distributors; some records may be duplicated with different `dthInicioVigencia` values.

**Reusability:** **Refactor.** This is the seed of the tariff fallback CSV for `tariff/aneel.py`. It contains the exact fields needed (`sigDistribuidora`, `vlrTEConvencional`, `vlrTUSDConvencional`, `vlrTotaTRFConvencional`, `vlrTRFBrancaPonta`, etc.). Filter to B1 Convencional + B1 Branca, add `dthFimVigencia` column, add a `source_fetched_at` field, and commit to `data/tariff_fallback_b1.csv`. Then build the live fetch on top.

---

### `Dados/tarifas-homologadas-distribuidoras-energia-eletrica.csv`
**Size:** ~64MB, 259,085 rows

**Summary:** Full ANEEL homologated tariff dump (semicolon-delimited). Contains all tariff types (A1-A4, B1-B3), all distributors, from 2010 to ~2024, with `DatInicioVigencia` / `DatFimVigencia` validity windows. Fields include VlrTUSD and VlrTE.

**Inputs:** Downloaded from ANEEL Open Data. **Outputs:** Not currently read by any code.

**Quality flags:**
- Encoding appears to have mojibake issues in some fields (visible in CSV peek) — likely Windows-1252 encoded, not UTF-8.
- 64MB is too large to commit to git — should be gitignored and fetched via API or stored as a compressed filtered subset.
- No code references this file — it was downloaded as reference but never integrated.

**Reusability:** **Keep (reference).** Filter to B1 records with `DatFimVigencia` >= 2024-01-01, convert to UTF-8, compress to `data/tariff_fallback_b1.csv.gz` as the offline fallback for `tariff/aneel.py`. Then gitignore the full 64MB source.

---

### `Dados/tarifas-homologadas-distribuidoras-energia-eletrica (1).csv`
**Size:** ~64MB, 259,085 rows

**Summary:** Exact duplicate of `Dados/tarifas-homologadas-distribuidoras-energia-eletrica.csv` — same file size (66,003KB), same row count (259,085).

**Quality flags:** **Exact duplicate** — same size and row count as the sibling CSV. Confirmed duplication.

**Reusability:** **Drop.** Delete this file. Keep the original (un-parenthesized) filename.

---

### `Dados/daily_eletricity_generation_by_source_brazil.csv`
**Size:** ~567KB, 8,402 rows

**Summary:** Brazilian daily electricity generation by source (date, wind, hydroelectric, nuclear, solar, thermal) from 2000-01-01 onwards. Not currently referenced by any Python code.

**Inputs:** Unknown source (ONS or EPE; no provenance file). **Outputs:** Not used.

**Quality flags:**
- Note: filename misspells "electricity" as "eletricity".
- No source provenance documented.
- Not integrated into any current code.

**Reusability:** **Keep (reference).** Useful context for grid-mix reasoning and Bandeira Tarifária history correlations. Note provenance in `docs/data-sources.md` when created.

---

### `Dados/*.pdf` (appliance efficiency PDFs)
**Files:** `condicionadores-de-ar-indices-novos-IDRS_2023-12-22-v.2.pdf`, `fornos_de_micro-ondas_2023.pdf`, `lampada_decorativa.pdf`, `Lavadoras de roupa automáticas abertura frontal (front load).pdf`, `Lavadoras de roupa semi-automáticas.pdf`, `Lavadoras de roupas automáticas abertura superior (top load).pdf`, `Lavadoras e secadoras de roupa automáticas com abertura frontal (lava e seca).pdf`, `Refrigeradores-e-assemelhados_2023-12-22.xlsx` (as PDF companion), `Ventilador-de-mesa-parede-pedestal-e-circuladores-2023-04-06 v.1.xlsx` (as PDF companion), `Relatorio_Perdas_Energia.pdf`, `SAMP.pdf`, `Tarifas homologadas das distribuidoras de energia elétrica.pdf`, `CPFL.pdf`

**Reusability:** unreadable: PDF binary format. **Keep (reference).** INMETRO efficiency ratings are input material for the appliance efficiency recommendation tool. `CPFL.pdf` is likely a sample distributor bill useful for bill-parsing development. Move to `docs/reference/`.

---

### `Dados/*.xlsx` (appliance efficiency spreadsheets)
**Files:** `condicionadores-de-ar-indices-novos-IDRS_2023-12-22-v.2.xlsx` (~226KB), `Refrigeradores-e-assemelhados_2023-12-22.xlsx` (~196KB), `Ventilador-de-mesa-parede-pedestal-e-circuladores-2023-04-06 v.1.xlsx` (~422KB), `Ventilador-de-teto-2023-08-02.xlsx` (~247KB)

**Summary:** INMETRO appliance efficiency rating tables (2023 editions) for air conditioners, refrigerators, and fans. Not currently read by any code.

**Reusability:** **Keep (reference).** Machine-readable; will feed the `solar/catalog.py` or a future `bill/analysis.py::appliance_efficiency()` tool. Extract relevant columns (model, power_w, efficiency_class) into a cleaned JSON or CSV under `data/appliances/`.

---

## Root / Config Files

---

### `requirements.txt` (repo root)
**Size:** ~3.8KB, UTF-16 LE encoded (BOM visible as double-spaced characters).

**Summary:** Pinned dependency list from the Jupyter course environment. Contains Jupyter, IPython, ipykernel, matplotlib, pandas, streamlit, PyPDF2, etc. No uv or pyproject.toml integration.

**Quality flags:**
- UTF-16 LE encoding — `pip install -r requirements.txt` may fail on tools that expect UTF-8.
- Does not include: anthropic, pvlib, duckdb, pydantic, httpx, ruff, pyright, pytest — none of the v1 target deps.
- Includes heavy Jupyter/notebook deps that are not needed in production.

**Reusability:** **Drop.** Replaced by `pyproject.toml` + `uv.lock` (to be created in Sprint 1).

---

### `app_energia/requirements.txt`
**Size:** ~3.8KB, UTF-16 LE encoded.

**Summary:** Larger pinned environment from the app's dev context. Adds scrapy, selenium, beautifulsoup4, webdriver-manager, scipy, plotly, requests-cache, python-dotenv — some of which are v1-relevant (`requests-cache`, `python-dotenv`) but most are not.

**Quality flags:**
- UTF-16 LE encoding.
- Includes scrapy, selenium — web scraping tools not in v1 scope.
- Includes `requests-cache==1.2.1` — **relevant**, this is a planned v1 dependency for ANEEL cache.
- Two separate `requirements.txt` files (root and `app_energia/`) with overlapping but different deps — no single source of truth.

**Reusability:** **Drop.** Relevant deps (`requests-cache`, `httpx`, `python-dotenv`, `pandas`, `pydantic`) migrate to `pyproject.toml` with correct version ranges under `uv`.

---

### `README.md`
**Summary:** Well-written, forward-looking README describing the target architecture (`src/energia/` package, uv, pyright, pytest, ADRs). Written prospectively — describes a structure that does not yet exist in the repo.

**Quality flags:** None in the document itself. However, the quick-start commands (`uv sync`, `uv run streamlit run src/energia/ui/streamlit_app.py`) will fail because `src/energia/` doesn't exist yet.

**Reusability:** **Keep.** Will become accurate once Sprint 1 scaffold is in place.

---
