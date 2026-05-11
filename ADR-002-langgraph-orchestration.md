# ADR-002: LangGraph for chat orchestration; custom HR-5 audit; no LangChain core

**Status:** Accepted
**Date:** 2026-05-10
**Deciders:** Daniel Moreira
**Tags:** architecture, chat, orchestration

## Context

The chatbot is the primary interface of the Residential Energy Efficiency Application. Its responsibilities are: (a) accept user messages and bill images, (b) call typed domain tools (bill parsing, tariff lookup, solar sizing), (c) narrate results in PT-BR, (d) maintain conversation history, (e) enforce HR-5 (no invented numbers — every quantitative claim originates from a tool call), and (f) enforce HR-7 (per-session token budget).

Two architectural options were considered seriously:

**Option A — Direct Anthropic SDK with a custom tool registry and a hand-rolled tool-use loop.** This is what KICKOFF.md originally proposed. The orchestrator is ~30 lines of `while True:` around `client.messages.create`; tools are registered via a decorator that exposes their JSON schemas to the API.

**Option B — LangGraph as the orchestrator, with `langchain-anthropic` for the model wrapper and `langchain-core` for the `@tool` decorator.** No `langchain` meta-package, no LCEL chains, no prompt templates, no agents from `langchain.agents`. State is a `TypedDict`; the graph is two nodes (agent, tools) plus one conditional edge.

A third option — full LangChain including chains, LCEL, and agents — was rejected without extensive evaluation. The abstractions duplicate things we already have clean (`prompts.py`, direct LangGraph nodes), and the framework's historical churn (the langchain → langchain-core split, recurrent agent API revisions) makes it a poor fit for a project that values stability over breadth of integrations.

## Decision

Adopt **Option B**: LangGraph for orchestration, `langchain-core` for tool definition and message types, `langchain-anthropic` for the model wrapper. Skip the rest of the LangChain ecosystem for v1.

Specific dependency surface:

```
langgraph >= 0.2
langchain-core >= 0.3
langchain-anthropic >= 0.2
```

Explicitly NOT in v1:

```
langchain                   (meta-package — chains, prompts, agents)
langchain-community         (third-party integrations)
langsmith                   (paid tracing SaaS — LGPD risk on Brazilian bill data)
```

Adopting any of the above post-v1 requires a new ADR.

## Architecture summary

- **State** is a `TypedDict` in `src/energia/chat/state.py`: a message list (with LangGraph's `add_messages` reducer), `user_id`, `conversation_id`, and `tokens_used`.
- **Graph** in `src/energia/chat/graph.py` has two nodes: `agent` (a `ChatAnthropic` call with all tools bound) and `tools` (LangGraph's prebuilt `ToolNode`). One conditional edge after `agent` routes to `tools` when there are tool calls, or to `END` otherwise. `tools` always loops back to `agent`.
- **Tools** are pure Python functions in domain modules (`src/energia/solar/sizing.py`, `src/energia/bill/parser.py`, etc.) wrapped by thin `@tool`-decorated functions in `src/energia/chat/tools/<domain>.py`. Domain functions are testable without LangChain. The wrappers are tested for schema and routing.
- **HR-5 audit** lives in `src/energia/chat/audit.py` as a `BaseCallbackHandler` (`DuckDBAuditCallback`) that writes to the `tool_calls` table on every `on_tool_start` / `on_tool_end` / `on_tool_error`. This is our audit trail, not LangSmith. Independent of the framework.
- **HR-7 cost guardrail** lives in `src/energia/chat/budget.py` as a second callback (`TokenBudgetCallback`) that accumulates `usage_metadata` on each `on_llm_end` and raises `TokenBudgetExceeded` past threshold. The graph caller (`ui/streamlit_app.py`) catches the exception and renders a user-friendly message.
- **Checkpointing** for v1 is in-process only (`MemorySaver`). Cross-session resume is a Sprint 4+ decision, not a v1 concern.

## Consequences

Positive:

- The two-node graph shape pays off as flows get richer. Sprint 1's bill ingestion ("parsed → uncertain → ask user → confirmed → ready") and Sprint 3's solar feasibility intake ("collecting lat/lon → orientation → tilt → consumption → simulating → presenting") map naturally onto extra nodes plus conditional edges, with no rewrite of the spine.
- LangGraph's `ToolNode` handles the parallel-tool-call case correctly out of the box. With a hand-rolled loop we'd have to write that ourselves and write tests for it.
- `usage_metadata` on `ChatAnthropic` responses standardizes token accounting across models — easier to swap to Haiku (HR-7 fallback) or future Anthropic models without changing the budget callback.
- Domain functions stay pure. Tests for `solar.sizing.estimate_solar_system` do not import LangChain.
- Future RAG over ANEEL regulations (post-v1) can add a `retrieval` node to the graph without redesigning the orchestrator.

Negative:

- One more framework to learn. LangGraph documentation is decent but the abstractions (reducers, conditional edges, channels) take some ramp-up.
- Three packages with their own release cadence (`langgraph`, `langchain-core`, `langchain-anthropic`). Pinning ranges in `pyproject.toml` and reviewing release notes before bumps is now part of operating the project.
- Debugging is one layer of indirection deeper than direct SDK. Mitigation: HR-5 audit callback gives us full visibility into tool calls and timing without needing LangSmith.
- LangGraph's parallel-tool-call execution means our audit callback must be thread-safe / re-entrant-safe. The DuckDB connection helper in `db.connect()` is connection-per-call, which sidesteps the issue, but it's worth flagging in `audit.py`.
- The `langchain-anthropic` package is a wrapper over the official `anthropic` SDK. If a new Anthropic feature lands (e.g., a new tool-use parameter), there's a lag before `langchain-anthropic` exposes it. We pin `anthropic` directly so the underlying SDK is available if we need to drop into it.

Neutral:

- The `@tool` decorator from `langchain-core` and our originally proposed registry decorator are conceptually identical. Choosing the LangChain decorator is a vocabulary choice — Pydantic input model, docstring as description, function body executes — not a capability change.

## Rejected: full LangChain

The `langchain` meta-package brings in chains (LCEL), prompt templates (`ChatPromptTemplate`), output parsers, and the legacy agent abstractions. For our project:

- `prompts.py` is a Protected Path containing a single PT-BR system prompt. We don't need `ChatPromptTemplate`'s composition.
- We have no chain that wouldn't reduce more cleanly to a LangGraph node.
- The legacy agent abstractions (`AgentExecutor`, etc.) have been superseded by LangGraph itself.

LangChain core would add ~80MB of transitive dependencies and an abstraction layer we'd never use. Rejected.

## Rejected: LangSmith

LangSmith is a hosted tracing/observability service. It would:

- Send prompts, responses, and tool inputs/outputs to a third-party endpoint.
- Process Brazilian bill extraction data — including CPF, address, and installation numbers — through a foreign cloud service.

This conflicts with HR-6 (LGPD discipline on bill data). The custom `DuckDBAuditCallback` writing to the local DuckDB satisfies the same observability need without the data-residency problem. Rejected for v1. A v2+ revisit is possible if we add explicit anonymization at the callback layer and a clear LGPD privacy notice, but that is not free engineering work and not in scope.

## Rejected: direct Anthropic SDK (Option A)

The original recommendation. Rejected after Daniel's evaluation. The trade-offs were:

- **Plus:** ~30 lines of orchestrator code; minimum surface area; one less framework to learn; no third-party API churn risk.
- **Minus:** every multi-step flow (Sprint 1 bill confirmation, Sprint 3 incremental solar input gathering) becomes a hand-rolled state machine. The work is straightforward but accumulates; by Sprint 3 we'd have built a small LangGraph anyway.

Daniel's call. Documented for posterity. If post-v1 experience shows LangGraph is overhead-heavy for the actual workflow we land on, this ADR can be superseded.

## References

- LangGraph documentation: https://langchain-ai.github.io/langgraph/
- `langchain-anthropic` package: https://python.langchain.com/docs/integrations/chat/anthropic/
- HR-5 (LLM quantitative discipline): `CLAUDE.md`
- HR-6 (LGPD discipline on bill data): `CLAUDE.md`
- HR-7 (Cost guardrails on Anthropic API): `CLAUDE.md`
