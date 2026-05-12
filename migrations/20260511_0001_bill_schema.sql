-- Migration: 20260511_0001_bill_schema
-- Extends bills table with Sprint 1 columns: bill detail, composition, extraction metadata.
-- HR-3: this file is immutable once applied. New changes require a new timestamped migration.
--
-- NOTE: DuckDB ALTER TABLE ADD COLUMN does not support column constraints (NOT NULL).
-- DEFAULT values backfill existing rows. NOT NULL semantics are enforced at the
-- application layer via Pydantic models (Bill, BillComposition in models.py).

ALTER TABLE bills ADD COLUMN IF NOT EXISTS installation_number       TEXT;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS issue_date                DATE;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS due_date                  DATE;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS tariff_group              TEXT;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS modalidade                TEXT;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS composition_json          JSON    DEFAULT '{}';
ALTER TABLE bills ADD COLUMN IF NOT EXISTS confidence                DOUBLE  DEFAULT 1.0;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS needs_user_confirmation   BOOLEAN DEFAULT FALSE;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS confirmed_at              TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_bills_distributor_period ON bills(distributor, period);
