# Residential Energy Efficiency Application — Project CLAUDE.md

**Version:** 1.0
**Date:** 2026-05-10
**Project:** Residential Energy Efficiency Application (Brazilian residential energy chatbot)
**Owner:** Daniel Moreira
**Repo:** github.com/danimoreira90/Residential-Energy-Efficiency-Application

---

## Inheritance

This project **extends** the global agentic engineering framework defined in `~/.claude/CLAUDE.md` (Claude Swarm v2.0) where it is present. If the global file is absent on a given machine, this file stands alone — Daniel's MacBook may have it, his Windows box may not, and the project must remain workable in both cases.

**You inherit, fully, when the global framework is present:**
- 13 Core Rules (research-first, TDD, EDD, SDD, verify-before-claim, anti-cheat, conventional commits, no secrets, type safety, security guardian on auth/data, db-architect on schema, 12-Factor, CAP statement)
- 4 architectural frameworks (12-Factor, CAP Theorem, C4 Model, ADR format)
- 3 methodologies always active (TDD, EDD, SDD)
- The Tier 2/3 specialist agents in `~/.claude/agents/`
- The rules in `~/.claude/rules/`
- The personal skills in `~/.claude/skills/`

**This file adds, in addition to the global framework:**
- Project identity, stack, and domain (residential energy, Brazil, LLM-led chatbot)
- Project-specific hard rules (overrides where applicable)
- Branch role system (orthogonal to the global Tier system)
- Protected paths specific to this repo
- Agent routing per project Role
- Known gaps in inherited Claude Swarm v2.0 (transparency)

**Read this file FIRST, then `~/.claude/CLAUDE.md` if it exists. Project-specific rules below override global rules where they conflict.**

---

## Project Identity

```yaml
name: Residential Energy Efficiency Application
type: B2C SaaS prototype (single-user MVP)
target_market: Brazilian residential customers (Group B1) — Maricá-RJ first
core_pillars:
  - Bill analysis and coaching (parse conta de luz, explain anomalies, suggest savings)
  - Solar feasibility (sizing + payback for prospective PV adopters)
  - Conversational interface (Anthropic Claude with strict tool-use discipline)
status: kickoff (week 0 — repo exists as ~95% Jupyter notebooks, needs migration)
roadmap_to_v1: 4 sprints (~4 weeks)
```

## Stack

```yaml
runtime: python 3.11+
package_manager: uv (uv.lock committed alongside pyproject.toml)
layout: single-package src/energia/

ui:
  framework: streamlit (latest)
  patterns: st.chat_message + sidebar
  no_authentication: true   # session-id keyed, single user (HR-2)

llm:
  provider: anthropic
  sdk: anthropic python sdk
  model: claude-sonnet-4-6  # cheap enough, strong tool use, vision-capable
  fallback: claude-haiku-4-5-20251001  # if cost becomes an issue
  pattern: tool-use loop in src/energia/chat/orchestrator.py

solar_pv:
  library: pvlib
  weather_data: nasa power (free, global, decades of hourly history)
  forecast_data: forecast.solar (1-3 day production prediction; v2)

data:
  db: duckdb (single local file at data/energia.duckdb, gitignored)
  http_cache: requests-cache against aneel + nasa power calls
  validation: pydantic 2

tariff_source:
  primary: aneel dados abertos rest api (dadosabertos.aneel.gov.br)
  cached: yes — TTL 24h on tariff data, 1h on bandeira
  fallback: hand-curated csv per distributor (when ANEEL is down)

dev_environment:
  os_target: windows 11 (primary), linux/mac (secondary)
  shell: powershell on windows, bash elsewhere
  editor: vscode
  agent_runtime: claude code 2.1.138+
```

## Hard Rules (Project-Specific Overrides)

These rules **override** anything in the global Claude Swarm where they conflict. Listed by priority. Mirrors `AGENTS.md` for tools that don't read this file.

### HR-1 — Manual Commits Only (overrides Swarm Rule 7)

**Rule:** ALL git commits in this project MUST be executed MANUALLY by Daniel.

**Forbidden actions for any agent:**
- `git add` (any path)
- `git commit` (any message)
- `git push` (any remote)
- `gh pr create` / `gh pr merge`
- Any wrapper, alias, hook, or script that triggers the above

**Permitted:**
- Show `git status` and `git diff --cached`
- Suggest commit message in plain text for Daniel to copy/paste
- Stage files only when Daniel says "stage X for me"
- Run `git pull`, `git fetch`, `git checkout`, `git branch`, `git log` (read-only operations)

**Violation:** if an agent commits anything automatically, Daniel reverts the commit and the agent's session ends.

### HR-2 — v1 Scope is Locked

**Rule:** The following are explicitly OUT of v1 scope and must not be scaffolded, designed for, or partially implemented:

- WhatsApp delivery channel (any provider)
- Live inverter integration (Growatt, SolarEdge, Enphase, Modbus TCP, etc.)
- NILM / energy disaggregation (`nilmtk` and friends)
- Smart-home control or load shifting automation
- Multi-tenant authentication or RBAC
- Commercial / industrial customers (Group A tariffs)

**Why:** these are real product directions, but each one would force architectural decisions before we have a working v1. Premature commitment = expensive rework.

**Implication for agents:**
- Do NOT scaffold WhatsApp clients, queues, or webhook handlers.
- Do NOT design endpoints assuming inverter telemetry will arrive.
- Do NOT add `nilmtk` or HMM disaggregation models to dependencies.
- v1 chatbot suggests actions for the human to take manually. It does not control hardware.

If a feature request implies any of the above, stop and flag it. Do not silently assume "I'll just stub it for now."

### HR-3 — Migrations Already Applied Are Immutable

**Rule:** Any migration in `migrations/` with a timestamp ≤ today MUST NOT be edited. New behavior = new migration with new timestamp.

**Why:** even though we use a local DuckDB file, the discipline of forward-only migrations is what keeps Daniel's dev DB and the test DB in sync. Editing applied migrations is the fastest way to corrupt that.

**Enforcement:** see `docs/agentic-engineering/PROTECTED-PATHS.md`.

### HR-4 — Test File Editing Requires Approval

This **refines** (does not override) the inherited anti-cheat rules:

**Permitted by agent:** CREATE new test files (TDD red-green-refactor as per global skill `tdd`).
**Forbidden by agent without explicit Daniel approval:**
- EDIT existing test files (`tests/**/test_*.py`)
- DELETE existing tests
- Add `@pytest.mark.skip`, `@pytest.mark.xfail`, or `@pytest.mark.skipif` to existing tests
- Soften assertions (e.g., `assert x == 5` → `assert x > 0`)
- Replace specific mocks with `Mock()` catch-alls in existing tests

**Override permitted only with:** explicit message from Daniel like "OK to edit test_bill_parser.py because Y" + entry in `docs/tech-debt.md` with ID.

### HR-5 — LLM Quantitative Discipline (project-specific, no analog in Swarm)

**Rule:** the chatbot must never invent numbers. Every quantitative claim in a chatbot response must originate from a tool call.

**Implication for agents implementing chatbot features:**

- Each capability is a typed Python function registered via `energia.chat.tools.registry`. The LLM picks tools and narrates results; it does not compute.
- All numeric computation lives inside the tool function. Never in the system prompt. Never in free-text post-processing the model does after a tool result.
- The system prompt MUST contain (in PT-BR): "Você nunca inventa números — toda afirmação quantitativa vem de uma chamada de ferramenta. Se não houver ferramenta disponível, diga que não sabe."
- Every conversation turn that produces a numeric claim must be auditable: `user message → tool call(s) → result(s) → narration`. Logging in `src/energia/chat/orchestrator.py` must capture this chain.

**Eval gate:** before any new chatbot capability ships, a capability eval (`evals/<tool_name>.jsonl`) must achieve pass@3 ≥ 0.90, and the regression suite must achieve pass^3 = 1.00. See EDD discipline in the global framework.

### HR-6 — LGPD Discipline on Bill Data (project-specific)

**Rule:** Brazilian bills contain personal data (CPF/CNPJ, address, installation number — UC). Agents must:

- Never log bill PDFs, photos, or extracted CPF/CNPJ to stdout, files, or external services.
- Never embed user identifiers in Anthropic API `metadata` field or any external request.
- Store bill data only in `data/energia.duckdb` (gitignored).
- When uncertain whether a field is PII, treat it as PII.

When implementing bill parsing or any feature that handles bill data, write a one-line note in `docs/lgpd-log.md` describing what data is touched and why.

### HR-7 — Cost Guardrails on Anthropic API

**Rule:** every chatbot session has a per-session token budget. The orchestrator (`src/energia/chat/orchestrator.py`) MUST:

- Track cumulative input + output tokens per session.
- Halt with a graceful error message if a session exceeds 200,000 tokens cumulatively.
- Log warning at 50% and 80% of budget.

The budget number is a project setting in `src/energia/config.py` and can be tuned, but the mechanism must always exist. Runaway tool-use loops are a real failure mode and a real cost.

---

## Branch Roles (Orthogonal to Tier System)

The Claude Swarm Tier system answers **"who knows how to do this?"** — orchestrator delegates to specialists.

The project Role system answers **"what type of change is this?"** — branch naming and scope.

The two coexist: a `feature/solar-sizing-tool` branch invokes the orchestrator, which delegates to `ai-ml-engineer` (for tool design) and `lang-python` (Tier 3) for implementation.

**The 6 Roles:**

| Role | Branch prefix | When | Invoke (Tier 2 / 3) |
|---|---|---|---|
| `feature/*` | `feature/<short-name>` | New chatbot capability, new Streamlit page, new module | orchestrator → planner → builder → ai-ml-engineer OR backend-expert → lang-python |
| `data/*` | `data/<short-name>` | New external data source (ANEEL endpoint, distributor bill format, NASA POWER, weather) | orchestrator → builder → db-architect → lang-python |
| `quality/*` | `quality/<short-name>` | Tests, evals, docs, ADRs, observability | orchestrator → qa-champion → doc-engineer |
| `infra/*` | `infra/<short-name>` | CI/CD, deploy, secrets, monitoring | orchestrator → devops-engineer → cloud-engineer → security-guardian |
| `bugfix/*` | `bugfix/issue-<n>-<short>` | Specific bug referenced by issue | orchestrator → planner → builder + qa-champion |
| `chore/*` | `chore/<short-name>` | Maintenance (deps, configs, gitignore, refactor) | orchestrator → builder (lightweight, often skip Tier 2 specialists) |

Detailed role descriptions, scoping rules, and invocation patterns live in `docs/agentic-engineering/ROLES.md` (to be created during Sprint 1).

---

## Protected Paths (Project-Specific)

Agents may NOT modify the following without explicit Daniel approval:

```
migrations/2026*.sql                  # Applied to local DuckDB (HR-3)
docs/adr/0*.md                        # Approved ADRs are immutable (create new ones to revise)
.github/                              # CI configs (when added)
.gitattributes
tests/**/test_*.py                    # Editing forbidden (HR-4); creation permitted
evals/**/*.jsonl                      # Eval baselines are append-only
src/energia/chat/prompts.py           # System prompt; touch only via SPEC + Daniel
```

Editable with review (Daniel reads diff before approval):

```
pyproject.toml                        # New deps require ADR
uv.lock
ruff.toml
pyrightconfig.json
.gitignore
.claude/settings.local.json
```

Free to edit by agent (within role scope):

```
src/energia/**/*.py (NOT chat/prompts.py, NOT in tests/)
docs/sessions/**, docs/specs/**, docs/decisions/**
notebooks/**                          # Scratch only — never imported by src/
```

Full path-by-path table: `docs/agentic-engineering/PROTECTED-PATHS.md`.

---

## Skills/Agents Available in This Context

**From Claude Swarm v2.0 (~/.claude/, inherited where present):**

```
Skills (always loadable when global framework is installed):
  anti-cheat                    Anti-fraud test integrity
  blueprint                     Multi-PR / multi-session project planning
  eval-driven-development       EDD lifecycle (5 phases, pass@3/pass^3 gates)
  memory-management             Session persistence
  spec-driven-dev               SDD protocol (SPEC.md → PLAN.md → subagent execution)
  system-design                 C4 + CAP decision matrix
  twelve-factor                 12-Factor compliance audit

Agents (Tier 2 specialists):
  ai-ml-engineer  architect  backend-expert  builder  cloud-engineer
  db-architect  devops-engineer  doc-engineer  frontend-expert
  git-master  orchestrator  planner  qa-champion  security-guardian

Agents (Tier 3 micro-executors):
  lang-python  tool-docker

Rules (always active):
  anti-cheat-discipline.md      coding-standards.md      edd-discipline.md
  git-conventions.md            security.md              tdd-discipline.md
  testing-requirements.md       verification-discipline.md
```

**Project-local (to be created in Sprint 1):**

```
energia-tool-registry         Encodes the typed-tool pattern as a loadable skill,
                              including registration, eval scaffolding, and the HR-5
                              quantitative discipline checks
```

---

## Known Gaps in Inherited Claude Swarm v2.0

The global `~/.claude/CLAUDE.md` references resources that **may not exist yet** as of 2026-05-10. Behavior expected from agents when encountering these:

| Reference in global CLAUDE.md | Status | What agent should do |
|---|---|---|
| Slash commands `/plan`, `/build`, `/review`, `/deploy`, `/test`, `/git`, `/security`, `/migrate`, `/document`, `/swarm`, `/architect`, `/rag`, `/mcp`, `/loop` | LIKELY NOT IMPLEMENTED | Apply principle/intent manually using available tools. Do NOT improvise silently — acknowledge the gap. |
| Skills referenced but not present: `research-first`, `tdd-workflow`, `autonomous-loop`, `code-review`, `rag-pipeline`, `agent-builder`, `mcp-builder`, `db-migrations`, `cloud-deploy`, `ci-cd-pipeline`, `refactor-clean`, `memory-context` | LIKELY NOT IMPLEMENTED | Use the closest available skill or rule, OR fallback to disciplined manual execution. Acknowledge the gap. |
| `mcp-configs/mcp-servers.json` | NOT FOUND | MCP servers configured per-machine. Run `claude mcp list` to see what's actually available. |
| `hooks/` (pre-commit, post-tool, session-persist) | LIKELY NOT IMPLEMENTED | Hooks do NOT fire automatically. Daniel runs lint/typecheck/tests manually. |
| Global framework absent entirely | POSSIBLE on a fresh machine | Operate from this CLAUDE.md + AGENTS.md alone. Surface a one-line note that global framework was not found, then proceed. |

These gaps are tracked in `docs/tech-debt.md` (project-level) and do NOT block development.

---

## Quick Reference for Agents

```
Before any task:
  1. Read this file
  2. Read ~/.claude/CLAUDE.md (Claude Swarm v2.0) — if present
  3. Read CONTEXT.md (domain glossary)
  4. Read KICKOFF.md (architecture and tool-registry pattern)
  5. Read PLAN.md for the current sprint task
  6. Map the codebase before acting

Before any commit (DANIEL ONLY):
  1. Show git diff --cached
  2. Run lint, typecheck, tests
  3. For chatbot features: run evals (capability + regression)
  4. Verify Honest Reporting Mandate (real output, no summaries)
  5. Daniel runs git add / commit / push manually

When uncertain:
  Stop. Report uncertainty. List 2-3 options with trade-offs. Wait for Daniel.
```

---

## Pointers

- Generic multi-model agent rules: `AGENTS.md`
- Domain glossary: `CONTEXT.md`
- Architecture blueprint and tool-registry pattern: `KICKOFF.md`
- Sprint-by-sprint execution plan: `PLAN.md`
- Agentic engineering details: `docs/agentic-engineering/README.md`
- ADRs: `docs/adr/`
- Tech debt: `docs/tech-debt.md`
- Sessions log: `docs/sessions/`
- LGPD activity log: `docs/lgpd-log.md`
