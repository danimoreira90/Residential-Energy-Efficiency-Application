# Residential Energy Efficiency App — Kickoff Plan

## Locked v1 scope

- **Audience:** Brazilian residential users (B1 tariff group).
- **Capabilities:** bill upload + analysis + coaching, solar feasibility simulator. No hardware, no inverter integration in v1.
- **Channel:** Streamlit web app.
- **Primary interface:** chatbot. Dashboards are secondary.
- **Architectural principle:** every quantitative claim comes from a typed Python function the LLM calls via tool use. The LLM never invents numbers.

---

## Project structure

```
residential-energy/
├── pyproject.toml
├── .env.example                # ANTHROPIC_API_KEY, ANEEL_BASE_URL, etc.
├── README.md
├── data/                       # DuckDB file lives here, gitignored
├── src/energia/
│   ├── __init__.py
│   ├── config.py               # Pydantic Settings
│   ├── models.py               # Bill, User, SolarSite, TariffSnapshot
│   ├── db.py                   # DuckDB session + migrations
│   │
│   ├── bill/
│   │   ├── parser.py           # Vision-based extraction (Claude)
│   │   ├── store.py            # Persist + retrieve bills
│   │   └── analysis.py         # Period comparison, anomaly detection
│   │
│   ├── tariff/
│   │   ├── aneel.py            # ANEEL Open Data API client (cached)
│   │   ├── bandeira.py         # Current flag + 12-month history
│   │   ├── branca.py           # Tarifa Branca simulation
│   │   └── distributors.py     # Per-distributor quirks (Enel RJ ICMS, etc.)
│   │
│   ├── solar/
│   │   ├── irradiance.py       # NASA POWER + Forecast.Solar clients
│   │   ├── sizing.py           # pvlib weather-to-power
│   │   ├── payback.py          # ROI given user's tariff
│   │   └── catalog.py          # Common panels/inverters in BR
│   │
│   ├── chat/
│   │   ├── orchestrator.py     # Anthropic SDK + tool loop
│   │   ├── tools.py            # Registry decorator
│   │   ├── prompts.py          # System prompt in PT-BR
│   │   └── memory.py           # Conversation history persistence
│   │
│   └── ui/
│       └── streamlit_app.py    # st.chat_message + sidebar
│
├── notebooks/                  # Move existing .ipynb here, treat as scratch
└── tests/
    ├── test_bill_parser.py
    ├── test_solar_sizing.py
    └── test_tariff_aneel.py
```

---

## Tool-registry pattern

Each capability is a typed function. The LLM picks which tools to call.

```python
# src/energia/chat/tools.py
from pydantic import BaseModel
from typing import Callable, Any

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, name: str, description: str, input_model: type[BaseModel]):
        def decorator(fn: Callable):
            self._tools[name] = {
                "schema": {
                    "name": name,
                    "description": description,
                    "input_schema": input_model.model_json_schema(),
                },
                "model": input_model,
                "fn": fn,
            }
            return fn
        return decorator

    def schemas(self) -> list[dict]:
        return [t["schema"] for t in self._tools.values()]

    def call(self, name: str, raw: dict) -> Any:
        t = self._tools[name]
        return t["fn"](t["model"].model_validate(raw))

registry = ToolRegistry()
```

Example registration alongside an implementation:

```python
# src/energia/solar/sizing.py
from pydantic import BaseModel, Field
from energia.chat.tools import registry

class SolarSizingInput(BaseModel):
    lat: float = Field(description="Latitude in decimal degrees")
    lon: float = Field(description="Longitude in decimal degrees")
    monthly_kwh: float = Field(description="Average monthly consumption (kWh)")
    roof_orientation: str = Field(description="N, NE, E, SE, S, SW, W, or NW")
    roof_tilt_deg: float = Field(default=15.0, description="Roof tilt in degrees")

@registry.register(
    name="estimate_solar_system",
    description=(
        "Estimates recommended kWp, expected monthly generation, and rough cost "
        "for a residential PV system at the given location. Call when user asks "
        "whether solar makes sense, what size they need, or for payback estimates."
    ),
    input_model=SolarSizingInput,
)
def estimate_solar_system(inp: SolarSizingInput) -> dict:
    # 1. pull weather: pvlib.iotools.get_pvgis_tmy(inp.lat, inp.lon)
    # 2. build ModelChain with assumed module + inverter from catalog
    # 3. simulate annual AC energy
    # 4. size system to cover ~110% of monthly_kwh
    # 5. return structured result
    return {
        "recommended_kwp": ...,
        "monthly_generation_kwh": ...,
        "annual_generation_kwh": ...,
        "estimated_cost_brl": ...,
        "assumptions": {...},
    }
```

---

## Orchestrator

```python
# src/energia/chat/orchestrator.py
import json
from anthropic import Anthropic
from energia.chat.tools import registry
from energia.chat.prompts import SYSTEM_PROMPT

client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
MODEL = "claude-sonnet-4-6"  # good tool-use, reasonable cost

def chat(messages: list[dict]) -> tuple[str, list[dict]]:
    """Run one user turn through the model, executing tool calls until end_turn."""
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=registry.schemas(),
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text = "".join(b.text for b in response.content if b.type == "text")
            return text, messages

        if response.stop_reason == "tool_use":
            # Echo assistant turn back into history
            messages.append({"role": "assistant", "content": response.content})

            # Run every tool the model asked for
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = registry.call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {e}",
                            "is_error": True,
                        })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Other stop reasons (max_tokens, etc.) — bail
        return "(model did not finish)", messages
```

---

## System prompt (sketch — PT-BR)

```python
# src/energia/chat/prompts.py
SYSTEM_PROMPT = """\
Você é um assistente especializado em eficiência energética residencial no Brasil.
Seu papel é ajudar o usuário a entender sua conta de luz, identificar oportunidades
de economia e avaliar se vale a pena instalar energia solar.

Regras inegociáveis:
1. Nunca invente números. Toda afirmação quantitativa deve vir de uma chamada de
   ferramenta. Se você não tem ferramenta para calcular algo, diga que não sabe.
2. Sempre cite a unidade (kWh, R$, %, meses) e o período de referência.
3. Quando o usuário enviar uma foto de conta de luz, use `parse_bill_image` antes
   de qualquer análise.
4. Para qualquer recomendação de economia, mostre o impacto estimado em R$/mês.
5. Responda em português brasileiro, tom amigável e direto. Evite jargão técnico
   sem explicar.

Contexto do usuário (quando disponível): localização, distribuidora, classe
tarifária, histórico de contas, modalidade tarifária atual.
"""
```

---

## Initial tool catalog (v1)

| Tool name | Module | What it does |
|---|---|---|
| `parse_bill_image` | `bill.parser` | Vision-based extraction from a photo of a Brazilian energy bill |
| `store_bill` | `bill.store` | Persist a parsed bill for the user |
| `list_user_bills` | `bill.store` | Return the user's bill history |
| `compare_bill_periods` | `bill.analysis` | Compare two periods, decompose delta into consumption / tariff / bandeira |
| `detect_consumption_anomaly` | `bill.analysis` | Flag bills > N% above seasonal baseline |
| `current_bandeira` | `tariff.bandeira` | Returns current month's flag and surcharge |
| `get_tariff` | `tariff.aneel` | Pull current TE + TUSD for a distributor + class |
| `simulate_tarifa_branca` | `tariff.branca` | Estimate savings if user switched to white tariff |
| `estimate_solar_system` | `solar.sizing` | Recommend kWp + estimated generation |
| `solar_payback` | `solar.payback` | ROI given user's bills + system cost |

Each one is a 20–80 line function. Build them incrementally; the chatbot becomes more capable as you register more.

---

## Claude Code prompts — run in order

### Prompt 1 — Inventory (read-only)

```
You're helping me inventory a Streamlit-based residential energy efficiency
project that's mostly Jupyter notebooks (~95% by line count). DO NOT change
any code yet.

Read every notebook (.ipynb) and Python file in this repo. Then produce two
files at the repo root:

1. INVENTORY.md — one section per file containing:
   - File path and approximate size (cells/lines)
   - Two-sentence summary of what it does
   - Inputs: data files read, APIs called, environment variables used
   - Outputs: data written, plots produced, models trained
   - Quality flags: dead cells, hardcoded paths, secrets in code, duplicated
     logic, broken imports
   - Reusability score (keep / refactor / drop) with one-line justification
     per function or major cell

2. GAPS.md — what's missing to make this a real production app:
   - Package structure (currently zero)
   - Tests, types, error handling, logging, CI, deployment
   - Data integrations needed: ANEEL Open Data, NASA POWER, bill parser
   - UX gaps: chatbot, persistent user state, auth
   Be specific — file paths and line numbers, not generalities.

Stop after producing those two files. Do not refactor anything.
```

### Prompt 2 — Migration plan (still no code changes)

```
Read INVENTORY.md, GAPS.md, and KICKOFF.md (which contains the target
src/energia/ structure).

Produce MIGRATION.md mapping every reusable piece of existing code to its
new home:

- Per-notebook table: cell range → target module → required transformations
  (typing, error handling, config extraction, etc.)
- Per-function table: existing signature → new signature → notes
- A clear "drop" list with one-line justification each

Do not move any code. I will review the plan first.
```

### Prompt 3 — Scaffold the package

```
Create the src/energia/ package per KICKOFF.md. Each module should contain:
- Module docstring describing its responsibility
- Type hints on all function signatures
- A `# TODO: migrate from notebooks/<file>.ipynb cell N` comment where logic
  will be ported in
- For tool-exposed functions: the @registry.register decorator with a real
  description and Pydantic input model

Set up pyproject.toml using uv with dependencies:
  anthropic, pydantic, pydantic-settings, pvlib, pandas, duckdb,
  streamlit, requests, python-dotenv, pytest, ruff

Add ruff config (line length 100, target py311).
Add .env.example with ANTHROPIC_API_KEY placeholder.
Add a minimal README.md with quickstart (uv sync, streamlit run).
Add a basic tests/ directory with one passing test per module to anchor CI.

Implement chat/tools.py and chat/orchestrator.py exactly as in KICKOFF.md.
Leave every other module's body as TODOs — do not migrate logic yet.
```

### Prompt 4 — Migrate the first capability

```
Pick the bill-parsing logic from notebook X (per MIGRATION.md). Implement
src/energia/bill/parser.py end-to-end:

- A `parse_bill_image(image_bytes: bytes) -> Bill` function
- Uses Claude's vision via the Anthropic SDK to extract: distribuidora,
  classe (B1/B2/B3), modalidade (Convencional/Branca), período de referência,
  consumo_kwh, valor_total_brl, bandeira do mês, composição (TUSD/TE/ICMS/
  PIS/COFINS/COSIP)
- Returns a validated Bill Pydantic model (define it in models.py)
- Registers `parse_bill_image` as a tool

Add tests in tests/test_bill_parser.py with a sample bill PNG (mock the
Anthropic call — don't hit the real API in tests).
```

After prompt 4, the pattern is established. Every subsequent capability is the same shape: pick a notebook chunk → implement the module → register the tool → write a test. The chatbot becomes more useful with each one.

---

## Sprint roadmap

- **Sprint 1 (foundation):** prompts 1–3 above. Repo cleanly structured, scaffolded, deployable. No real features yet, but the chatbot loop runs end-to-end with one stub tool that returns "Hello, world."
- **Sprint 2 (bill spine):** `parse_bill_image`, `store_bill`, `list_user_bills`, `compare_bill_periods`. Streamlit upload widget. Chatbot can answer "why was my bill higher last month?"
- **Sprint 3 (tariff awareness):** ANEEL client, bandeira, Tarifa Branca simulator. Chatbot can answer "should I switch to Tarifa Branca?" and "what's the bandeira this month doing to my bill?"
- **Sprint 4 (solar feasibility):** pvlib + NASA POWER, sizing, payback. Chatbot can answer "should I get solar?" with grounded numbers for the user's exact location and consumption.

After v1: inverter integration (Growatt-first), WhatsApp channel, anomaly alerts, NILM disaggregation.

---

## Things to decide before sprint 2

- **Bill format coverage.** Brazilian bills vary by distributor. Start with one (Enel RJ if that's your local) and add more on demand. Don't over-engineer the parser.
- **User identity.** v1 can be a single-user app (no auth) keyed off a session ID. Auth is a sprint-5 problem.
- **Cost guardrails.** Each chatbot turn costs Anthropic API credits. Set a per-session token budget early so a runaway loop doesn't surprise you.
- **Privacy.** Bills contain CPF/CNPJ and address. Decide what you store, encrypted vs not, and put it in a `PRIVACY.md` from day one. LGPD applies.

---

## Honest caveats

- **Bill OCR via vision will be ~90% reliable on first pass.** Plan for a manual-correction UI in the chatbot ("I read R$ 487.30 — is that right?") before assuming the extraction is right.
- **`pvlib` requires careful weather data.** TMY (typical meteorological year) data via PVGIS is fine for feasibility, but real production forecasting needs current weather. Don't promise users predictions you can't back up.
- **ANEEL Open Data API is not always fast or stable.** Cache aggressively (DuckDB-backed cache with TTL). Don't call it on every chatbot turn.
- **The chatbot will hallucinate without strict tool use discipline.** The system prompt rule "never invent numbers" is doing a lot of work — back it up by making sure every numeric claim has a tool to source it from. Audit conversations weekly.
