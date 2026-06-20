"""bill_store — persistence + hash-cache for parsed bills.

Mirrors the chat/memory.py persistence pattern: each function takes an
optional ``db_path`` and runs inside ``connection()`` from ``energia.db``.

HR-3: writes against the existing schema (migrations
``20260510_0001_initial_schema.sql`` + ``20260511_0001_bill_schema.sql``).
No new migration this task — every Bill field already has a column.

HR-6 posture (Branch A, ADR-003):
- ``data/energia.duckdb`` is gitignored — the local file is the LGPD trust
  boundary. ``installation_number`` is stored plaintext per the existing
  schema. ``raw_extraction`` JSON embeds the full Bill including UC.
- Image bytes are NEVER written. The cache key is ``sha256(image_bytes)``
  stored only as a hex digest in the ``bill_hash`` column.
- This module's logger emits PII-free messages only — hash, row count, generic
  status. Never bill fields, never the UC, never the user_id payload.

HR-5: ``find_by_hash`` rehydrates a Bill via ``Bill.model_validate`` so the
returned object is structurally identical to one a fresh parse would produce.
No partial / re-emitted state.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from energia.db import connection
from energia.models import Bill

logger = logging.getLogger(__name__)


def find_by_hash(
    user_id: str,
    bill_hash: str,
    db_path: str | None = None,
) -> Bill | None:
    """Return the cached Bill for (user_id, bill_hash), or None on miss.

    The WHERE filter is per-user even though ``bill_hash`` is globally UNIQUE
    at the column level — the per-user contract is what callers depend on,
    and global uniqueness is an implementation detail of the v1 single-user
    schema.
    """
    with connection(db_path) as con:
        row = con.execute(
            "SELECT raw_extraction FROM bills "
            "WHERE user_id = ? AND bill_hash = ?",
            [user_id, bill_hash],
        ).fetchone()
        if row is None:
            return None
        raw: Any = row[0]
        # DuckDB returns JSON columns as the decoded Python object (dict/list)
        # in 1.x. Guard the str case in case the driver ever returns the raw
        # text — Bill.model_validate handles dicts only, so we json.loads first.
        if isinstance(raw, str):
            raw = json.loads(raw)
        return Bill.model_validate(raw)


def insert(
    user_id: str,
    bill: Bill,
    bill_hash: str,
    db_path: str | None = None,
) -> str:
    """Insert a bill row and return its UUID.

    Idempotency contract (PLAN.md line 663): on duplicate ``bill_hash`` the
    INSERT is a no-op and the function returns the existing row's id via a
    follow-up SELECT. Callers can treat the call as "ensure this hash has a
    row, return its id" rather than "create".

    Writes:
    - top-level filterable columns (period, distributor, installation_number,
      consumption_kwh, total_brl, ...) for indexed lookups;
    - ``raw_extraction`` JSON as the canonical rehydration payload via
      ``bill.model_dump(mode="json")`` (TD-015 — JSON-primitive only across
      the serialization boundary);
    - ``composition_json`` separately as the per-row composition view (PLAN
      schema note #6);
    - ``needs_user_confirmation`` re-derived from ``confidence < 0.85`` to
      match the parser's contract (TD-008 / Task 1.3).
    """
    bill_dump: dict[str, Any] = bill.model_dump(mode="json")
    composition_dump: dict[str, Any] = bill_dump.get("composition") or {}
    needs_confirmation = bill.confidence < 0.85

    with connection(db_path) as con:
        existing = con.execute(
            "SELECT id FROM bills WHERE bill_hash = ?", [bill_hash]
        ).fetchone()
        if existing is not None:
            return str(existing[0])

        new_row = con.execute(
            """
            INSERT INTO bills (
                user_id, bill_hash, period, distributor,
                installation_number, issue_date, due_date,
                consumption_kwh, tariff_group, modalidade,
                bandeira, total_brl, composition_json, confidence,
                needs_user_confirmation, raw_extraction
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (bill_hash) DO NOTHING
            RETURNING id
            """,
            [
                user_id,
                bill_hash,
                bill.period,
                bill.distributor,
                bill.installation_number,
                bill.issue_date,
                bill.due_date,
                bill.consumption_kwh,
                bill.tariff_group,
                bill.modalidade,
                bill.bandeira,
                bill.total_brl,
                json.dumps(composition_dump),
                bill.confidence,
                needs_confirmation,
                json.dumps(bill_dump),
            ],
        ).fetchone()

        if new_row is None:
            # Lost race: another transaction inserted the same hash between our
            # SELECT and INSERT. Resolve via a follow-up SELECT — no PII logged.
            recovered = con.execute(
                "SELECT id FROM bills WHERE bill_hash = ?", [bill_hash]
            ).fetchone()
            if recovered is None:
                raise RuntimeError(
                    f"insert produced no row and follow-up SELECT failed "
                    f"for bill_hash prefix={bill_hash[:8]}…"
                )
            return str(recovered[0])
        return str(new_row[0])
