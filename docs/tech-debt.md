# Tech Debt Log

Entries logged when technical debt is knowingly introduced. Each entry includes:
what, why introduced, and resolution target.

Newest entries go at the top. When resolved, move to the "Resolved" section
at the bottom with the resolution date and the commit/PR that closed it.


## TD-019: get_tariff v1 — single-distributor resolution, multi-distributor Protocol + fallback deferred

**What.** Task 2.3 landed `get_tariff` on `feature/get-tariff` as a pure lookup
over the single committed Enel RJ snapshot (ADR-004 / ADR-005). Distributor
resolution is intentionally hardcoded to the one snapshot: the user's
`distributor` string is matched (case-insensitive, accent-tolerant via
`unicodedata` NFKD + casefold) against the snapshot's canonical name + aliases,
resolving to the constant slug `enel_rj`. There is:

- no `DistributorResolver` Protocol / slug map,
- no generic cross-distributor fallback,
- no second snapshot.

A distributor that doesn't match Enel RJ returns a number-free "fora do escopo"
disclaimer; `baixa_renda` (and any `v1_supported is False` subclass) returns a
number-free subsidized-account disclaimer (HR-5).

**Why introduced.** Designing a multi-distributor abstraction against a single
example is an ADR-007-class honesty risk (recorded in ADR-005). The worst
failure mode is a "nearest distributor" fallback that returns Enel's tariff for
`Light` / `CPFL` — a direct HR-5 violation wearing a feature's clothes. The
honest v1 covers exactly the one verified snapshot and disclaims the rest. The
resolver abstraction only earns its keep when a second *verified* snapshot
creates a real case to generalize from.

**Carried debt.**
1. `_V1_SLUG = "enel_rj"` and the single-snapshot resolution in
   `src/energia/chat/tools/tariff.py` must be generalized when distributor #2
   arrives — into a resolver that maps a normalized distributor name to a slug
   across all committed snapshots.
2. The `InjectedState` parameter on `get_tariff` is currently unread (kept for
   tool-signature parity / a future bill-aware variant). It is dead weight until
   then.

**Resolution target.** Re-open when a second distributor snapshot is committed.
At that point: add the resolver (Protocol or slug map), keep the
"no-match → out-of-scope, no fallback" guarantee, and extend
`tests/chat/tools/test_tariff.py` with the second distributor's resolution +
isolation cases. Drop or use the `state` parameter when a bill-aware tariff
variant actually needs it.

---

## TD-018: compare_bill_periods v1 — narrow scope + effective-rate ≠ tariff + WHAT-not-WHY framing

**What.** Task 1.5 landed on `feature/bill-comparison` with a deliberately
narrower scope than the PLAN.md Task 1.5 entry originally described, and a
honesty relabel of the rate field. The v1 tool reports three deltas only:

- `consumption_delta_kwh` + `consumption_delta_pct`
- `cost_delta_brl` + `cost_delta_pct`
- `effective_rate_delta_brl_per_kwh` — derived from
  `later.total_brl / later.consumption_kwh` minus the equivalent for the
  earlier period.

Field names use `effective_rate_*`, NEVER `tariff_*`. The "effective rate"
is the BLENDED R$/kWh the user actually paid (`total_brl / consumption_kwh`)
— it is NOT the regulated tariff (TUSD + TE). The tool's docstring,
narration seed, and PT-BR error messages describe WHAT moved (consumption
Δ, cost Δ, effective-rate Δ) — never WHY. No "sua tarifa subiu", no
"causou", no "porque". The test suite enforces both: the success-path
narration is asserted free of `tarifa`/`causou`/`porque`/`por que` tokens;
every not-enough-bills branch is asserted free of `kWh`/`R$`/`%` tokens
(HR-5 — no synthesized numbers when there's nothing to compute).

**Why introduced.**

1. **The PLAN.md Task 1.5 entry (lines 996-1004) specifies a 4-cell
   decomposition** — consumption effect + tariff effect + bandeira effect +
   tax effect + residual — that requires authoritative `tariff_a` and
   `tariff_b` values from ANEEL. Those don't exist in v1; `get_tariff` is
   Sprint 2 Task 2.3. Shipping the formula now would either invent tariff
   numbers (HR-5 violation) or derive them from the bill's `composition_json`
   (which is empirically unreliable per TD-014 — degrades to `null` on most
   bills). The narrower v1 scope reports only what we can compute honestly
   from stored Bill fields.

2. **The blended `total / consumption` is NOT a tariff.** It collapses
   regulated tariff (TUSD + TE), bandeira surcharge, ICMS, PIS/COFINS, COSIP
   and any minimum charge into one R$/kWh number. Calling it a "tariff" in
   the field name or narration would teach the LLM to attribute movement to
   the wrong cause. The relabel ("effective rate") is the structural HR-5
   win: we report a number we can derive, not a price we don't have.

3. **The full PLAN decomposition reopens as a Task 1.5 amendment after
   Sprint 2.** Once `get_tariff` returns authoritative TUSD/TE/bandeira
   surcharge values per period, the comparison can grow new cells
   (`tariff_effect_brl`, `bandeira_effect_brl`, `tax_effect_brl`, `residual`)
   on top of the existing scaffolding. The `BillPeriodComparison` Pydantic
   model becomes the slot for those additions; no schema change needed.

**Stale-correction gap (accepted v1 limitation).** `compare_bill_periods`
reads bills from `bill_store` — the *stored parse*. `correct_bill_field`
(Task 1.8) updates `current_bill` in ChatState but does NOT propagate
corrections back to `bill_store`. So a comparison run after an in-session
correction will use the pre-correction stored values. Low-impact given
current parse reliability (header fields are consistently MATCH per the
parser-reliability baseline + TD-016 normalizations), and the comparison
isn't a high-stakes financial calculation — it's a narration seed for the
LLM. Revisit if compare-after-correction starts producing visibly wrong
numbers. The fix would be either (a) propagating `correct_bill_field`
updates back to `bill_store` (adds a write path that has to handle the
"which row to update" question — bills are immutable by design today), or
(b) preferring `state["current_bill"]` over `bill_store` for the matching
period in `compare_bill_periods`. Both are larger than v1's scope.

**HR-4 status.** Zero existing tests modified. The registry sweep was clean
(every existing test uses membership / equality-of-views / lower-bound on
`ALL_TOOLS`, never an exact count or set equality). The new `find_by_period`
/ `find_latest_periods` tests live in a NEW file
(`tests/bill/test_store_periods.py`), separate from the existing
`tests/bill/test_store.py`, so `test_store.py` stays untouched.

**Resolution target.** Already resolved on this branch. Re-open as a Task
1.5 amendment when Sprint 2 Task 2.3 (`get_tariff`) lands — the
`BillPeriodComparison` model gains the causal cells, the tool's docstring
loses the "never WHY" constraint, and the test assertions on
`tarifa`/`causou`/`porque` get relaxed in favor of structural checks on the
new cells. The stale-correction gap is its own follow-up, tracked here for
when it becomes a real user complaint rather than a theoretical concern.

**Observed (Task 1.5 smoke test, Dez/2025 → Fev/2026):** model narrated "pode indicar
mudança de bandeira tarifária ou de impostos" — an unsupported causal hypothesis —
directly above its own "não consigo explicar por que" disclaimer. Confirms the
narration-layer leak is real, not theoretical. Fix: add a no-causal-speculation
clause to the system prompt (prompts.py) in Sprint 2 when get_tariff lands and
honest causal decomposition becomes possible. Repro: two bills with different
bandeira/consumption, then "compara minhas contas".

---

## TD-017: bill_store persistence + hash-cache — HR-4 fixture mocks + v1 scope narrowing

**What.** Task 1.4 landed on `feature/bill-store` with three changes:

1. **`src/energia/bill/store.py`** (new) — mirrors `chat/memory.py`.
   `find_by_hash(user_id, bill_hash)` returns a `Bill | None` rehydrated from
   `bills.raw_extraction` JSON via `Bill.model_validate`; `insert(user_id,
   bill, bill_hash)` writes top-level filterable columns plus
   `bill.model_dump(mode="json")` into `raw_extraction`, idempotent on
   duplicate hash (`ON CONFLICT (bill_hash) DO NOTHING; SELECT existing.id`)
   per PLAN.md line 663. No new migration — the existing
   `20260510_0001_initial_schema.sql` + `20260511_0001_bill_schema.sql`
   already cover every Bill field (HR-3 unchanged).

2. **Hash-cache seam in `src/energia/chat/tools/bill.py`** — at the top of
   `parse_bill_tool`, after reading `pending_bill_image`. Computes
   `sha256(image_bytes).hexdigest()`, consults `bill_store.find_by_hash` for
   `(user_id, hash)`; on hit, skips `parse_bill_image` entirely and emits a
   narration with the `" (lido da memória local — sem nova consulta de
   visão)"` marker. On miss, the existing parse path runs, then
   `bill_store.insert(...)`. **Insert failures do not surface as parse
   errors** — the parse already succeeded, the user gets their bill, and the
   cache is a perf/cost optimization not a correctness gate. Insert-failure
   log is **PII-free**: hash prefix only (8 hex chars), generic message,
   never bill fields or UC.

3. **HR-4 test edits (approved before implementation, all additive fixture
   plumbing — no assertion softened, no skip/xfail).** Five tests gained
   `mocker.patch` calls for `energia.chat.tools.bill.bill_store.find_by_hash`
   (returning None to force the cache-miss path) and, where the success
   branch runs, `bill_store.insert` (returning a fake UUID):

   - `tests/chat/tools/test_bill.py::test_parse_bill_tool_dispatches_and_clears_pending_image_on_success`
   - `tests/chat/tools/test_bill.py::test_parse_bill_tool_catches_billparseerror_and_returns_toolmessage`
   - `tests/chat/test_bill_persistence.py::test_parse_bill_success_populates_current_bill_in_state`
   - `tests/chat/test_bill_persistence.py::test_parse_bill_failure_does_not_populate_current_bill`
   - `tests/chat/test_bill_persistence.py::test_current_bill_survives_checkpoint_round_trip`

   Plus a new test (not an HR-4 edit — new file content):
   `tests/chat/tools/test_bill.py::test_parse_bill_tool_cache_hit_skips_vision_call_and_emits_marker`
   pins the cache-hit branch: `parse_bill_image` and `bill_store.insert` are
   never called; the Command update carries `cached.model_dump(mode="json")`;
   the ToolMessage content contains "memória local".

**Why introduced.** Task 1.4 in `docs/PLAN.md` originally listed three CRUD
tools (`store_bill` internal + `list_user_bills` + `get_bill` LLM-callable)
and the hash-cache. v1 narrowed this to the cache path only — neither
`list_user_bills` nor `get_bill` has a caller today; the only LLM-facing
bill tool is `parse_bill`. Task 1.5 (`compare_bill_periods`) is what will
actually drive cross-bill retrieval; when it lands it can call
`bill_store.find_by_period(...)` directly from Python without an
LLM-facing tool. Keeping the LLM tool surface narrow until something needs
it is HR-2 hygiene. The HR-4 fixture-mock edits are unavoidable: production
behavior changed (cache lookup before parse, insert after), and tests that
exercised the prior path must now mock the new collaborators or they would
hit the real `data/energia.duckdb`.

**HR-6 posture (Branch A — ADR-003 confirmed).** Plaintext
`installation_number` and full `raw_extraction` JSON in the gitignored
local DuckDB matches the existing schema and ADR-003's "local file is the
LGPD trust boundary" stance. Image bytes never written — only the hex
SHA-256. Insert-failure log redaction is enforced inside `parse_bill_tool`
(hash prefix only).

**Resolution target.** Already resolved on this branch. Revisit
`list_user_bills` / `get_bill` when Task 1.5 or a later feature actually
needs an LLM-facing retrieval tool. Revisit the HR-6 plaintext-UC posture
if Daniel ever tightens HR-6 to forbid plaintext UC even in the gitignored
local file — that would require a new ADR, a new forward-only migration,
and an encryption layer (separate task).

---

## TD-016: parser-reliability eval — composition dropped, installation_number normalized

**What.** Two coupled changes on `feature/parser-reliability-cleanup` after the
first real baseline run:

1. **Drop `composition` from the eval.** `BillLabel.composition`, the
   `_score_composition` function, and the composition entries in
   `score_bill`'s field assembly + `_all_miss` were removed from
   `src/energia/evals/parser_reliability.py`. The example labels
   (`evals/parser_reliability/labels.example.jsonl`) and the README field
   table / verdict notes were trimmed to match. Old `labels.jsonl` files
   carrying a `"composition"` key still load — Pydantic v2's default
   `extra="ignore"` drops unknown keys at `model_validate`. A new loader test
   (`test_load_labels_ignores_legacy_composition_key`) pins that contract.

2. **Normalize `installation_number` (UC) before comparing.** New helper
   `_normalize_uc(v) = v.strip().lstrip("0") or "0"` strips leading zeros on
   both expected and parsed values (Brazilian bill templates render the same
   UC with different left-pad widths). Wired in via a dedicated `_score_uc`
   so the normalization is scoped to that one field — like `Decimal` compare
   on `consumption_kwh`/`total_brl`. Redaction is **unchanged**: the
   normalized UCs never leave `_score_uc`'s scope; `_make_field` still drops
   `expected`/`parsed` to `None` for `installation_number`, and
   `_format_field_value` still emits `[redacted — HR-6]` regardless of
   verdict. The two existing redaction tests stay green; the new test
   (`test_score_installation_number_normalizes_leading_zeros`) pins both the
   MATCH-after-normalization behavior and redaction continuity in one place.

**Why introduced (composition).** First real baseline run showed composition
degrades to `None` on every bill — the parser already structurally degrades
the fiscal table to `None` when it's unreadable (TD-014), and Grupo B1
residential sizing doesn't use the TUSD/TE breakdown anyway. Composition
extraction is a Grupo A / tariff-swap concern. The eval was reporting a
non-real "failure" on every run; dropping it removes noise and keeps the
HR-5 guarantees on the fields that actually matter for v1 (distributor, UC,
period, consumption, total).

**Why introduced (UC normalization).** Same baseline run showed
`installation_number` MISREAD on bills where the parsed value and the labeled
value differ only in leading-zero padding (e.g. `0006354013` vs
`000006354013`). The underlying UC is identical; the zero-pad width is
template formatting. Exact string compare was over-strict.

**HR-4 (approved before implementation).**
`tests/evals/test_parser_reliability.py` edited:

- *Deleted* (covered behavior that no longer exists):
  `test_score_composition_present_vs_absent_matrix` (4 parametrized cases),
  `test_score_composition_label_none_with_bill_value_is_invention`,
  `test_load_labels_rejects_invalid_composition_literal`.
- *Updated* (composition key/kwarg cleanup, no assertion softened, no logic
  change): `test_load_labels_round_trips_two_fake_rows`,
  `test_load_labels_rejects_bad_period_format`,
  `test_load_labels_skips_comments_and_empty_lines`,
  `test_score_match_when_all_fields_equal`,
  `test_run_parser_reliability_with_mocked_parse_bill_image`,
  `test_run_parser_reliability_records_parse_failure`,
  `test_run_parser_reliability_infers_jpeg_media_type`.
- *Added*: `test_load_labels_ignores_legacy_composition_key`,
  `test_score_installation_number_normalizes_leading_zeros`.
- Helpers: `_make_composition` removed (unused), `_make_label` loses the
  `composition` kwarg, module docstring trimmed. `_make_bill` keeps its
  `composition` kwarg because the underlying `Bill` model still has the
  field (we did not change `models.py`).

**Resolution target.** Both changes already resolved on this branch.
Re-add composition scoring if a v2 feature uses the TUSD/TE breakdown
(Grupo A audit, Tarifa Branca simulation comparing fiscal blocks, etc.).
The UC normalization is permanent — it reflects how the data actually
renders on Brazilian bills.

---

## TD-015: current_bill stored as JSON-primitive dict + langgraph allowed_objects deprecation deferred

**What.** Two coupled changes on the `feature/hitl-bill-correction` branch:

1. **Production contract change.** `ChatState.current_bill` was retyped from
   `NotRequired[Bill | None]` to `NotRequired[dict[str, Any] | None]`. The
   `parse_bill` success path now writes `bill.model_dump(mode="json")` and
   `correct_bill_field` rehydrates via `Bill.model_validate(...)` and writes
   back `validated.model_dump(mode="json")`. The checkpoint never holds a
   domain object (no Bill, Decimal, or date instances crossing the
   serialization boundary). HR-5 surgical-update semantics are intact:
   `candidate = dict(current_bill); candidate[field] = new_value` followed by
   `Bill.model_validate(candidate)` proves the whole is well-formed before
   write-back. HR-2 / HR-6 lifecycle unchanged — dict still lives only in the
   in-process MemorySaver, never persisted, never logged.

2. **HR-4 test edits (approved before implementation).**
   - `tests/chat/test_bill_persistence.py` — two tests changed their type
     assertions from "Bill instance" to "dict that rehydrates to the same Bill
     via `Bill.model_validate`". The recoverable value is asserted, not the
     in-channel object type. No assertion was softened; no test was skipped
     or marked xfail; the contract is strictly stronger because it now
     verifies both shape AND content.
   - `tests/chat/tools/test_correct.py` — the `_make_state` helper now stores
     `current_bill.model_dump(mode="json")` so injected fixtures mirror the
     production contract. Each success-path assertion that previously did
     `isinstance(new_bill, Bill)` now rehydrates the dict via
     `Bill.model_validate(stored)` before asserting on typed values. The
     byte-identical guarantee in
     `test_correct_distributor_changes_only_that_field` is now a dict-on-dict
     comparison via `model_dump(mode="json")` on both sides — same invariant.

**Why introduced.** A Streamlit run printed:
`Deserializing unregistered type energia.models.Bill from checkpoint. This
will be blocked in a future version.` Storing a Bill instance in the
checkpoint relies on LangGraph's `JsonPlusSerializer` ext-type path for
arbitrary Pydantic v2 models, which the langchain-core deprecation flow has
warned will be locked down. Routing the value through `model_dump(mode="json")`
makes the checkpoint primitive-only and removes the dependency on
serializer-version internals.

**Related deferral — `allowed_objects` pending-deprecation.** Pytest also
emits a separate `LangChainPendingDeprecationWarning` from
`langgraph/checkpoint/serde/jsonplus.py:45` where `LC_REVIVER = Reviver()` is
called at module import time with no `allowed_objects` argument. langchain-core
1.3.3 warns and defaults to `"core"`. The correct narrower value for our
state would be `"messages"` (we only persist LangChain `BaseMessage`
subclasses + primitives). At langgraph 1.1.10, `MemorySaver` exposes no clean
way to pass a custom Reviver — `LC_REVIVER` is a module-level constant in
jsonplus.py, not parametrized through `JsonPlusSerializer.__init__`. Setting
it would require monkey-patching the module constant (fragile, version-pinned)
or filtering the warning category (cosmetic only). A pending-deprecation is
upstream's promise to warn before action; deferring is safe.

**Resolution target.** Code change already resolved on this branch. Revisit
the `allowed_objects` warning when langgraph exposes a public knob for the
serializer's reviver, or when langchain-core flips the default away from
`"core"` and breaks message round-trip. Both HR-4 entries are audit-trail
only — Daniel approved both edits before implementation; no further action.

---

## TD-014: test_models.py edited under quality/optional-bill-composition — HR-4 audit trail

**What.** A single line was added to
`tests/test_models.py::TestBill::test_bill_stores_amounts_as_decimal`:

```python
assert bill.composition is not None
```

inserted between the `bill.consumption_kwh` assertion and the
`bill.composition.other` assertions. The new line narrows `bill.composition`
from `BillComposition | None` (its model type as of this branch) back to
`BillComposition` so the subsequent assertions remain type-safe under
pyright. No existing assertion was modified, removed, or softened.

**Why introduced.** The branch `quality/optional-bill-composition` makes
`Bill.composition` optional (default `None`) so a bill with a legible header
and an unreadable fiscal table can still parse — Grupo B1 residential solar
sizing only needs header fields (consumption_kwh, total_brl, distributor,
period). The TUSD/TE/ICMS breakdown is a Grupo A concern and is the part
that intermittently breaks parses. The original test still constructs `Bill`
via `_valid_bill()` which embeds a `BillComposition`, so runtime behaviour
is unchanged; the added `assert ... is not None` is purely a static-type
narrow.

This is an HR-4 process record, not deferred work. Daniel explicitly
approved the edit before implementation. No skip/xfail/skipif marker was
added; only an additional positive assertion was inserted.

**Resolution target.** Already resolved — recorded here as the required
HR-4 audit trail entry.

---

## TD-013: test_graph.py edited under feature/conversation-memory — HR-4 audit trail

**What.** All four `GRAPH.invoke(...)` call sites in `tests/chat/test_graph.py`
gained a `config={"configurable": {"thread_id": "..."}}` keyword argument:

- `test_graph_runs_single_turn_with_no_tool_calls` → `thread_id="test-conv-single"`
- `test_graph_runs_tool_use_loop` → `thread_id="test-conv-tools"`
- `test_graph_accumulates_tokens_across_turns` → `thread_id="test-conv-tokens"`
- `test_graph_handles_tool_error_gracefully` → `thread_id="test-conv-err"`

No assertions were softened, no test logic was changed, no skips or xfails were
added. The edit is purely mechanical: `feature/conversation-memory` compiled the
chat graph with an in-process `MemorySaver` checkpointer (ADR-002 / PLAN:474),
which makes `configurable.thread_id` a required argument on every `invoke`.
Distinct thread_ids per test keep MemorySaver's per-thread state isolated so
the existing assertions continue to exercise the same per-turn behaviour they
always did.

**Why introduced.** This is an HR-4 process record, not deferred work. Daniel
explicitly approved the edit before implementation. No existing assertion was
weakened — only the now-mandatory config kwarg was added at each call site.

**Resolution target.** Already resolved — recorded here as the required HR-4
audit trail entry.

---

## TD-012: test_smoke.py edited under Task 1.3 Stage B — HR-4 audit trail

**What.** `tests/test_smoke.py::test_import_chat_tools` was modified. The
previous assertion `assert len(ALL_TOOLS) == 1` (a stale Sprint-0 invariant
that locked in the hello_world stub as the only registered tool) was replaced
with a membership-based assertion:

```python
names = {t.name for t in ALL_TOOLS}
assert "hello_world" in names
assert "parse_bill" in names
```

The new form is strictly stronger: it asserts the identity of the tools that
must be registered, not just the count, and it survives future tool additions
without needing another edit. Task 1.3 Stage B added the `parse_bill` tool
(InjectedState pattern, Option A), which would have broken the strict count.

**Why introduced.** This is an HR-4 process record, not deferred work. Daniel
explicitly approved the edit before implementation, with the explicit note that
a membership assertion is stronger than the count it replaces. No existing
assertion was weakened — the test now pins identity rather than cardinality.

**Resolution target.** Already resolved — recorded here as the required HR-4
audit trail entry.

---

## TD-011: test_streamlit_helpers.py edited under CC-02 follow-up — HR-4 audit trail

**What.** `tests/ui/test_streamlit_helpers.py` was modified: both existing tests
now consume the `tmp_db` fixture and pass `tmp_db["user_id"]` /
`tmp_db["conversation_id"]` / `db_path=tmp_db["db_path"]` to `handle_message`,
replacing the hardcoded `"user-id" / "conv-id"` placeholder strings. A new
regression-guard test, `test_settings_duckdb_path_must_be_redirected_under_pytest`,
was added in the same file to fail loudly if the redirect ever regresses. This
closes a data leak where the helper tests, by virtue of importing
`energia.ui.streamlit_app`, triggered the module-level `migrate()` call against
the production `data/energia.duckdb` — and in some runs caused
`_bootstrap_session()` to write a `users` row with a `MagicMock`-stringified
`session_id`.

`tests/ui/conftest.py` was also extended to mutate `settings.duckdb_path` to a
per-session temp file at module load, before the streamlit stub is registered,
so the module-level `migrate()` in `streamlit_app.py` lands in temp regardless
of the stub's effectiveness.

`src/energia/ui/streamlit_app.py` gained an optional `db_path: str | None = None`
parameter on `handle_message`, threaded into `DuckDBAuditCallback`. The
Streamlit event-loop call site at the bottom of the module is unchanged (gets
the `None` default and reads `settings.duckdb_path` via `connect()`).

**Why introduced.** This is an HR-4 process record, not deferred work. Daniel
explicitly approved the edit before implementation. No existing assertion was
weakened — only fixture wiring changed, explicit DB-path plumbing was added,
and a forward-looking regression guard was created.

**Resolution target.** Already resolved — recorded here as the required HR-4
audit trail entry.

---

## TD-010: test_budget.py edited under TE-02 — HR-4 audit trail

**What.** `tests/chat/test_budget.py` was extended with
`test_budget_callback_warns_at_80_percent`, covering the `if pct >= 0.8 and not
self._warned_80:` branch in `TokenBudgetCallback.on_llm_end`. The 80% threshold
is mandated by HR-7 and was the only warning branch without a test. The test also
asserts the `_warned_80` flag suppresses duplicate warnings.

**Why introduced.** This is an HR-4 process record, not deferred work. Daniel
explicitly approved the edit before implementation. No existing assertion was
weakened — only new coverage was added.

**Resolution target.** Already resolved — recorded here as the required HR-4
audit trail entry.

---

## TD-009: test_audit.py edited under TE-01 — HR-4 audit trail

**What.** `tests/chat/test_audit.py` was extended with two new test functions:
`test_audit_callback_silent_skip_on_tool_end_without_start` and
`test_audit_callback_silent_skip_on_tool_error_without_start`. They cover the
`if call_id is None: return` early-return branches in `on_tool_end` and
`on_tool_error` that were permanently dark paths in the prior suite.

**Why introduced.** This is an HR-4 process record, not deferred work. Daniel
explicitly approved the edit before implementation. No existing assertion was
weakened — only new coverage was added.

**Resolution target.** Already resolved — recorded here as the required HR-4
audit trail entry.

---

## TD-008: test_models.py edited under CC-03 — HR-4 audit trail

**What.** `tests/test_models.py` was modified: `needs_user_confirmation` removed from
the `_valid_bill()` builder dict, `TestParseResult` class added, and
`test_bill_no_longer_has_needs_user_confirmation` added to `TestBill`. This is part
of the CC-03 refactor that moves the workflow flag from `Bill` into a `ParseResult`
wrapper.

**Why introduced.** This is an HR-4 process record, not deferred work. Daniel
explicitly approved the edit before implementation. No assertion was weakened —
tests were added and a field removed that no longer belongs on `Bill`.

**Resolution target.** Already resolved — recorded here as the required HR-4 audit
trail entry.

---

## TD-006: Task 0.4 migration tests over-specified for migration count

**What.** `tests/db/test_migrations.py` had two assertions hardcoded for
exactly one applied migration (`assert count == 1`, `assert len(rows) == 1`).
When Task 1.1 added a second migration, both tests broke despite the
runner working correctly. Fixed in 2026-05-11 with name-based lookup and
file-count comparison.

**Why introduced.** The Task 0.4 tests were written when only one
migration existed and didn't anticipate the natural growth of the
migrations folder. The fixes generalise the assertions to "all migrations
applied, no duplicates" and "this specific migration name maps to its
file's SHA-256" — both preserve the test intent while supporting any
number of migrations.

**Resolution target.** Resolved by edits to `test_migrate_is_idempotent`
and `test_migrate_records_applied_migration` in this commit. HR-4 process
followed correctly — Claude Code flagged before editing, Daniel approved.

---

## TD-005: hello_no_name example removed from capability eval

**What.** The 4th example in `evals/capability/hello_world.jsonl`
(`hello_no_name`, input "Oi") was removed in 2026-05-11. It expected the
model to not call any tool when the user gives no name. The model
consistently calls `hello_world` with a placeholder name (e.g. "amigo"),
which is a defensible response to ambiguous input but fails the strict
`expected_tool: null` check.

**Why introduced.** The Task 0.6 example was overspecified. The original
prompt intended "no tool call OR clarifying question" as acceptable, but
the scorer infrastructure doesn't support either-or semantics in a single
example. Without an "any of the following tools" or "any of the following
patterns" expression, the example becomes a coin-flip on stub-tool
behavior.

**Resolution target.** Sprint 1+ — when real tools replace hello_world,
redesign eval examples to test what we actually care about (bill
extraction accuracy, tariff calculation correctness, solar payback math).
Add either-or semantics to the scorer if a real capability needs it.

## TD-004: tests/test_smoke.py edited in Task 0.5

**What.** The `ALL_TOOLS` length assertion in `tests/test_smoke.py` was bumped
from `== 0` to `== 1` to match the new `hello_world` stub tool added in Task 0.5.

**Why introduced.** The original test in Task 0.3 carried a forward-looking
comment "Sprint 0: stub tool added in Task 0.5", which Claude Code took as
authorization to edit. HR-4 process miss — Claude Code should have flagged
before editing and waited for explicit approval, as it did with D1–D5
during Task 0.2 (legacy cleanup). The edit itself is correct (assertion is
not weakened); the process bypass is the debt.

**Resolution target.** Process-only debt — calibrate future Claude Code
sessions to flag tests/** edits even when the scaffolding telegraphed them.
No code change required.

---

## TD-003: ruff N818 suppression for TokenBudgetExceeded

**What.** `ruff.toml` suppresses rule N818 (exception class names should end
in "Error") for the entire project.

**Why introduced.** The exception class `TokenBudgetExceeded` follows the
exact spec name in PLAN.md Task 0.5. Suppressing N818 was the path of least
resistance to make ruff green without renaming a spec-defined symbol.

**Resolution target.** Sprint 1 or later — narrow the suppression to just
this one class via `# noqa: N818` instead of suppressing project-wide.
Or: rename to `TokenBudgetExceededError` in a deliberate PLAN.md revision.

---

## TD-002: pyright suppressions for langgraph type stubs

**What.** `pyrightconfig.json` suppresses `reportMissingTypeStubs` and
`reportUnknownMemberType` for langgraph imports.

**Why introduced.** LangGraph 0.2+ does not yet ship type stubs. Without
suppression, every import of langgraph triggers pyright warnings that
drown out real issues.

**Resolution target.** Revisit when `langgraph-types` is published, when
langgraph itself ships `.pyi` files, or when we can write narrow per-import
stubs in a `typings/langgraph/` overlay. Track upstream.

---

## TD-001: ~158 MB NREL CSV files remain in git history

**What.** Three NREL grid-flexibility CSVs (~158 MB total) live in the
git history. Working tree files are deleted and gitignored as of the
legacy-cleanup commit. Adding the 64 MB Brazilian tariff CSV in
`data/aneel/historical_tariffs.csv` adds another ~64 MB on top.

**Why introduced.** `git filter-repo` rewrites history and requires
`git push --force` to origin — a destructive operation that needs
Daniel's explicit approval before execution. Q5 from MIGRATION.md
was resolved as "gitignore now, filter-repo as a separate task."

**Resolution target.** After Sprint 0 closes. Daniel runs
`git filter-repo` from a fresh clone (HR-1), force-pushes to origin,
and notifies any collaborators with stale clones.

---

## Resolved

### TD-007 — ruff E402/I001 suppression for load_dotenv files

**Resolved:** 2026-05-14 — branch `refactor/audit-phase-1`

`_llm`/`_llm_with_tools` made lazy in `nodes.py`; `GRAPH` made lazy in
`graph.py` via `__getattr__`. `load_dotenv()` moved below imports in both
entry-point files. Per-file-ignores removed from `ruff.toml`.