# Parser-reliability eval

Measures how accurately `parse_bill_image` reads real bills by comparing its
structured `Bill` output against hand-written ground-truth labels.

## Why hand-written labels

Auto-labeling with an LLM would grade Claude-vision against itself — a useless
metric. The labels in this eval are written by Daniel from real bills (or any
human reviewer), and the harness only compares: it never invents, back-fills,
or guesses a value (HR-5).

## How to run

```
uv run python -m energia.evals.run parser <labels_path> <bills_dir>
```

Console output prints, per bill, each scored field's verdict
(`MATCH` / `MISS` / `MISREAD` / `INVENTION`) plus an aggregate count. The
`installation_number` line shows only the verdict — its value is redacted
(HR-6 / LGPD).

Exit codes: `0` if the eval ran end-to-end, `2` if the labels file is empty or
missing. The harness does not gate by score yet — read the aggregate counts and
decide.

## Verdicts

| Verdict     | Meaning                                                                      |
|-------------|------------------------------------------------------------------------------|
| `MATCH`     | Label and parsed value are both present and equal. Numeric fields compare as `Decimal` (`"374" == "374.00"`). `installation_number` strips leading zeros on both sides (`"0006354013" == "000006354013"`). |
| `MISS`      | Label has a value, parser returned nothing for that field (or the whole parse failed). |
| `MISREAD`   | Label has a value, parser produced a different value.                        |
| `INVENTION` | Label is `null` (not legibly on the bill), parser produced a value anyway. **HR-5 violation flag.** |

## Label schema

JSONL — one bill per line:

```json
{
  "image": "<filename relative to bills_dir>",
  "distributor": "<name or null>",
  "installation_number": "<UC or null>",
  "period": "<YYYY-MM or null>",
  "consumption_kwh": "<numeric string or null>",
  "total_brl": "<numeric string or null>"
}
```

A `null` field means "this value is not legibly on the bill" — not "I didn't
bother to label it". Treat the two cases as different and don't conflate them.
Numeric fields are strings here so the loader's validator can reject typos
before the eval runs; the harness compares them as `Decimal` so `"374"` and
`"374.00"` are MATCH.

> **Old labels with a `"composition"` key still load.** The composition field
> was removed in TD-016 (residential / Grupo B doesn't use the TUSD/TE
> breakdown). The loader uses Pydantic v2's default `extra="ignore"` so legacy
> keys are silently dropped — no need to re-edit your `labels.jsonl`.

## Files in this directory

- `labels.example.jsonl` — FAKE example data, committed, schema documentation only.
  Distributors like `Fakedist`, UCs like `000000`, periods like `1999-01` —
  obviously not real.
- `labels.jsonl` (or any other `.jsonl`) — your real labels. **Gitignored.**

## HR-6 — what stays local

Brazilian bills carry PII. Specifically:

- Real `labels.jsonl` (any filename ending in `.jsonl` other than
  `labels.example.jsonl`) is gitignored by directory rule:
  `evals/parser_reliability/*.jsonl` ignored, `labels.example.jsonl`
  re-included. Renaming to `daniels-real-bills.jsonl` will NOT bypass the
  ignore.
- Real bill images live in `tests/fixtures/bills/` which is gitignored as a
  whole directory.
- The harness redacts `installation_number` in both the in-memory record and
  the console output. CPF is not a `Bill` field and never enters the eval.

If you find yourself tempted to commit a real label or bill, stop. Use
`git diff --cached` before every commit on this branch.
