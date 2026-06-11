-- =============================================================================
-- Migration 001: Add platform_notification and application_failed enum values
-- Applied to: job_category_enum, job_stage_enum
-- Reason: BUG-09 fix — handle job portal auto-confirmations (Stepstone etc.)
-- Date: 2026-06-08
-- Safe to run on empty DB or on existing DB (IF NOT EXISTS guard).
-- =============================================================================

ALTER TYPE job_category_enum ADD VALUE IF NOT EXISTS 'platform_notification';
ALTER TYPE job_stage_enum    ADD VALUE IF NOT EXISTS 'application_failed';
