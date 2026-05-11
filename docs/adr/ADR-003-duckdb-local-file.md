# ADR-003: DuckDB as local-file data store

**Status:** Accepted
**Date:** 2026-05-10
**Deciders:** Daniel Moreira
**Tags:** architecture, database, data, lgpd

## Context

v1 needs to persist: parsed bills (structured JSON extraction), conversation
history (HR-5 audit trail), tool call log (input + output per call), and user
session metadata. Three options were evaluated:

1. **DuckDB (local file)** — embedded analytical SQL database. Single file
   on disk. No server process. Python-native via `duckdb` package. Data stays
   on the user's machine (LGPD-friendly).
2. **SQLite** — mature, standard, single-file. No native JSON type. Row-
   oriented storage is slower for the analytical queries (period comparisons,
   aggregations over bill history) that make up most of our workload.
3. **PostgreSQL** — full-featured, production-grade. Requires a server
   process, connection string, and managed migrations tooling. Overkill for
   a single-user v1; introduces LGPD risk if hosted on an external server.

## Decision

Use DuckDB with a single local file at `data/energia.duckdb`. The file is
gitignored (HR-6). A forward-only migration runner in `src/energia/db.py`
manages schema changes via timestamped SQL files in `migrations/`.

## CAP Trade-off Statement

This system is **CP** (Consistency + Partition Tolerance). DuckDB is a local
embedded database with no network partition scenarios in v1 (single-user,
single-process). Under the only realistic "partition" (process crash mid-
write), DuckDB's WAL ensures the committed state is consistent on restart.
Availability is not a meaningful axis for a local file — the file either
exists or doesn't (user deleted it, not a system fault). Financial data
(bill totals in R$) requires consistency over availability.

## 12-Factor Compliance

- **Factor III (Config):** `DUCKDB_PATH` is a Pydantic Settings value loaded
  from `.env` — not hardcoded. Default: `data/energia.duckdb`.
- **Factor VI (Stateless processes):** DuckDB is the backing store; the
  Streamlit process holds no in-process mutable state that would be lost on
  restart (beyond `st.session_state`, which is intentionally session-scoped).
- **Factor XI (Logs):** DuckDB operations emit to Python `logging`, not to
  the DuckDB file. The DuckDB file is data, not logs.

## Consequences

**Positive:**
- No server setup. `uv sync && streamlit run` is the full quickstart.
- LGPD-compliant by default: bill PII (CPF, address, installation number)
  stays on the user's machine (HR-6).
- DuckDB handles analytical queries (period comparisons, aggregations over
  bill history) with columnar efficiency — better than SQLite for this
  workload.
- Native JSON type since DuckDB 0.9 — used for `bills.raw_extraction` and
  `tool_calls.input_json / output_json`.

**Negative:**
- Concurrent write access is limited (one write connection at a time).
  Not a concern for v1 single-user.
- Migration to PostgreSQL (post-v1, when multi-user auth is needed) requires
  a data migration. The forward-only runner is designed to make the schema
  history visible for a future export.

**Neutral:**
- `data/energia.duckdb` is gitignored. Each user carries their own data.
  No shared database in v1.

## Migration runner

`src/energia/db.py` provides `migrate()` (added in Task 0.4): reads
`migrations/*.sql` in lexicographic order, records applied migrations in a
`schema_migrations` table with the file's SHA-256 hash, and refuses to apply
a modified previously-applied migration (HR-3 enforcement). The runner is
idempotent — safe to call on every startup.

## References

- HR-3: Applied migrations are immutable once committed.
- HR-6: Bill PII must not leave the local machine.
- `src/energia/db.py` — connection helper and migration runner (Task 0.4).
- `migrations/` — timestamped SQL files; first migration added in Task 0.4.
- ADR-002: LangGraph orchestration — explains why DuckDB handles the HR-5
  audit trail instead of LangSmith.
