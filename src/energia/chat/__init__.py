"""LangGraph chatbot orchestrator, tools, audit, and budget enforcement.

Sprint 0 (Task 0.5) adds:
- state.py    — ChatState TypedDict with add_messages reducer.
- graph.py    — StateGraph: agent node + ToolNode + conditional routing.
- nodes.py    — agent_node, tool_node, route_after_agent.
- audit.py    — DuckDBAuditCallback (HR-5: every tool call logged).
- budget.py   — TokenBudgetCallback + TokenBudgetExceeded (HR-7).
- memory.py   — Conversation persistence helpers.
- prompts.py  — System prompt in PT-BR (PROTECTED PATH — HR-4).
- tools/      — LangChain @tool wrappers around domain functions.
"""
