-- ---------------------------------------------------------------------------
-- Migration 003 — per-school notification config (SIGNL4, Telegram, thresholds)
-- ---------------------------------------------------------------------------
-- Adds notification_config JSONB to schools so each B2B client can have their
-- own alerting channels without schema changes.
--
-- Schema:
-- {
--   "signl4_webhook": "https://connect.signl4.com/webhook/TEAM_SECRET",
--   "telegram_chat_id": "-100...",
--   "fit_score_threshold": 75,   -- alert only above this score
--   "alert_on_match": true,       -- instant alert on high-score match
--   "weekly_report_email": true,  -- HTML report on Sunday
--   "report_recipients": ["coach@school.de"]
-- }
-- ---------------------------------------------------------------------------

ALTER TABLE schools
  ADD COLUMN IF NOT EXISTS notification_config JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN schools.notification_config IS
  'Per-client notification settings: signl4_webhook, telegram_chat_id, fit_score_threshold, alert_on_match, weekly_report_email, report_recipients.';

-- Partial index: quickly find schools with SIGNL4 configured
CREATE INDEX IF NOT EXISTS idx_schools_signl4
  ON schools ((notification_config->>'signl4_webhook'))
  WHERE notification_config->>'signl4_webhook' IS NOT NULL;

-- Partial index: schools with instant match alerting enabled
CREATE INDEX IF NOT EXISTS idx_schools_alert_on_match
  ON schools ((notification_config->>'alert_on_match'))
  WHERE notification_config->>'alert_on_match' = 'true';

-- Helper view: schools with any active notification channel
CREATE OR REPLACE VIEW v_schools_notify AS
SELECT
  id,
  tenant_id,
  name,
  city,
  plan,
  notification_config,
  notification_config->>'signl4_webhook'            AS signl4_webhook,
  notification_config->>'telegram_chat_id'          AS telegram_chat_id,
  COALESCE((notification_config->>'fit_score_threshold')::int, 70) AS fit_score_threshold,
  COALESCE((notification_config->>'alert_on_match')::boolean, false) AS alert_on_match,
  COALESCE((notification_config->>'weekly_report_email')::boolean, true) AS weekly_report_email
FROM schools
WHERE active = true
  AND (
    notification_config->>'signl4_webhook'   IS NOT NULL
    OR notification_config->>'telegram_chat_id' IS NOT NULL
    OR COALESCE((notification_config->>'weekly_report_email')::boolean, true)
  );

COMMENT ON VIEW v_schools_notify IS
  'Active schools with at least one notification channel configured.';

-- schema_versions
INSERT INTO schema_versions (version, description)
VALUES ('3.0', 'Per-school notification_config JSONB: SIGNL4, Telegram, fit_score_threshold, alert_on_match')
ON CONFLICT (version) DO NOTHING;
