-- =============================================================================
-- JobRadar B2B — Weiterbildungsschule Extension
-- Migration: 002
-- Builds on top of schema v1.1 (companies / jobs / job_events).
-- All new tables are purely additive. Existing tables untouched.
--
-- Architecture: Collect once → Enrich once → Match many → Report many
--
-- Multi-tenant design:
--   - schools.tenant_id  maps each school to its own UUID namespace
--   - school-scoped tables carry school_id FK (not tenant_id directly)
--   - global tables (search_clusters, job_enrichments, llm_cache,
--     prompt_templates) have no tenant_id — shared across all clients
--   - RLS stubs included; enable when going live with first paying client
-- =============================================================================

-- ---------------------------------------------------------------------------
-- ENUMs (new)
-- ---------------------------------------------------------------------------

DO $$ BEGIN
  CREATE TYPE school_plan_enum AS ENUM (
    'pilot', 'starter', 'standard', 'pro', 'enterprise'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE report_status_enum AS ENUM (
    'draft', 'ready', 'sent', 'failed'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE match_status_enum AS ENUM (
    'pending', 'approved', 'rejected', 'sent'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE feedback_type_enum AS ENUM (
    'useful', 'not_relevant', 'too_senior', 'wrong_language',
    'wrong_location', 'duplicate', 'good_employer', 'bad_employer'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE report_recipient_role_enum AS ENUM (
    'coach', 'manager', 'admin'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------------------
-- schools
-- ---------------------------------------------------------------------------
-- One row per client school. tenant_id = their UUID namespace in the system.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS schools (
  id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID          NOT NULL UNIQUE,  -- their access scope UUID
  name           TEXT          NOT NULL,
  city           TEXT          NOT NULL DEFAULT 'Berlin',
  website        TEXT,
  contact_person TEXT,
  contact_email  TEXT,
  plan           school_plan_enum NOT NULL DEFAULT 'pilot',
  active         BOOLEAN       NOT NULL DEFAULT true,
  notes          TEXT,
  created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_schools_tenant_id ON schools (tenant_id);
CREATE INDEX IF NOT EXISTS idx_schools_active    ON schools (active) WHERE active = true;

COMMENT ON TABLE  schools            IS 'B2B client schools. tenant_id = their UUID namespace.';
COMMENT ON COLUMN schools.tenant_id  IS 'Maps to tenant_id in jobs/companies for RLS isolation.';
COMMENT ON COLUMN schools.plan       IS 'Billing plan: pilot → starter → standard → pro → enterprise.';

CREATE TRIGGER trg_schools_updated_at
  BEFORE UPDATE ON schools
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ---------------------------------------------------------------------------
-- courses
-- ---------------------------------------------------------------------------
-- One row per active course offering at a school.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS courses (
  id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id        UUID          NOT NULL REFERENCES schools (id) ON DELETE CASCADE,
  name             TEXT          NOT NULL,
  category         TEXT          NOT NULL,  -- data_analytics, webdev, it_support, office, cloud, etc.
  language_level   TEXT,                   -- B1, B2, C1 — target participant language level
  target_region    TEXT          NOT NULL DEFAULT 'Berlin',
  report_frequency TEXT          NOT NULL DEFAULT 'weekly',  -- weekly, biweekly, monthly
  active           BOOLEAN       NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_school_id ON courses (school_id);
CREATE INDEX IF NOT EXISTS idx_courses_active     ON courses (school_id, active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_courses_category   ON courses (category);

COMMENT ON TABLE  courses                  IS 'Course offerings per school. Unit of matching and reporting.';
COMMENT ON COLUMN courses.category         IS 'Shared category key — links to search_clusters.';
COMMENT ON COLUMN courses.language_level   IS 'Target participant German level for language filtering.';
COMMENT ON COLUMN courses.report_frequency IS 'How often Flow 12 generates reports for this course.';

CREATE TRIGGER trg_courses_updated_at
  BEFORE UPDATE ON courses
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ---------------------------------------------------------------------------
-- search_clusters
-- ---------------------------------------------------------------------------
-- GLOBAL shared job market segments. Not per school.
-- Multiple schools with similar courses share the same cluster.
-- This is the core "Collect once" optimization.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS search_clusters (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  name              TEXT          NOT NULL UNIQUE,  -- slug: data_analytics_entry_berlin
  display_name      TEXT          NOT NULL,
  category          TEXT          NOT NULL,
  region            TEXT          NOT NULL DEFAULT 'Berlin',
  description       TEXT,
  title_examples    TEXT[]        NOT NULL DEFAULT '{}',  -- representative job titles
  active            BOOLEAN       NOT NULL DEFAULT true,
  refresh_frequency TEXT          NOT NULL DEFAULT 'daily',
  last_refreshed_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_clusters_category ON search_clusters (category);
CREATE INDEX IF NOT EXISTS idx_search_clusters_active   ON search_clusters (active) WHERE active = true;

COMMENT ON TABLE  search_clusters                  IS 'Global shared job market segments. Not per school.';
COMMENT ON COLUMN search_clusters.name             IS 'Slug used in n8n and code to reference cluster.';
COMMENT ON COLUMN search_clusters.title_examples   IS 'Sample titles for QA and documentation.';
COMMENT ON COLUMN search_clusters.refresh_frequency IS 'daily | weekly — how often Flow 1 re-scrapes this cluster.';

-- ---------------------------------------------------------------------------
-- course_cluster_subscriptions
-- ---------------------------------------------------------------------------
-- Which clusters a course subscribes to. N:M.
-- Custom per-course keyword overrides possible here.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS course_cluster_subscriptions (
  id                      UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id               UUID       NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
  search_cluster_id       UUID       NOT NULL REFERENCES search_clusters (id) ON DELETE CASCADE,
  weight                  SMALLINT   NOT NULL DEFAULT 10 CHECK (weight BETWEEN 1 AND 10),
  custom_include_keywords TEXT[]     NOT NULL DEFAULT '{}',
  custom_exclude_keywords TEXT[]     NOT NULL DEFAULT '{}',
  active                  BOOLEAN    NOT NULL DEFAULT true,
  UNIQUE (course_id, search_cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_ccs_course_id   ON course_cluster_subscriptions (course_id);
CREATE INDEX IF NOT EXISTS idx_ccs_cluster_id  ON course_cluster_subscriptions (search_cluster_id);

COMMENT ON TABLE  course_cluster_subscriptions         IS 'N:M: course subscribes to shared search clusters.';
COMMENT ON COLUMN course_cluster_subscriptions.weight  IS '1-10: how important this cluster is for the course.';

-- ---------------------------------------------------------------------------
-- search_profiles
-- ---------------------------------------------------------------------------
-- Per-course matching rules. JSON-driven so n8n reads from DB, not hardcoded.
-- One course can have multiple profiles (e.g. one strict, one broad).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS search_profiles (
  id                    UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id             UUID       NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
  name                  TEXT       NOT NULL,                    -- e.g. "Strict Entry", "Broad"
  target_titles         JSONB      NOT NULL DEFAULT '[]',       -- ["Junior Data Analyst", "BI Assistant"]
  alternative_titles    JSONB      NOT NULL DEFAULT '[]',       -- broader title variants
  exclude_titles        JSONB      NOT NULL DEFAULT '[]',       -- ["Senior", "Lead", "Head of"]
  required_skills       JSONB      NOT NULL DEFAULT '[]',       -- ["Excel", "SQL", "Power BI"]
  nice_skills           JSONB      NOT NULL DEFAULT '[]',       -- ["Python", "Tableau"]
  exclude_requirements  JSONB      NOT NULL DEFAULT '[]',       -- ["5+ years", "Master's"]
  language_rules        JSONB      NOT NULL DEFAULT '{}',       -- {accept:[...], flag:[...], reject:[...]}
  location_rules        JSONB      NOT NULL DEFAULT '{}',       -- {accept:[...], reject:[...]}
  seniority_filter      TEXT[]     NOT NULL DEFAULT ARRAY['junior','intern'],
  report_settings       JSONB      NOT NULL DEFAULT '{}',       -- top_n, include_employer_targets, etc.
  active                BOOLEAN    NOT NULL DEFAULT true,
  version               SMALLINT   NOT NULL DEFAULT 1,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_profiles_course_id ON search_profiles (course_id);
CREATE INDEX IF NOT EXISTS idx_search_profiles_active    ON search_profiles (course_id, active) WHERE active = true;

COMMENT ON TABLE  search_profiles                    IS 'Per-course matching rules. n8n reads these — never hardcoded in nodes.';
COMMENT ON COLUMN search_profiles.target_titles      IS 'Primary job titles to match. JSON array of strings.';
COMMENT ON COLUMN search_profiles.language_rules     IS '{accept, flag, reject} arrays for German level requirements.';
COMMENT ON COLUMN search_profiles.seniority_filter   IS 'Only these seniority levels pass. Default: junior + intern.';
COMMENT ON COLUMN search_profiles.version            IS 'Incremented when profile is calibrated. Old matches stay linkable.';

CREATE TRIGGER trg_search_profiles_updated_at
  BEFORE UPDATE ON search_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ---------------------------------------------------------------------------
-- job_enrichments
-- ---------------------------------------------------------------------------
-- GLOBAL enrichment cache. One row per unique job (by input_hash).
-- LLM sees each unique job ONCE — results shared across all schools.
-- "Enrich once" layer.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS job_enrichments (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id                UUID          NOT NULL UNIQUE REFERENCES jobs (id) ON DELETE CASCADE,
  input_hash            TEXT          NOT NULL UNIQUE,  -- SHA256 of job text — cache key
  job_family            TEXT,                           -- data, webdev, it_support, office, cloud
  seniority             seniority_enum,
  required_skills       JSONB         NOT NULL DEFAULT '[]',
  nice_skills           JSONB         NOT NULL DEFAULT '[]',
  language_requirements JSONB         NOT NULL DEFAULT '{}',
  years_experience      SMALLINT,
  employment_type       TEXT,                           -- Vollzeit, Teilzeit, Befristet
  risk_flags            JSONB         NOT NULL DEFAULT '[]',  -- ["requires_5yr_exp", "C2_german"]
  summary_b2b           TEXT,                           -- neutral summary for coach reports (not personal)
  model_used            TEXT,
  enrichment_version    SMALLINT      NOT NULL DEFAULT 1,
  created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_enrichments_job_id     ON job_enrichments (job_id);
CREATE INDEX IF NOT EXISTS idx_job_enrichments_input_hash ON job_enrichments (input_hash);
CREATE INDEX IF NOT EXISTS idx_job_enrichments_job_family ON job_enrichments (job_family);
CREATE INDEX IF NOT EXISTS idx_job_enrichments_seniority  ON job_enrichments (seniority);

COMMENT ON TABLE  job_enrichments              IS 'Global LLM enrichment. Each job enriched once. Shared across all schools.';
COMMENT ON COLUMN job_enrichments.input_hash   IS 'SHA256(job_title||company||description). Cache key — skip if exists.';
COMMENT ON COLUMN job_enrichments.risk_flags   IS 'Array of machine-readable rejection reasons for filtering.';
COMMENT ON COLUMN job_enrichments.summary_b2b  IS 'Coach-facing summary. No personal context, no PII.';

-- ---------------------------------------------------------------------------
-- matching_queue
-- ---------------------------------------------------------------------------
-- Lightweight queue: new jobs waiting to be matched against all course profiles.
-- Flow 11 reads from here, processes, then deletes processed rows.
-- Avoids time-based filtering fragility.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS matching_queue (
  job_id    UUID        PRIMARY KEY REFERENCES jobs (id) ON DELETE CASCADE,
  added_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matching_queue_added_at ON matching_queue (added_at);

COMMENT ON TABLE  matching_queue         IS 'Queue of jobs awaiting course matching. Flow 11 drains this.';
COMMENT ON COLUMN matching_queue.job_id  IS 'Set by Flow 4/7 after DB write. Deleted by Flow 11 after match.';

-- ---------------------------------------------------------------------------
-- job_matches
-- ---------------------------------------------------------------------------
-- Per-course matching results. "Match many" layer.
-- One job can match multiple courses across multiple schools.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS job_matches (
  id                UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id            UUID           NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
  course_id         UUID           NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
  school_id         UUID           NOT NULL REFERENCES schools (id) ON DELETE CASCADE,
  search_profile_id UUID           REFERENCES search_profiles (id) ON DELETE SET NULL,
  fit_score         SMALLINT       CHECK (fit_score BETWEEN 0 AND 100),
  fit_reason        TEXT,
  matched_skills    JSONB          NOT NULL DEFAULT '[]',
  missing_skills    JSONB          NOT NULL DEFAULT '[]',
  risk_flags        JSONB          NOT NULL DEFAULT '[]',
  status            match_status_enum NOT NULL DEFAULT 'pending',
  reviewed          BOOLEAN        NOT NULL DEFAULT false,
  created_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  UNIQUE (job_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_job_matches_course_id      ON job_matches (course_id, status);
CREATE INDEX IF NOT EXISTS idx_job_matches_school_id      ON job_matches (school_id);
CREATE INDEX IF NOT EXISTS idx_job_matches_fit_score      ON job_matches (course_id, fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_job_matches_pending        ON job_matches (course_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_job_matches_created_at     ON job_matches (course_id, created_at DESC);

COMMENT ON TABLE  job_matches                  IS 'Course-specific job matches. One job × one course = one row.';
COMMENT ON COLUMN job_matches.fit_score        IS '0-100. Rule-based or LLM-assigned. Used to rank top recommendations.';
COMMENT ON COLUMN job_matches.status           IS 'pending → approved/rejected (QA) → sent (in report).';

-- ---------------------------------------------------------------------------
-- reports
-- ---------------------------------------------------------------------------
-- One row per generated weekly pack per school × course.
-- summary JSONB holds the funnel metrics shown in Rechercheumfang section.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reports (
  id           UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id    UUID               NOT NULL REFERENCES schools (id) ON DELETE CASCADE,
  course_id    UUID               NOT NULL REFERENCES courses (id) ON DELETE CASCADE,
  period_start DATE               NOT NULL,
  period_end   DATE               NOT NULL,
  report_type  TEXT               NOT NULL DEFAULT 'weekly',
  status       report_status_enum NOT NULL DEFAULT 'draft',
  file_url     TEXT,
  sheet_url    TEXT,
  sent_at      TIMESTAMPTZ,
  summary      JSONB              NOT NULL DEFAULT '{}',
  -- summary shape: {raw_jobs, deduped, senior_excluded, location_excluded,
  --                 language_excluded, curated, top_picks, employers_targeted,
  --                 skill_trends, coach_hours_saved_estimate}
  created_at   TIMESTAMPTZ        NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_school_course   ON reports (school_id, course_id);
CREATE INDEX IF NOT EXISTS idx_reports_period          ON reports (school_id, period_start DESC);
CREATE INDEX IF NOT EXISTS idx_reports_status          ON reports (status) WHERE status IN ('draft', 'ready');

COMMENT ON TABLE  reports          IS 'Generated weekly packs per school × course. Flow 12 writes here.';
COMMENT ON COLUMN reports.summary  IS 'Funnel metrics for Rechercheumfang section in coach report.';

-- ---------------------------------------------------------------------------
-- report_recipients
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS report_recipients (
  id        UUID                      PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID                      NOT NULL REFERENCES schools (id) ON DELETE CASCADE,
  course_id UUID                      REFERENCES courses (id) ON DELETE CASCADE,  -- NULL = all courses
  email     TEXT                      NOT NULL,
  role      report_recipient_role_enum NOT NULL DEFAULT 'coach',
  active    BOOLEAN                   NOT NULL DEFAULT true,
  UNIQUE (school_id, course_id, email)
);

CREATE INDEX IF NOT EXISTS idx_report_recipients_school ON report_recipients (school_id, active);

COMMENT ON COLUMN report_recipients.course_id IS 'NULL = receives reports for all courses of this school.';

-- ---------------------------------------------------------------------------
-- feedback
-- ---------------------------------------------------------------------------
-- Coach/manager feedback on individual job matches.
-- Used to calibrate search profiles and build blacklists.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS feedback (
  id            UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
  job_match_id  UUID               REFERENCES job_matches (id) ON DELETE SET NULL,
  school_id     UUID               NOT NULL REFERENCES schools (id) ON DELETE CASCADE,
  course_id     UUID               REFERENCES courses (id) ON DELETE SET NULL,
  feedback_type feedback_type_enum NOT NULL,
  comment       TEXT,
  created_at    TIMESTAMPTZ        NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_school_id    ON feedback (school_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_job_match_id ON feedback (job_match_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type         ON feedback (school_id, feedback_type);

COMMENT ON TABLE  feedback              IS 'Coach/manager feedback on matches. Drives profile calibration.';
COMMENT ON COLUMN feedback.feedback_type IS 'too_senior / wrong_language / good_employer etc.';

-- ---------------------------------------------------------------------------
-- llm_cache
-- ---------------------------------------------------------------------------
-- GLOBAL cache for LLM calls. Keyed by input_hash.
-- Shared across all schools — same prompt + same input = same response.
-- Never store PII here.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS llm_cache (
  id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  cache_key    TEXT          NOT NULL UNIQUE,    -- task_type + ':' + input_hash
  task_type    TEXT          NOT NULL,            -- job_enrichment, match_explain, report_summary
  model        TEXT          NOT NULL,
  input_hash   TEXT          NOT NULL,
  output_json  JSONB         NOT NULL,
  tokens_in    INT,
  tokens_out   INT,
  cost_eur     NUMERIC(10,6),
  created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  expires_at   TIMESTAMPTZ                        -- NULL = never expires
);

CREATE INDEX IF NOT EXISTS idx_llm_cache_key        ON llm_cache (cache_key);
CREATE INDEX IF NOT EXISTS idx_llm_cache_task_type  ON llm_cache (task_type);
CREATE INDEX IF NOT EXISTS idx_llm_cache_expires_at ON llm_cache (expires_at) WHERE expires_at IS NOT NULL;

COMMENT ON TABLE  llm_cache              IS 'Global LLM response cache. Same input → reuse output. No PII.';
COMMENT ON COLUMN llm_cache.cache_key    IS 'task_type:input_hash — checked before any LLM call.';
COMMENT ON COLUMN llm_cache.cost_eur     IS 'Tracked per call for cost monitoring per client.';

-- ---------------------------------------------------------------------------
-- prompt_templates
-- ---------------------------------------------------------------------------
-- Versioned prompts stored in DB. n8n reads task_type + latest active version.
-- No prompt changes require n8n redeployment.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS prompt_templates (
  id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type  TEXT          NOT NULL,
  version    SMALLINT      NOT NULL DEFAULT 1,
  template   TEXT          NOT NULL,
  notes      TEXT,
  active     BOOLEAN       NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  UNIQUE (task_type, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_task ON prompt_templates (task_type, active) WHERE active = true;

COMMENT ON TABLE  prompt_templates           IS 'Versioned LLM prompts. n8n reads latest active version per task_type.';
COMMENT ON COLUMN prompt_templates.task_type IS 'job_enrichment | match_scoring | report_summary | coach_notes';

-- ---------------------------------------------------------------------------
-- Reporting view: funnel overview per school × course × week
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_report_funnel AS
SELECT
  s.name                                        AS school,
  c.name                                        AS course,
  r.period_start,
  r.period_end,
  r.status,
  (r.summary->>'raw_jobs')::int                 AS raw_jobs,
  (r.summary->>'deduped')::int                  AS deduped,
  (r.summary->>'senior_excluded')::int          AS senior_excluded,
  (r.summary->>'language_excluded')::int        AS language_excluded,
  (r.summary->>'location_excluded')::int        AS location_excluded,
  (r.summary->>'curated')::int                  AS curated,
  (r.summary->>'top_picks')::int                AS top_picks,
  r.sheet_url,
  r.sent_at
FROM reports r
JOIN schools s ON s.id = r.school_id
JOIN courses c ON c.id = r.course_id
ORDER BY r.period_start DESC;

COMMENT ON VIEW v_report_funnel IS 'Weekly funnel metrics per school × course. Use for QA and billing.';

-- ---------------------------------------------------------------------------
-- Reporting view: top matches ready for next report
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW v_pending_matches AS
SELECT
  s.name         AS school,
  c.name         AS course,
  sp.name        AS profile,
  j.job_title,
  comp.name      AS company,
  j.location,
  j.work_mode,
  je.seniority,
  jm.fit_score,
  jm.fit_reason,
  jm.matched_skills,
  jm.risk_flags,
  j.source_url,
  jm.created_at
FROM job_matches jm
JOIN jobs          j    ON j.id    = jm.job_id
JOIN companies     comp ON comp.company_id = j.company_id AND comp.tenant_id = j.tenant_id
JOIN courses       c    ON c.id    = jm.course_id
JOIN schools       s    ON s.id    = jm.school_id
LEFT JOIN job_enrichments je ON je.job_id = jm.job_id
LEFT JOIN search_profiles sp ON sp.id     = jm.search_profile_id
WHERE jm.status = 'pending'
ORDER BY s.name, c.name, jm.fit_score DESC NULLS LAST;

COMMENT ON VIEW v_pending_matches IS 'All approved/pending matches ready for next report cycle.';

-- ---------------------------------------------------------------------------
-- RLS — school isolation stubs
-- ---------------------------------------------------------------------------
-- Enable when first paying B2B client is onboarded.
-- App must: SET LOCAL app.current_school_id = '<school_uuid>' per session.
-- ---------------------------------------------------------------------------

ALTER TABLE courses                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_cluster_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_profiles              ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_matches                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_recipients            ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback                     ENABLE ROW LEVEL SECURITY;

-- Permissive policies (single-operator mode — all rows visible)
-- Replace with restrictive policy when isolating clients:
--   DROP POLICY allow_all_courses ON courses;
--   CREATE POLICY school_isolation ON courses
--     USING (school_id = current_setting('app.current_school_id')::uuid);

CREATE POLICY allow_all_courses     ON courses                      FOR ALL USING (true);
CREATE POLICY allow_all_ccs         ON course_cluster_subscriptions FOR ALL USING (true);
CREATE POLICY allow_all_profiles    ON search_profiles              FOR ALL USING (true);
CREATE POLICY allow_all_matches     ON job_matches                  FOR ALL USING (true);
CREATE POLICY allow_all_reports     ON reports                      FOR ALL USING (true);
CREATE POLICY allow_all_recipients  ON report_recipients            FOR ALL USING (true);
CREATE POLICY allow_all_feedback    ON feedback                     FOR ALL USING (true);

-- ---------------------------------------------------------------------------
-- Grants — extend existing roles to new tables
-- ---------------------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE ON
  schools, courses, search_clusters, course_cluster_subscriptions,
  search_profiles, job_enrichments, matching_queue,
  job_matches, reports, report_recipients, feedback,
  llm_cache, prompt_templates
TO jobradar_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO jobradar_app;

GRANT SELECT ON
  schools, courses, search_clusters, course_cluster_subscriptions,
  search_profiles, job_enrichments, matching_queue,
  job_matches, reports, report_recipients, feedback,
  llm_cache, prompt_templates,
  v_report_funnel, v_pending_matches
TO jobradar_readonly;

-- ---------------------------------------------------------------------------
-- Seed: search clusters (Starter pack — Berlin, entry-level)
-- ---------------------------------------------------------------------------

INSERT INTO search_clusters (name, display_name, category, region, description, title_examples, refresh_frequency)
VALUES
  (
    'data_analytics_entry_berlin',
    'Data Analytics / BI — Entry Level Berlin',
    'data_analytics',
    'Berlin',
    'Junior data analyst, BI and reporting roles. Entry level. No senior/lead.',
    ARRAY['Junior Data Analyst','Reporting Analyst','BI Assistant','Power BI Analyst',
          'CRM Data Assistant','Operations Analyst','Marketing Data Analyst','Excel Specialist'],
    'daily'
  ),
  (
    'webdev_entry_berlin',
    'Web Development — Entry Level Berlin',
    'webdev',
    'Berlin',
    'Junior frontend, fullstack and web content roles. Entry level.',
    ARRAY['Junior Web Developer','Frontend Developer Junior','React Developer Junior',
          'WordPress Developer','CMS Manager','Web Content Specialist','Low-Code Developer',
          'QA Tester Junior','E-Commerce Technical Assistant'],
    'daily'
  ),
  (
    'it_support_entry_berlin',
    'IT Support / Cloud Support — Entry Level Berlin',
    'it_support',
    'Berlin',
    '1st level support, helpdesk, junior sysadmin, cloud support roles.',
    ARRAY['IT Support Specialist','1st Level Support','Helpdesk','Service Desk',
          'Junior System Administrator','Azure Support','Cloud Support Junior',
          'Technical Support','IT Operations Junior'],
    'daily'
  ),
  (
    'office_admin_entry_berlin',
    'Office / Kaufmännisch — Entry Level Berlin',
    'office_admin',
    'Berlin',
    'Office assistant, Sachbearbeiter, administrative and backoffice roles.',
    ARRAY['Büroassistenz','Sachbearbeiter','Kaufmännische Assistenz','Backoffice',
          'Office Assistant','HR Assistant Junior','Customer Operations','Projektassistenz',
          'Teamassistenz','Verwaltungsassistenz'],
    'daily'
  ),
  (
    'digital_marketing_entry_berlin',
    'Digital Marketing — Entry Level Berlin',
    'digital_marketing',
    'Berlin',
    'Social media, content, SEO and online marketing junior roles.',
    ARRAY['Junior Online Marketing Manager','Social Media Manager Junior',
          'Content Creator','SEO Specialist Junior','Performance Marketing Assistant',
          'E-Commerce Marketing Assistant','Community Manager'],
    'weekly'
  ),
  (
    'cloud_devops_entry_germany',
    'Cloud / DevOps — Entry Level Germany (Remote)',
    'cloud_devops',
    'Germany',
    'Cloud support, junior DevOps, Azure/AWS assistant roles. Remote/hybrid.',
    ARRAY['Junior Cloud Engineer','Azure Administrator Associate','AWS Support Junior',
          'DevOps Engineer Junior','Infrastructure Support','Cloud Operations Junior',
          'Site Reliability Engineer Junior'],
    'weekly'
  )
ON CONFLICT (name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Seed: prompt templates
-- ---------------------------------------------------------------------------

INSERT INTO prompt_templates (task_type, version, template, notes)
VALUES
  (
    'job_enrichment',
    1,
    'Analyse this job posting and extract structured information.
Return ONLY valid JSON with these fields:
{
  "job_family": "data_analytics|webdev|it_support|office_admin|digital_marketing|cloud_devops|other",
  "seniority": "intern|junior|middle|senior|lead|principal|staff|director",
  "required_skills": ["skill1", "skill2"],
  "nice_skills": ["skill1"],
  "language_requirements": {"german": "B2", "english": "B1"},
  "years_experience": null,
  "employment_type": "Vollzeit|Teilzeit|Befristet|Freelance",
  "risk_flags": ["requires_5yr_exp", "c2_german", "relocation", "unpaid_trial"],
  "summary_b2b": "One sentence neutral summary for career coaches."
}
Job posting:
{{job_text}}',
    'v1: initial enrichment. Shared across all schools.'
  ),
  (
    'match_scoring',
    1,
    'You are evaluating whether a job matches a course profile for career coaching purposes.

Course profile:
{{search_profile_json}}

Job enrichment:
{{job_enrichment_json}}

Score this match 0-100 and explain briefly.
Return ONLY valid JSON:
{
  "fit_score": 75,
  "fit_reason": "Matches required SQL + Excel skills. German B2 required — within course level.",
  "matched_skills": ["SQL", "Excel"],
  "missing_skills": ["Power BI"],
  "risk_flags": ["german_b2_required"]
}',
    'v1: LLM match scoring. Used only for top candidates after rule pre-filter.'
  ),
  (
    'report_summary',
    1,
    'Write a weekly market summary for a career coach at a Weiterbildung school.
Tone: professional, neutral, helpful. No hype. In German.

Course: {{course_name}}
Top jobs this week: {{top_jobs_json}}
Skill trends: {{skill_trends_json}}
Funnel metrics: {{funnel_metrics_json}}

Write 3-4 sentences summarising the market this week. Include 1-2 actionable coach tips.',
    'v1: weekly coach summary. Per-report, not per-job.'
  )
ON CONFLICT (task_type, version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Schema version
-- ---------------------------------------------------------------------------

INSERT INTO schema_versions (version, description)
VALUES ('2.0', 'B2B Weiterbildung extension: schools, courses, search_clusters, search_profiles, job_enrichments, job_matches, reports, feedback, llm_cache, prompt_templates, matching_queue')
ON CONFLICT (version) DO NOTHING;
