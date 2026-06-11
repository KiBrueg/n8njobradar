# JobRadar — Security & Hardening Guide

> Design target: portfolio + small-business grade.
> The system should be demonstrably secure to a technical employer and adaptable to a company environment without a rewrite.

---

## 1. Secrets Management

### Rules
- **No hardcoded secrets anywhere** — not in code, not in workflow JSON exports, not in comments.
- All sensitive values stored in **n8n Credentials** (encrypted at rest by n8n) or environment variables on the VPS.
- n8n workflow exports (`.json` files) must be scrubbed before committing to any repo.

### Variables that must never appear in plaintext
```
ANTHROPIC_API_KEY
FIRECRAWL_API_KEY
POSTGRES_PASSWORD
GMAIL_OAUTH_TOKEN
MAILDE_IMAP_PASSWORD
TELEGRAM_BOT_TOKEN
WEBHOOK_SECRET
```

### Recommended pattern on VPS
```bash
# /etc/n8n/.env — readable only by n8n process user
chmod 600 /etc/n8n/.env
chown n8n:n8n /etc/n8n/.env
```

---

## 2. Input Validation & Sanitization

### raw_text size limit
Before sending to Claude, enforce a max size in the n8n Code node:

```javascript
const MAX_BYTES = 32_000; // ~8k tokens, well within Claude context
const text = $json.raw_text || '';

if (Buffer.byteLength(text, 'utf8') > MAX_BYTES) {
  // Truncate with marker so Claude knows it's partial
  $json.raw_text = text.slice(0, MAX_BYTES) + '\n[TRUNCATED]';
}
```

### Why: prevents accidental token overflow and protects against prompt injection via email body.

### Null/empty guard
```javascript
if (!$json.raw_text || $json.raw_text.trim().length < 10) {
  // Route to ignore branch — don't call Claude at all
  $json.skip = true;
}
```

### Email header stripping
Strip tracking pixels and dangerous HTML before passing to Claude:
- Use Textcleaner or a simple regex pass in n8n Code node.
- Remove `<script>`, `<img>`, `<a href>` tags from HTML-only emails.
- Never pass raw HTML to Claude — convert to plain text first.

---

## 3. SQL Injection Prevention

### Rule: parameterized queries only

n8n Postgres node supports parameterized queries via the **"Execute Query"** operation with `$1, $2, ...` placeholders.

**Never do this:**
```sql
-- WRONG — string interpolation
INSERT INTO companies (company_id, name)
VALUES ('{{ $json.company_id }}', '{{ $json.company_name }}');
```

**Always do this:**
```sql
-- CORRECT — parameterized
INSERT INTO companies (company_id, name)
VALUES ($1, $2)
ON CONFLICT (company_id) DO NOTHING;
```
With parameters array: `[$json.job_event.company_id, $json.job_event.company_name]`

### Additional: validate enums before DB write

In the n8n Code node before DB upsert, validate that stage/priority/category are in the allowed set:

```javascript
const VALID_STAGES = ['discovered','applied','screening','interview',
                      'test_task','offer','rejected','withdrawn','on_hold'];
const VALID_PRIORITIES = ['high','medium','low'];

const stage = VALID_STAGES.includes($json.job_event.stage)
  ? $json.job_event.stage : null;

const priority = VALID_PRIORITIES.includes($json.job_event.priority)
  ? $json.job_event.priority : null;
```

---

## 4. Webhook Security (Manual Flow)

The manual input endpoint must not be publicly accessible without authentication.

### Option A: Static secret header (simple, good for personal use)
```
POST /webhook/jobradar-manual
Header: X-Webhook-Secret: <WEBHOOK_SECRET>
```

n8n Header Auth node validates the value against `$env.WEBHOOK_SECRET`.

### Option B: HMAC signature (better, production-grade)
Caller signs the body with a shared secret → n8n verifies:
```javascript
const crypto = require('crypto');
const sig = $request.headers['x-signature'];
const body = JSON.stringify($json);
const expected = crypto
  .createHmac('sha256', $env.WEBHOOK_SECRET)
  .update(body)
  .digest('hex');

if (sig !== expected) throw new Error('Invalid webhook signature');
```

### IP allowlist (optional hardening)
Restrict webhook endpoint to known IPs via VPS firewall (ufw/iptables) if the caller is fixed.

---

## 5. PII & Data Privacy

Email bodies contain personal data (names, addresses, communication history).

### Rules
- **raw_text is stored in job_events.raw_text** — Postgres at rest should be encrypted (VPS disk encryption or Postgres TDE).
- **Never log raw_text to Telegram notifications** — log only: company, stage, job_title, event_id.
- **Retention policy:** Consider a cron job that NULLs `raw_text` in job_events older than 90 days (keeps parsed_json, deletes original body).
- **Telegram channel storage:** If using Telegram as blob storage for email bodies, use a private channel accessible only to you. Treat `file_id` as sensitive.

### GDPR considerations (if ever used for others)
- Add `data_owner_id` / `tenant_id` to all tables (stubs already in schema).
- Implement DELETE cascade on user/tenant removal.
- Document what data is stored and for how long.

---

## 6. PostgreSQL Hardening

### Row Level Security (RLS) — stub for future multi-user

RLS is already stubbed in `db/schema.sql`. When adding a second user:

```sql
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY jobs_tenant_isolation ON jobs
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

n8n sets the tenant context before queries:
```sql
SET LOCAL app.current_tenant_id = '<uuid>';
```

### DB user permissions (principle of least privilege)

```sql
-- App user: read/write to job tables only
CREATE ROLE jobradar_app LOGIN PASSWORD '<strong_password>';
GRANT SELECT, INSERT, UPDATE ON companies, employers, jobs, job_events TO jobradar_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO jobradar_app;

-- Read-only user for analytics/Sheets sync
CREATE ROLE jobradar_readonly LOGIN PASSWORD '<strong_password>';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO jobradar_readonly;
```

### Connection pooling
Use **PgBouncer** in front of Postgres on VPS (transaction mode):
- Prevents connection exhaustion if n8n runs many parallel workflows.
- n8n connects to PgBouncer (port 6432), not Postgres directly (port 5432).
- Postgres port 5432 blocked at firewall — only localhost access.

---

## 7. Rate Limiting & Circuit Breaker

### Claude API rate limits
- claude-sonnet-4-6: ~40k tokens/min (Anthropic Tier 1). A job email ≈ 2k tokens → ~20 parallel calls safe.
- In n8n: use **Batch** node (batch size = 5) + **Wait** node (3s delay) when processing bulk scraped jobs.
- On 529 (overloaded): retry with exponential backoff — 5s, 15s, 45s, then dead-letter.

### Firecrawl rate limits
- Free tier: 500 credits/month. Monitor usage.
- In n8n: add counter in Postgres (`scrape_runs` table) or check Firecrawl dashboard via API.

### Dead-letter pattern
Failed items (Claude error, DB error) → write to `job_events` with `action = 'error'` and `parsed_json = { error: "...", raw_text_hash: "..." }`. Never lose an item silently.

---

## 8. Audit & Observability

### Immutable audit log
`job_events` is append-only — **never DELETE from job_events**. It's the audit trail.

Each event records:
- Who triggered it (`input_source`, `email_account_id`)
- When (`created_at`, `email_date`)
- What Claude returned (`parsed_json`)
- What the raw input was (`raw_text`, `raw_reference`)

### Structured logging in n8n
Use n8n's built-in execution log + optionally forward to a log aggregator (Loki/Grafana stack on VPS).

Log format for Telegram alerts (safe, no PII):
```
[JobRadar] New event: interview_invite
Company: Acme GmbH | Role: Senior BE | Stage: interview
Date: 2026-06-12 14:00 UTC | Priority: high
EventID: <job_event.id>
```

---

## 9. Dependency & Code Security

- **n8n version:** Pin to a specific version in Docker Compose. Update deliberately, not automatically.
- **Docker:** Run n8n as non-root user. Use read-only filesystem where possible.
- **VPS firewall (ufw rules):**
  ```
  Allow: 22 (SSH, key-only), 443 (HTTPS for n8n), 80 (redirect to 443)
  Deny: 5432 (Postgres — internal only), 6379 (Redis — internal only)
  ```
- **n8n behind reverse proxy:** Nginx with TLS (Let's Encrypt). n8n not exposed on raw port.
- **Regular backups:** Postgres `pg_dump` daily → encrypted → offsite (Telegram channel or S3).

---

## 10. Security Checklist (deploy readiness)

- [ ] All secrets in n8n Credentials or `.env`, none in workflow JSON
- [ ] Webhook endpoint protected with secret header or HMAC
- [ ] All SQL queries parameterized (no string interpolation)
- [ ] raw_text size capped at 32KB before Claude call
- [ ] Enum validation before DB write
- [ ] DB user has minimal permissions (not superuser)
- [ ] Postgres not accessible from public internet
- [ ] n8n behind HTTPS reverse proxy
- [ ] VPS firewall configured (ufw)
- [ ] Docker containers run as non-root
- [ ] PgBouncer configured for connection pooling
- [ ] Telegram notifications contain no raw email body / PII
- [ ] Dead-letter pattern implemented (failed events logged, not dropped)
- [ ] n8n workflow JSON exports scrubbed before any repo commit
- [ ] Disk encryption enabled on VPS
