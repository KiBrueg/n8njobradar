-- =============================================================================
-- Migration 002: Add sender_risk_level and sender_risk_signals to job_events
-- Reason: Sender Risk Check node computes these values but they were not
--         persisted to DB. Added for filtering, alerting, and audit.
-- Date: 2026-06-09
-- Safe to run on empty or existing DB (IF NOT EXISTS / IF NOT EXISTS guards).
-- =============================================================================

ALTER TABLE job_events
  ADD COLUMN IF NOT EXISTS sender_risk_level   TEXT,
  ADD COLUMN IF NOT EXISTS sender_risk_signals TEXT[] NOT NULL DEFAULT '{}';

-- Index for fast filtering (e.g. "show all high-risk senders")
CREATE INDEX IF NOT EXISTS idx_job_events_sender_risk_level
  ON job_events (sender_risk_level)
  WHERE sender_risk_level IS NOT NULL;

INSERT INTO schema_versions (version, description)
VALUES ('1.2', 'Add sender_risk_level, sender_risk_signals to job_events')
ON CONFLICT (version) DO NOTHING;
