# ADR-004: Versioned local JSON snapshot as the authoritative tariff source

**Status:** Accepted
**Date:** 2026-06-25
**Deciders:** Daniel Moreira
**Tags:** architecture, data, tariff, edd, lgpd

## Context

The chatbot needs the regulated B1 tariff (TUSD + TE) for a distributor to
answer "qual a tarifa?" and, later, to decompose a bill change into tariff vs
bandeira vs tax effects (the TD-018 follow-up). HR-5 forbids inventing numbers:
every quantitative claim must come from a tool reading an authoritative source.

Two approaches were evaluated for *where that authoritative number lives at
runtime*:

1. **Live ANEEL Open Data REST client + cache** (the original ADR-006 plan,
   `docs/PLAN.md:1193`): query `dadosabertos.aneel.gov.br` on demand, backed by
   a `requests-cache` SQLite store (TTL 24h tariffs / 1h bandeira), with a
   hand-curated CSV fallback when ANEEL is down.
2. **Versioned local JSON snapshot**: a small, hand-verified JSON file per
   distributor committed to the repo at
   `src/energia/tariff/snapshots/<slug>.json`, transcribed from the published
   ANEEL homologation resolution (REH). A reader parses it; refreshing the
   number is a deliberate, reviewed edit — not a hot-path network call.

## Decision

Adopt **Option 2** — the versioned local JSON snapshot is the authoritative
runtime tariff source. The live ANEEL API client and `requests-cache` approach
described in the original plan is **dropped**.

`src/energia/tariff/snapshot.py` is the reader: Pydantic v2 models
(`TariffSnapshot`, `SubclassTariff`, `TariffSource`) plus `load_snapshot(slug)`,
which resolves the file relative to the module (not the CWD) and parses money
with `json.loads(..., parse_float=Decimal)` so R$/MWh values never round-trip
through binary float. Refreshing a tariff (new REH each year) is a separate,
off-hot-path step: edit the snapshot JSON, review the diff against the
published resolution, run the loader tests, commit.

## CAP Trade-off Statement

This system is **CP** (Consistency + Partition Tolerance) for tariff reads.
The snapshot is a local committed file: there is no network dependency at
runtime, so there is no partition to tolerate during a lookup, and the value
read is always the exact version committed (consistent + auditable). The live
API alternative would have been **AP** at best — available only when ANEEL is
reachable and the cache is warm, and serving a number whose provenance and
freshness vary per request. For a regulated price that changes about once a
year and must be auditable, consistency over availability is correct.

## 12-Factor Compliance

- **Factor III (Config):** the active distributor slug is a code/argument
  default (`"enel_rj"`), not a hardcoded secret; no API base URL or key is
  needed because there is no live call.
- **Factor VI (Stateless processes):** the reader is a pure function over a
  committed file — no cache file, no warm-up state, no background refresh.
- **Factor XI (Logs):** the loader does no network I/O and emits nothing on the
  hot path; provenance lives in the snapshot's `source` block, not in logs.

## Consequences

**Positive:**
- **Deterministic + offline:** lookups work with no network and give the same
  answer every run — directly testable and EDD-friendly.
- **Auditable (HR-5):** each snapshot records its `source` (REH resolution
  number, publish date, URL); the number the chatbot quotes traces to a
  specific published resolution.
- **No new dependency or LGPD surface:** drops `requests-cache` and an outbound
  call; nothing about a user or their bill leaves the machine for a tariff
  lookup (HR-6).
- **Simple failure mode:** an unknown slug is a clear `FileNotFoundError`, not a
  timeout / stale-cache / partial-response matrix.

**Negative:**
- **Manual refresh:** a new REH requires a human to transcribe and commit the
  new snapshot. Acceptable: tariffs change ~annually and the review *is* the
  HR-5 guarantee. A future fetch script may *propose* a snapshot diff, but the
  committed file stays the source of truth.
- **Staleness risk if forgotten:** mitigated by `effective_from` /
  `effective_to` in the snapshot, which a future check can use to warn when the
  active snapshot is past its validity window.

**Neutral:**
- Only one snapshot (Enel RJ) ships in v1. Multi-distributor resolution is a
  separate concern — see ADR-005.

## References

- HR-5: the chatbot never invents numbers; quantitative claims come from a tool.
- HR-6: no user/bill data leaves the machine (a tariff lookup makes no call).
- `src/energia/tariff/snapshot.py` — reader + Pydantic models (Task 2.1).
- `src/energia/tariff/snapshots/enel_rj.json` — the first committed snapshot.
- ADR-005: tariff distributor scope — the `get_tariff` tool over this snapshot.
- `docs/PLAN.md:1193` — the superseded live-API plan this ADR replaces.
