-- Migration: 20260510_0001_initial_schema
-- Foundational tables for users, conversations, message log, tool call audit, bills skeleton.
-- HR-3: this file is immutable once applied.

CREATE TABLE IF NOT EXISTS users (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  session_id      TEXT         NOT NULL UNIQUE,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  display_name    TEXT,
  -- LGPD: no PII at user level in v1; bill-level PII handled in Sprint 1
);

CREATE TABLE IF NOT EXISTS conversations (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  user_id         UUID         NOT NULL REFERENCES users(id),
  started_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
  ended_at        TIMESTAMPTZ,
  total_tokens_in  INTEGER     NOT NULL DEFAULT 0,
  total_tokens_out INTEGER     NOT NULL DEFAULT 0,
);

CREATE TABLE IF NOT EXISTS messages (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  conversation_id UUID         NOT NULL REFERENCES conversations(id),
  role            TEXT         NOT NULL CHECK (role IN ('user', 'assistant')),
  content         TEXT         NOT NULL,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  message_id      UUID         NOT NULL REFERENCES messages(id),
  tool_name       TEXT         NOT NULL,
  input_json      TEXT         NOT NULL,
  output_json     TEXT,
  error           TEXT,
  duration_ms     INTEGER,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
);

CREATE TABLE IF NOT EXISTS bills (
  id              UUID         PRIMARY KEY DEFAULT uuid(),
  user_id         UUID         NOT NULL REFERENCES users(id),
  bill_hash       TEXT         NOT NULL UNIQUE,
  period          TEXT         NOT NULL,    -- YYYY-MM
  distributor     TEXT         NOT NULL,
  consumption_kwh NUMERIC(10,2) NOT NULL,
  total_brl       NUMERIC(10,2) NOT NULL,
  bandeira        TEXT,
  raw_extraction  JSON         NOT NULL,    -- full Bill model as JSON, expanded in Sprint 1
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_message ON tool_calls(message_id);
CREATE INDEX IF NOT EXISTS idx_bills_user_period ON bills(user_id, period);
