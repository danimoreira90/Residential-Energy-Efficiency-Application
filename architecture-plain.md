# How this application is built — plain language

This is a walkthrough of how the chatbot works under the hood. It's meant to be readable without prior LLM or LangChain background. Save it in `docs/architecture-plain.md` so you can come back to it.

---

## What this app does

A user opens a chat in a browser. They upload a photo of their Brazilian energy bill. The chatbot reads the bill, stores it, and then answers questions like "why was last month more expensive?" or "would solar panels pay back at my house?". The chatbot answers in Portuguese, in plain language, but every number it gives the user comes from a real calculation — never a guess.

That last sentence is the most important rule of the whole project. It's called HR-5 in the docs.

---

## The pieces

### Streamlit — the chat window

This is what the user actually sees and interacts with. A web page running on `http://localhost:8501`. It has a chat area, a place to upload files, and a sidebar for settings. Streamlit is a Python library that lets us build this kind of interface without writing JavaScript.

When the user types a message and hits enter, Streamlit hands the message off to the next layer.

### LangGraph — the conversation flow controller

LangGraph receives the message and decides what happens next. Think of it as a flowchart. For v1, the flowchart is small:

```
START → [agent] → does the agent want to use a tool? → yes → [tools] → back to [agent]
                                                     → no  → END (show response to user)
```

In words: the agent (Claude) looks at the message. If Claude needs to compute something, the flowchart routes to the tools step. The tools do their work and return numbers. The numbers go back to Claude. Claude turns them into a friendly sentence. Done.

Later (Sprint 1+) we add more steps. For example: parsing a bill might need a confirmation step. We add a node to the flowchart for that. LangGraph makes this kind of addition cheap and clean.

### Claude — the reasoning engine

Claude is the AI that does the talking. We send it the conversation so far plus a list of tools it can call. Claude decides:

- "I can answer this from what I already know" → writes a response
- "I need to calculate something" → asks LangGraph to call a specific tool

Claude never does math itself. It picks tools and narrates results. This separation is what keeps the answers grounded.

### Tools — Python functions that compute things

Every "thing the chatbot can do" is a regular Python function. Example:

```python
def estimate_solar_system(lat, lon, monthly_kwh, roof_orientation):
    # Real math: pull weather data, run pvlib calculations
    return {"recommended_kwp": 4.2, "monthly_generation": 520, ...}
```

That function lives in `src/energia/solar/sizing.py`. It can be tested by itself. It has no idea what Claude or LangGraph are.

A thin wrapper in `src/energia/chat/tools/solar.py` registers it as a tool that Claude can call. The wrapper does two things: it tells Claude what the tool does (via the docstring), and what inputs it needs (via a Pydantic schema). Pydantic is a Python library that validates inputs — if Claude passes the wrong shape, we get an error before the function even runs.

### DuckDB — the local database

DuckDB is a database that lives in a single file on your computer (`data/energia.duckdb`). It's like SQLite but better at analytical queries. We use it to store:

- **Users** — your session ID (no accounts in v1)
- **Conversations** — each chat session
- **Messages** — every message you and the chatbot exchange
- **Tool calls** — every time the chatbot calls a tool, with what input, what output, how long it took
- **Bills** — every bill you upload, parsed into structured data

The tool calls table is the audit trail. It's how we satisfy HR-5 — we can always go back and see "what did the chatbot claim, and which tool calculation did that come from?"

### External data sources

We don't store tariff or weather data ourselves. We fetch it on demand from:

- **ANEEL Open Data** — the Brazilian energy regulator publishes tariffs by distributor and the monthly "bandeira" flag (the surcharge color).
- **NASA POWER** — free worldwide weather data, including hourly solar irradiance. We need this for solar feasibility math.

Both responses are cached locally (TTL = how long before we re-fetch) so we don't hammer their servers and so we work fine when they're slow or down.

---

## How a single message flows through

User uploads a bill image and asks: *"Por que minha conta de outubro foi mais cara que setembro?"*

1. Streamlit receives the message and image.
2. Streamlit calls `GRAPH.invoke(...)` — that's LangGraph's "run the flowchart" function. It passes the message, the image, and the user's session ID.
3. LangGraph enters the `agent` node. It sends everything to Claude: the conversation history + the system prompt + the list of available tools (including `parse_bill_image`, `compare_bill_periods`, etc.).
4. Claude responds: "I need to call `parse_bill_image` first." (Claude doesn't *say* this in words to the user; it returns a structured tool call.)
5. LangGraph routes to the `tools` node. The `parse_bill_image` function runs. It sends the image to Claude's vision feature, gets back structured data (consumer of so many kWh, total R$, bandeira flag, etc.), and stores the bill in DuckDB.
6. The audit callback (`DuckDBAuditCallback`) logs this tool call to the database: which tool, what input (without the image bytes — those don't get logged, HR-6), what output, how long it took.
7. The token-budget callback (`TokenBudgetCallback`) adds up how many tokens this turn cost and stops the whole loop if we're over budget (HR-7).
8. LangGraph routes back to the `agent` node with the parsed bill in the conversation.
9. Claude now wants to compare it to September. It calls `compare_bill_periods` next.
10. That tool fetches the two bills from DuckDB, decomposes the R$ delta into components (consumption changed by X, tariff changed by Y, bandeira changed by Z), and returns the breakdown.
11. Audit log records this call too.
12. LangGraph routes back to `agent`. Claude now has everything it needs.
13. Claude writes a response in PT-BR: *"Sua conta de outubro foi R$ 47 mais cara que setembro. Disso, R$ 28 vieram da mudança de bandeira (verde → vermelha 1) e R$ 19 vieram do consumo, que subiu 8%..."*
14. LangGraph reaches END (Claude doesn't need more tools). The response goes back to Streamlit. Streamlit displays it.

The whole round trip is a few seconds. The audit log row sits in DuckDB forever (or until you delete the file).

---

## Why this design

**Why does Claude not compute things itself?**
Because LLMs hallucinate numbers. A model that says "your bill went up R$ 47" without a real calculation behind it might be off by R$ 100 and have no way of knowing. By making it call a tool for every number, we get auditable, reproducible answers.

**Why are tools plain Python functions?**
Because they're testable. We can unit-test `estimate_solar_system(lat=-22.92, lon=-42.83, ...)` directly, with no AI involved, and assert specific outputs. If a refactor accidentally breaks the math, the test catches it long before a user ever sees a wrong number.

**Why DuckDB and not Postgres?**
v1 is single-user, running on your laptop. DuckDB needs no setup — just a file. When we go multi-user (post-v1), we move to Postgres. The schema is the same; we'd swap the connector.

**Why no cloud monitoring (LangSmith)?**
Bill data has CPFs and addresses in it. Brazilian privacy law (LGPD) doesn't let us send that to third-party services casually. We keep audit data local in DuckDB.

**Why LangGraph instead of writing the loop ourselves?**
The Sprint 0 loop is so simple that writing it ourselves would be fine. But Sprint 1 adds the "confirm low-confidence bill extraction" step, Sprint 3 adds the multi-step solar input gathering. By Sprint 3, the hand-rolled state machine would be 200 lines and hard to follow. LangGraph keeps each step (each node) small and the flow visible.

---

## What Sprint 0 actually builds

The current sprint is foundation. By the end of it:

- A clean Python package at `src/energia/` with `uv`-managed dependencies.
- The DuckDB schema (users, conversations, messages, tool calls, bills).
- A working chat in Streamlit. You can type "oi, me chama de Daniel" and the chatbot will respond. It only knows one tool — `hello_world` — which just greets you back. But the wiring is real: it goes through LangGraph, calls the tool, logs to DuckDB, tracks tokens.
- A test suite that runs locally with `uv run pytest`.
- An "evals" framework that's ready to grade chatbot capabilities (pass rate, regression checks) — empty for now, populated in Sprint 1+.

Not useful for a real user yet. But every piece of the architecture above exists in code, tested, and wired together. The remaining sprints are about adding tools — each one is "implement one Python function, wrap it as a tool, write a test, register it" — and the chatbot gets more capable each time.

---

## What comes next, sprint by sprint

**Sprint 1 — Bill spine.** The first real tools: `parse_bill_image`, `store_bill`, `list_user_bills`, `compare_bill_periods`. By the end, you can upload three months of bills and ask the chatbot why one was more expensive — and the answer breaks down where the money went.

**Sprint 2 — Tariff awareness.** Tools that know about ANEEL tariffs, the monthly bandeira, and the "Tarifa Branca" time-of-use pricing option. The chatbot can answer "should I switch to Tarifa Branca?" and "what's this month's bandeira surcharge costing me?".

**Sprint 3 — Solar feasibility.** Tools that pull weather from NASA POWER, run pvlib's solar physics, and simulate year-by-year payback under Brazilian net-metering rules (Lei 14.300). The chatbot can answer "do solar panels pay back at my house in Maricá?" with real numbers.

After Sprint 3, v1 is done. Post-v1 ideas (inverter integration, WhatsApp delivery, NILM disaggregation) are explicitly out of scope right now — we ship v1 first, then revisit.
