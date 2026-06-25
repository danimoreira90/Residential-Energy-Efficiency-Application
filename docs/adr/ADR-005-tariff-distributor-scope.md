# ADR-005: get_tariff scope — pure lookup, single distributor, disclaimers over numbers

**Status:** Accepted
**Date:** 2026-06-25
**Deciders:** Daniel Moreira
**Tags:** architecture, tariff, chatbot, hr-5, edd

## Context

`get_tariff` is the LLM-facing tool that surfaces the regulated tariff from the
ADR-004 snapshot. Three design questions had to be settled before building it:

1. **What does the tool read?** Should it consult bills / ChatState to tailor
   the answer, or be a pure function of its arguments?
2. **What does it return when it cannot give an honest number** — a subsidized
   subclass (`baixa_renda`, whose discount v1 does not compute) or a
   distributor with no committed snapshot?
3. **How does it resolve a distributor** today, and how will it grow when a
   second distributor's snapshot is added?

The forces: HR-5 (never invent a number; never imply a number we don't have),
HR-6 (don't touch bill PII unless needed), and TD-018's hard-won lesson that a
tariff number must be clearly distinguished from a bill's *blended effective
rate* (`total_brl / consumption_kwh`) so the model doesn't narrate false causes.

## Decision

1. **`get_tariff` is a PURE LOOKUP.** Arguments in (`distributor`,
   `subclass="convencional"`), regulated tariff or disclaimer out. No DB reads,
   no ChatState bill reads, no causal language. It loads the snapshot via
   `load_snapshot` and computes nothing the snapshot doesn't already define
   (`base_tariff_brl_per_kwh` = (TUSD + TE) / 1000). The `InjectedState`
   parameter is kept for tool-signature parity but is intentionally unread.

2. **Honest branches carry ZERO numbers (HR-5):**
   - `baixa_renda` (or any subclass whose `v1_supported` is `False`) → a PT-BR
     disclaimer that the account is subsidized and v1 does not compute the
     discount. No number.
   - An unrecognized subclass → a disclaimer naming `convencional` as covered.
     No number.
   - A distributor that matches neither the snapshot's canonical name nor any
     alias → a "fora do escopo" message naming Enel RJ as the only covered
     distributor. **No fallback to Enel's numbers for another distributor.**

3. **Single-distributor resolution today; Protocol deferred.** v1 ships exactly
   one snapshot (Enel RJ). Resolution matches the user's distributor string
   against the snapshot's canonical name + aliases, case-insensitively and
   accent-tolerantly (`unicodedata` NFKD + casefold). A general
   `DistributorResolver` Protocol and any generic cross-distributor fallback
   are **deferred until a second real snapshot exists** — see the honesty-risk
   note below and TD-019.

## Honesty-risk note (the deferred-abstraction trap)

Building a multi-distributor resolver or a "nearest distributor" fallback now,
with only one snapshot, is an ADR-007-class honesty risk: an abstraction
designed against a single example tends to encode that example's assumptions
and, worse, invites a fallback that returns *some* number when the right answer
is "I don't have that distributor." A fallback that silently substitutes Enel's
tariff for `Light` or `CPFL` would be a direct HR-5 violation dressed up as a
feature. The honest v1 behaviour is to cover exactly what we have a verified
snapshot for and disclaim the rest. The resolver abstraction earns its keep
only when a second verified snapshot creates a real second case to generalize
from.

## Consequences

**Positive:**
- HR-5 holds by construction: the only numbers `get_tariff` emits come from a
  committed, audited snapshot; every other path is a number-free disclaimer.
- The tariff number is framed in the response as the regulated TUSD + TE tariff,
  explicitly *not* the blended effective rate and *not* a causal explanation —
  closing the TD-018 narration-leak risk at the tool layer.
- HR-6 is trivially satisfied: the tool never reads or logs bill data; its logs
  carry only distributor / subclass / slug strings.

**Negative:**
- Adding a distributor is two steps (commit a snapshot, confirm resolution),
  not a config toggle. Intended — each distributor's tariff is an HR-5 artifact.
- Accent/case resolution is heuristic; a wildly misspelled distributor falls to
  the out-of-scope branch (which is the safe failure).

**Neutral:**
- The unread `InjectedState` parameter is dead weight today; it exists so the
  signature matches the other tools and so a future bill-aware variant doesn't
  change the tool's call shape.

## References

- HR-5: never invent numbers; no fallback tariffs.
- HR-6: don't touch bill PII; PII-free logs.
- ADR-004: the snapshot source `get_tariff` reads.
- TD-018: effective rate ≠ regulated tariff; WHAT-not-WHY framing.
- TD-019: deferred multi-distributor Protocol + generic fallback.
- `src/energia/chat/tools/tariff.py` — the tool (Task 2.3).
- `tests/chat/tools/test_tariff.py` — resolution, disclaimer, HR-5/HR-6 tests.
