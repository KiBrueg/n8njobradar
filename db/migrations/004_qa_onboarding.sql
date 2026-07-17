-- Migration 004: QA workflow columns + school onboarding intake + source learning views
-- Source: HERMES specs (QA View Spec, School Onboarding Form) + StepStone takeaway
--   (reject reasons must feed query/source performance).
-- Safe to re-run (IF NOT EXISTS guards). Date: 2026-07-17.

-- ── 1. Onboarding form intake (staging before schools/courses creation) ─────
CREATE TABLE IF NOT EXISTS course_onboarding_submissions (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  school_name   TEXT        NOT NULL,
  contact_email TEXT,
  course_name   TEXT        NOT NULL,
  payload       JSONB       NOT NULL DEFAULT '{}',  -- full raw form: roles, skills, region, exclusions...
  status        TEXT        NOT NULL DEFAULT 'new'
                CHECK (status IN ('new', 'reviewed', 'approved', 'rejected')),
  review_notes  TEXT,
  school_id     UUID        REFERENCES schools (id) ON DELETE SET NULL,  -- set after approval
  course_id     UUID        REFERENCES courses (id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_onboarding_status ON course_onboarding_submissions (status)
  WHERE status = 'new';
COMMENT ON TABLE course_onboarding_submissions IS
  'Form intake staging. Webhook writes here; human approves before schools/courses rows are created.';

-- ── 2. QA columns on job_matches (QA View Spec section 3) ───────────────────
ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS reject_reason  TEXT
  CHECK (reject_reason IS NULL OR reject_reason IN (
    'too_senior', 'wrong_language', 'wrong_location', 'not_entry_level',
    'pure_sales', 'support_heavy', 'fake_or_low_quality', 'duplicate',
    'already_seen', 'salary_too_low', 'requires_degree',
    'requires_car_or_travel', 'requires_c1_german', 'requires_3_years_experience'));
ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS coach_note      TEXT;
ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS student_action  TEXT;
ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS report_priority TEXT
  CHECK (report_priority IS NULL OR report_priority IN ('top5', 'normal', 'backup'));
ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS source_checked  BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN job_matches.reject_reason   IS 'QA reject taxonomy — feeds v_source_performance learning loop.';
COMMENT ON COLUMN job_matches.report_priority IS 'top5 / normal / backup — report generator ordering.';

-- ── 3. Learning loop: source & reject analytics (StepStone takeaway) ────────
CREATE OR REPLACE VIEW v_source_performance AS
SELECT
  j.source_input,
  COALESCE(SUBSTRING(j.source_url FROM 'https?://(?:www\.)?([^/]+)'), 'unknown') AS source_domain,
  COUNT(*)                                            AS matches_total,
  COUNT(*) FILTER (WHERE m.status = 'approved')       AS approved,
  COUNT(*) FILTER (WHERE m.status = 'rejected')       AS rejected,
  ROUND(100.0 * COUNT(*) FILTER (WHERE m.status = 'approved') / NULLIF(COUNT(*), 0)) AS approval_pct,
  MODE() WITHIN GROUP (ORDER BY m.reject_reason)      AS top_reject_reason
FROM job_matches m
JOIN jobs j ON j.id = m.job_id
GROUP BY j.source_input, source_domain;

COMMENT ON VIEW v_source_performance IS
  'Which sources produce approvable matches. Low approval_pct => fix query or drop source.';

CREATE OR REPLACE VIEW v_reject_reasons AS
SELECT
  m.course_id,
  c.name AS course_name,
  m.reject_reason,
  COUNT(*) AS cnt
FROM job_matches m
JOIN courses c ON c.id = m.course_id
WHERE m.reject_reason IS NOT NULL
GROUP BY m.course_id, c.name, m.reject_reason
ORDER BY cnt DESC;

COMMENT ON VIEW v_reject_reasons IS
  'Reject taxonomy per course — tells which filter rule to tighten in search_profiles.';
