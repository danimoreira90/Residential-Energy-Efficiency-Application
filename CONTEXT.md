# Residential Energy Efficiency Application — Domain Glossary (CONTEXT.md)

**Status:** Draft v0.1 | **Date:** 2026-05-10 | **Last updated by:** Daniel

> Domain language used in the Residential Energy Efficiency Application codebase. Variables, functions, file names, conversations, and agent-generated text MUST use these canonical terms.
>
> Brazilian residential energy has dense vocabulary (regulatory, tariff, PV, LLM-domain). When terms are Portuguese-only with no clean English equivalent, we keep them in Portuguese. Code keeps English where natural, Portuguese where the regulatory term has no faithful translation.
>
> Not all jargon yet — this is a starting point. Add new terms inline as you encounter friction.

---

## How to use this file

When you're discussing the system with an agent and you find yourself using vague or overloaded terminology, **stop and add the term here**. The next session will be sharper.

Example transformation:
- BEFORE: "The bill went up because the green thing turned red"
- AFTER: "The Bandeira Tarifária flipped from Verde to Vermelha 2 between Period N and Period N+1, adding R$ 0.07 per kWh"

---

## Core entities

### User
A natural person using the chatbot. v1 is single-user keyed off a Streamlit session ID — no auth, no accounts, no multi-tenant concept yet (HR-2). Persisted as a row in `users` with a session-derived UUID.

### Bill (a.k.a. "Conta de Luz")
A single monthly invoice from the energy distributor for one Installation. The product's primary input. A Bill has a Period (`mês de referência`), a Distributor, a Tariff Group, a Modalidade Tarifária, a kWh consumption value, a total amount in R$, the active Bandeira flag, the breakdown (TUSD + TE + ICMS + PIS/COFINS + COSIP + bandeira surcharge), and the line-by-line composition.

Stored in `bills` after parsing. Always linked to a User and an Installation.

### Installation (a.k.a. "Unidade Consumidora", "UC")
A physical metered point of consumption at a specific address. Identified by an installation number (`número da instalação`) issued by the Distributor. One User can have multiple Installations (rare in v1; design for it but don't expose UI for it).

Fields of note: `installation_number`, `address`, `distributor_id`, `tariff_group`, `modalidade`.

### Distributor (a.k.a. "Distribuidora")
A regulated electricity distribution concessionaire. Each one publishes its own tariffs through ANEEL. Brazil has ~50+ distributors, but for v1 we focus on the user's local one.

Notable distributors: Enel RJ, Enel SP, Enel CE, Light (RJ metropolitan), CPFL Paulista, Cemig (MG), Coelba (BA), Celpe (PE), Equatorial. Maricá is served by **Enel Rio**.

Per-distributor adapter logic lives in `src/energia/tariff/distributors.py`. Quirks (RJ ICMS substitution, etc.) are documented per-adapter.

### Tariff Group ("Grupo Tarifário")
ANEEL classifies consumers into:
- **Group A** — high-voltage industrial/commercial. **Out of scope for v1 (HR-2).**
- **Group B** — low-voltage. v1 targets B1 (residential) specifically. B2 (rural) and B3 (commercial low-voltage) deferred.

When code references "Group" without qualification, assume B1.

### Modalidade Tarifária
The pricing scheme applied to a B1 consumer:
- **Convencional** — flat R$/kWh regardless of hour.
- **Branca** — three-tier time-of-use: Ponta (peak, ~3 hours weekday evening), Intermediária (1h before + 1h after Ponta), Fora de Ponta (everything else, including weekends).

A v1 chatbot capability (`simulate_tarifa_branca`) compares a user's current Convencional consumption profile against what their bill would have been under Branca, accounting for the typical residential evening peak. The user supplies their consumption shape; we don't assume.

### Period ("Mês de Referência")
The billing period. Format: `YYYY-MM` in code, `mês/ano` in PT-BR UI. The Period is when consumption happened, not when the bill was paid (`vencimento`) or generated (`emissão`). All time-series analysis keys on Period.

### Conversation
A chatbot session — a sequence of user messages, model responses, and tool calls/results. Stored in `conversations` and `messages` tables for audit (HR-5). Every numeric claim by the model must be traceable to a logged tool call in this table.

### Tool Call
A typed Python function call invoked by the model via Anthropic's tool-use API. Each call has `name`, `input` (validated against a Pydantic schema), `output` (JSON-serializable), `tokens_in`, `tokens_out`, and `timestamp`. Logged in `tool_calls`.

---

## Brazilian regulatory and tariff vocabulary

These terms are non-negotiable in code and UI — they have specific legal/regulatory meaning under ANEEL Resolução Normativa.

### ANEEL
Agência Nacional de Energia Elétrica. The federal regulator. Publishes tariffs, distributed generation rules, and bandeira flags. Open data at `dadosabertos.aneel.gov.br`. Primary external data source for v1 tariff information.

### ONS
Operador Nacional do Sistema Elétrico. Operates the national grid. Publishes generation/load data. Not used in v1 directly.

### TE (Tarifa de Energia)
The portion of the tariff that pays for the electricity itself. Quoted in R$/kWh by ANEEL. Separated from TUSD on the bill since 2015 (the "tarifa desverticalizada" reform).

### TUSD (Tarifa de Uso do Sistema de Distribuição)
The portion of the tariff that pays for distribution infrastructure. Also in R$/kWh. Sum `TE + TUSD = total energy price before taxes and bandeira`.

### Bandeira Tarifária
Monthly grid-condition surcharge mechanism since 2015. Four colors:
- **Verde** — no surcharge.
- **Amarela** — small surcharge (~R$ 0.02/kWh in 2024-2025; check current value).
- **Vermelha 1** — medium surcharge.
- **Vermelha 2** — high surcharge.
- **Escassez Hídrica** — extraordinary surcharge invoked during 2021 drought; returns when needed.

ANEEL announces the flag near the end of each month for the following month. The chatbot pulls current and 12-month historical flags via `tariff.bandeira.current_bandeira()` and `tariff.bandeira.bandeira_history()`.

### ICMS
State-level VAT on electricity. **Varies per state.** RJ has historical specificity: distributors apply substituição tributária, meaning the displayed tariff already includes ICMS — so calculations using ANEEL's published "tarifa sem tributos" must add ICMS for RJ users carefully. This is documented in `tariff/distributors.py` per distributor.

### PIS / COFINS
Federal taxes also on the bill. Calculated at the federal level.

### COSIP / CIP
Contribuição para o Custeio da Iluminação Pública. Municipal contribution funding street lighting. Not under federal regulation. v1 chatbot extracts it from the bill but treats it as opaque.

### Geração Distribuída (GD)
Self-consumed solar (or other) generation behind the meter. ANEEL Resolução Normativa 482/2012, updated by Lei 14.300/2022.
- **Microgeração distribuída** — installed capacity ≤ 75 kW. Residential and small commercial.
- **Minigeração distribuída** — installed capacity > 75 kW and ≤ 5 MW (3 MW for non-fontes).

v1 sizing is microgeração only.

### Lei 14.300/2022 (Marco Legal da GD)
Phases in net metering compensation reductions through 2029. Affects payback calculations for new installations. The `solar.payback` tool MUST account for the user's connection date — pre-2023 installations are grandfathered for 25 years; new installations face graduated reductions in TUSD compensation.

This is the single most important regulatory parameter in payback math.

### Crédito de Energia
When a GD system generates more than the home consumes in a billing period, the surplus is credited as kWh to be used in subsequent months at the same UC (or other UCs of the same user under autoconsumo remoto). Credits expire after 60 months. Modeled in `solar.payback.simulate_year()`.

### Fio B
The TUSD-Distribuição component. Lei 14.300 specifically reduces compensation for Fio B for new GD installations on a graduated schedule:
- 2023: 15% Fio B charged
- 2024: 30%
- 2025: 45%
- 2026: 60%
- 2027: 75%
- 2028: 90%
- 2029+: full Fio B charged on injected energy

Hardcoded in `tariff.gd.fio_b_schedule()`. Update if Lei changes.

---

## Solar PV vocabulary

### kWp (kilowatt-peak)
Installed PV capacity at standard test conditions (STC: 1000 W/m², 25°C, AM1.5). The headline metric for system size.

### kWh (kilowatt-hour)
Energy. What gets billed and what gets generated. 1 kWh = 1 kW for 1 hour.

### Irradiance
Solar power per unit area. Measured in W/m² (instantaneous) or kWh/m²/day (daily). Three components, all relevant to PV modeling:
- **GHI (Global Horizontal Irradiance)** — what a flat ground sensor sees. Sum of DNI×cos(zenith) + DHI.
- **DNI (Direct Normal Irradiance)** — beam component perpendicular to the sun.
- **DHI (Diffuse Horizontal Irradiance)** — sky-scattered component.

`pvlib` decomposes GHI into DNI/DHI when only GHI is available, then transposes to plane-of-array based on tilt and azimuth.

### TMY (Typical Meteorological Year)
A synthesized year of hourly weather built from many real years, representing the long-run typical. PVGIS (a free European Commission service) and NREL serve TMY data globally. v1 uses NASA POWER for hourly weather and pvlib for transposition.

### Performance Ratio (PR)
Actual annual energy output divided by what the panel rating × irradiance × area would predict. Healthy residential systems hit PR ≈ 0.75-0.85 in Brazil.

### Inverter
Converts DC from panels to AC for the grid. Sized smaller than the array (typical DC/AC ratio ~1.2 in Brazil) since panels rarely hit nameplate. Common Brazilian residential brands: Growatt, WEG, Fronius, SolarEdge, Solis. v1 doesn't talk to inverters; the catalog (`solar/catalog.py`) just provides reasonable defaults for sizing math.

### Payback (a.k.a. "Tempo de Retorno")
Years until the system has saved as much as it cost. v1 uses a year-by-year simulation accounting for: tariff inflation assumption (default 5% real), Lei 14.300 Fio B schedule, projected generation degradation (~0.5%/year), credit expiration. **Never** computed as a single division.

### Geração Mensal Estimada
Predicted kWh per month for a hypothetical system. Output of `solar.sizing.estimate_solar_system()`. Always reported as a 12-element series, not a single yearly average — seasonal variation matters for the user's bill mental model.

---

## System concepts

### Tool Registry
The pattern in `src/energia/chat/tools.py`. A decorator `@registry.register(name, description, input_model)` attaches a Python function as a callable tool the LLM can invoke. The registry exposes `schemas()` (passed to Anthropic SDK as `tools=`) and `call(name, raw_input)` (used inside the orchestrator's tool loop).

### Orchestrator
`src/energia/chat/orchestrator.py`. Implements the Anthropic SDK tool-use loop: send messages + tools, on `stop_reason == "tool_use"` execute the requested tools and feed results back, repeat until `end_turn`. Enforces HR-7 (cost guardrails) by tracking cumulative tokens per session.

### System Prompt
`src/energia/chat/prompts.py`. Defines the chatbot's persona, language, and HR-5 discipline ("never invent numbers"). PROTECTED — touch only via SPEC + Daniel approval.

### Tool-grounded Answer
A chatbot response where every numeric claim originates from a logged tool call. The opposite of a hallucinated answer. Per HR-5, this is the only acceptable kind of quantitative answer the chatbot can produce.

### Suggested Action
A non-quantitative recommendation the chatbot makes ("considere mudar para Tarifa Branca", "vale a pena trocar a geladeira antiga"). Suggested Actions can be qualitative without a tool call, but if they include a number ("você economizaria R$ X"), HR-5 applies and the number must come from a tool.

### Capability Eval
A JSONL file under `evals/<tool_name>.jsonl`. Each line: `{"input": {...}, "expected_call": "...", "expected_output_pattern": "..."}`. The eval runner sends each input through the orchestrator and asserts (a) the right tool was called with conformant inputs, and (b) the model's narration matches the expected pattern. Pass@3 ≥ 0.90 required for new capabilities.

### Regression Eval
A JSONL file under `evals/regression.jsonl`. Captures behaviors that previously worked. Pass^3 = 1.00 (all 3 attempts passing on every example) required before merge.

### Bill Hash
A SHA-256 of the user's bill PDF/photo. Used for deduplication when a user re-uploads the same bill. Stored in `bills.bill_hash`. We **do not** store the original file — only the parsed structured data + the hash.

### ANEEL Cache
A `requests-cache` SQLite store at `data/aneel-cache.sqlite`. TTL: 24h on tariff endpoints, 1h on bandeira current. Survives across runs. v1 must always be operable when ANEEL is down (cache hit) or slow (cache hit before timeout).

---

## AI / LLM vocabulary

### Hallucination
The model produces a plausible-sounding numeric or factual claim that has no grounding in any tool call or context fact. The single biggest risk for an energy efficiency chatbot — wrong R$ savings figures or wrong payback periods can lose the user money or trust irrecoverably. HR-5 exists to prevent this.

### Tool-use loop
The cycle inside the orchestrator: model produces tool calls → orchestrator executes them → orchestrator feeds results back as `user` messages → model continues. Terminates when model emits `end_turn`. Bounded by HR-7.

### Vision
Claude's ability to read images. v1 uses vision for bill parsing (`bill.parser.parse_bill_image`). The model receives the bill image + a structured-extraction prompt; output is a Pydantic-validated `Bill` object. Vision quality on Brazilian bills varies — first-pass accuracy ~90%; the chatbot offers "I read R$ 487.30 — está correto?" before proceeding.

### Sonnet / Haiku
Anthropic model tiers. v1 default is `claude-sonnet-4-6` (good tool-use, vision, reasoning); fallback is `claude-haiku-4-5-20251001` (cheaper, faster, slightly weaker on ambiguous tool selection).

### Prompt Injection
A malicious or accidental input that tries to override the system prompt. v1 risk surface: a user uploads a bill PDF that contains adversarial text in the bill image. Mitigation: vision extraction is constrained to a Pydantic schema; the parser ignores any free-form text outside expected fields.

---

## Roles and permissions vocabulary

v1 is **single-user**. No accounts, no roles, no RBAC. Streamlit session ID is the user identity. (HR-2 — multi-tenant out of scope.)

When auth is introduced (post-v1), terms to coin:
- "Owner" — the household head, primary contact
- "Member" — secondary household members with read access
- "Viewer" — accountants, family members without edit rights

---

## Forbidden / fuzzy / overloaded terms

Avoid these — use the canonical terms instead.

| Avoid | Use instead |
|---|---|
| "Conta" alone | "Bill" or "Conta de Luz" — "conta" alone is ambiguous |
| "Energia" alone in numeric context | "kWh" (energy) or "kW" (power) — they're different |
| "Tarifa" alone | "TE", "TUSD", "tarifa total", or "tarifa branca" — "tarifa" alone is too generic |
| "Bandeira" alone for status | "Bandeira Tarifária" + the color name |
| "Solar" alone | "PV", "geração distribuída", or "kWp do sistema" — "solar" is too generic |
| "Painéis" | "módulos fotovoltaicos" in technical contexts; "painéis" OK in UI |
| "Economia" alone | "Economia de R$ X/mês" or "Economia de Y kWh/mês" — quantify |
| "Investimento" alone | "Custo inicial estimado em R$ X" — be specific |
| "Retorno" alone | "Payback estimado em X anos" — quantify and qualify the assumptions |
| "Consumo alto" | "Consumo de X kWh, Y% acima da média sazonal do usuário" — quantify |
| "Inversor" without context | Specify brand+model when relevant; in catalog math, "inversor genérico de Z kW" |
| "Conta cara" / "conta gorda" | "Bill above seasonal baseline by R$ X" — neutral language with numbers |
| "Cliente" | "User" (current usage); reserved for future B2B sense |
| "App" alone | "Streamlit app" or "energia app" — "app" alone is ambiguous when WhatsApp comes in v2+ |
| "Token" alone | Anthropic API tokens (input/output count) vs. JWT auth token (post-v1) — disambiguate |

---

## PT-BR vs English in code

Rule of thumb:
- **English** — module names, function names, variable names, type names, error messages, log messages.
- **Portuguese** — UI labels, chatbot messages, system prompt, regulatory terms (TUSD, TE, ICMS, COSIP, Bandeira), distributor names, units shown to user (R$, kWh).

Mixed-language identifiers like `tarifaBranca` are tolerated when the regulatory term has no clean English ("White Tariff" loses meaning). Document the mix in this file as it appears.

---

## Changelog

- **2026-05-10** — Initial draft. Core entities, regulatory vocabulary, solar PV terms, system concepts, AI/LLM vocab.

---

## To resolve (open questions)

- [ ] How does v1 handle a user with multiple Installations (rare but real for owners with a primary residence + a beach house)? Design suggests "first one is default; switching is a settings concern, post-v1."
- [ ] Tarifa Branca simulation needs a consumption-shape assumption (when in the day does the user use energy?). Default profile from ANEEL's residential typical curves vs. ask the user — TBD.
- [ ] When ANEEL data is stale or the cache is empty, do we fall back to hand-curated CSV (last known good) or refuse to answer? Current design: fall back with a "values from <date>" disclaimer.
- [ ] Lei 14.300 Fio B schedule — should we let the user override the assumption (e.g., for sensitivity analysis) or keep it locked to the legal schedule? Current design: locked, but show in assumptions block.
- [ ] How long do we keep parsed bill data? LGPD says "as long as needed for the stated purpose." For v1, indefinite within the local DuckDB; user can clear by deleting the file. Document in privacy.md.
