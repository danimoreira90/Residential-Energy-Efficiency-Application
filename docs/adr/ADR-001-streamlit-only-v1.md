# ADR-001: Streamlit as sole UI channel for v1

**Status:** Accepted
**Date:** 2026-05-10
**Deciders:** Daniel Moreira
**Tags:** architecture, ui, frontend

## Context

v1 needs a web UI to: accept bill images, display chatbot turns, show the
session token counter (HR-7), and let the user trigger new conversations.
Three options were evaluated:

1. **Streamlit** — rapid prototyping, Python-native, no separate frontend
   build step. The existing codebase already has a Streamlit shell.
2. **FastAPI + React** — production-grade, but a full separate frontend
   project with CI/CD, TypeScript, and build tooling. Appropriate for v2+.
3. **FastAPI + Jinja2** — server-rendered HTML; simple, but low flexibility
   for a chat-style UI with streaming responses.

v1 is a single-user prototype targeting one household. It does not need the
concurrency or scalability of a dedicated frontend stack.

## Decision

Use Streamlit as the sole UI channel for v1. `src/energia/ui/streamlit_app.py`
is the application entrypoint. No FastAPI, no React.

The entrypoint is invoked with:

```bash
uv run streamlit run src/energia/ui/streamlit_app.py
```

## CAP Trade-off Statement

Not applicable to the UI layer. The UI is stateless between page refreshes;
all state is held in `st.session_state` (in-process, single-user) or in
DuckDB (see ADR-003).

## 12-Factor Compliance

- **Factor III:** No config is hardcoded in the UI; all values flow through
  `energia.config.settings`.
- **Factor VI:** The Streamlit process is stateless across sessions (each
  page load is a fresh Python run). Session-scoped state uses
  `st.session_state`, which is explicitly session-local.
- **Factor XI:** Logs go to stdout via Python `logging`, not to files.

## Consequences

**Positive:**
- Zero JavaScript, zero build step; rapid iteration from Python only.
- `st.chat_message` provides a functional chatbot layout out of the box.
- `st.file_uploader` handles bill image upload natively.
- Session identity via `st.session_state` gives us user-scoped data within
  a Streamlit session with no auth complexity.

**Negative:**
- Streamlit's concurrency model (one Python process per user, not
  thread-safe shared state) limits scaling beyond a handful of concurrent
  users. Acceptable for v1 single-user use.
- Native mobile experience is poor without a Progressive Web App wrapper.
  Post-v1 (HR-2 out of scope): WhatsApp channel.
- Real-time streaming responses require `st.write_stream`, available since
  Streamlit 1.31 — pin `streamlit>=1.36` to guarantee this.

**Neutral:**
- A FastAPI backend is explicitly out of v1 scope (HR-2). Any future REST
  or WebSocket API layer requires a new ADR before scaffolding begins.

## Alternatives considered

- `gradio` — similar to Streamlit but less flexible for multi-step chat
  flows. Rejected: smaller ecosystem, fewer contributors.
- CLI chatbot — possible for developer testing only; not a user-facing v1
  channel.

## References

- HR-2: v1 scope locked — WhatsApp channel is explicitly out of scope.
- `src/energia/ui/streamlit_app.py` — UI entrypoint (added in Task 0.5).
- ADR-002: LangGraph for chat orchestration.
