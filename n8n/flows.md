# JobRadar — n8n Workflow Specifications

> **Last updated:** 2026-06-10

> **Scope note:** This document describes the **logical design** of JobRadar workflows — what each flow does, what data it passes to Claude, and how it maps results to DB/Calendar/labels. It does NOT describe n8n infrastructure setup, credential configuration, or deployment. Those live in the "n8n automation project". All flows are implemented on top of the existing `Trigger → Normalize → LLM → DB write → Side effects` pattern from the n8n core.

> **Flows:** Email (Gmail) · Email (mail.de/IMAP) · Scraper (Firecrawl) · Manual (Webhook/Form) · **Job APIs (Combined)** · **Daily Digest** · Document Generation (Anschreiben + Lebenslauf)

## Schedule overview

| Flow | File | Trigger | Sources |
|------|------|---------|---------|
| Job APIs (Combined) | `job-apis-flow-api.json` | 04:00 daily | Arbeitnow + Remotive + RemoteOK API |
| Firecrawl Scraper | `firecrawl-flow-api.json` | 04:00 daily | berlinstartupjobs, indeed.de, remotely.de, devjobs.de, weworkremotely |
| Daily Digest | `daily-digest-flow-api.json` | 07:00 daily | DB → Telegram (TOP-5 of last 24h) |
| Gmail | `gmail-flow-api.json` | Realtime (Gmail trigger) | Gmail inbox |
| mail.de | `mailde-flow-api.json` | Every 15 min | IMAP inbox |
| Manual | `manual-flow-api.json` | Webhook (on demand) | Pasted text |

---

## Shared: LLM Call Node (OpenRouter → Qwen3)

Used identically in all flows.

**Node type:** HTTP Request  
**Method:** POST  
**URL:** `https://openrouter.ai/api/v1/chat/completions`  
**Headers:**
```
Authorization: Bearer {{ $env.OPENROUTER_API_KEY }}
content-type: application/json
```

**Body:**
```json
{
  "model": "qwen/qwen3-30b-a3b-instruct-2507",
  "max_tokens": 2048,
  "messages": [
    {
      "role": "system",
      "content": "{{ $env.JOBRADAR_SYSTEM_PROMPT }}"
    },
    {
      "role": "user",
      "content": "{{ JSON.stringify($json.normalized_input) }}"
    }
  ]
}
```

**Output:** Extract `choices[0].message.content`, strip `<think>...</think>` CoT blocks and markdown fences, parse as JSON → `$json.job_event`.

> **Note:** Qwen3 outputs Chain-of-Thought blocks wrapped in `<think>...</think>` before the JSON. The Parse node strips them with:
> ```js
> raw = raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
> ```

---

## Shared: DB Upsert Node

**Node type:** Postgres  
**Operation:** Execute Query

### Step 1 — Upsert company
```sql
INSERT INTO companies (company_id, name, meta)
VALUES (
  {{ $json.job_event.company_id }},
  {{ $json.job_event.company_name }},
  '{}'::jsonb
)
ON CONFLICT (company_id) DO NOTHING;
```

### Step 2 — Upsert employer (if employer_id present)
```sql
INSERT INTO employers (employer_id, company_id, name)
VALUES (
  {{ $json.job_event.employer_id }},
  {{ $json.job_event.company_id }},
  {{ $json.job_event.employer_name }}
)
ON CONFLICT (employer_id) DO UPDATE SET
  name = EXCLUDED.name,
  updated_at = NOW();
```
Skip if `employer_id` is null.

### Step 3 — Upsert job
```sql
INSERT INTO jobs (
  job_id_fuzzy, company_id, employer_id, job_title, location,
  seniority, work_mode, work_mode_raw, working_hours,
  salary_currency, salary_min, salary_max, salary_period,
  tech_stack, key_requirements,
  current_stage, priority, priority_level,
  interview_date, response_deadline, application_deadline,
  call_count, source_url, source_input, summary
)
VALUES ( ... )
ON CONFLICT (job_id_fuzzy) DO UPDATE SET
  current_stage        = EXCLUDED.current_stage,
  priority             = EXCLUDED.priority,
  priority_level       = EXCLUDED.priority_level,
  interview_date       = COALESCE(EXCLUDED.interview_date, jobs.interview_date),
  response_deadline    = COALESCE(EXCLUDED.response_deadline, jobs.response_deadline),
  application_deadline = COALESCE(EXCLUDED.application_deadline, jobs.application_deadline),
  tech_stack           = CASE WHEN array_length(EXCLUDED.tech_stack, 1) > 0
                              THEN EXCLUDED.tech_stack ELSE jobs.tech_stack END,
  summary              = EXCLUDED.summary,
  updated_at           = NOW()
RETURNING id;
```

### Step 4 — Insert job_event (always, immutable log)
```sql
INSERT INTO job_events (
  job_id, job_thread_key, job_id_fuzzy,
  input_source, source_detail, raw_reference, email_date,
  category, is_job_related, action,
  stage, priority, priority_level,
  interview_date, response_deadline, application_deadline,
  call_platform, call_platform_raw,
  raw_text, parsed_json
)
VALUES ( ... );
```

---

## Flow 1 — Email Flow

**Purpose:** Parse job-related Gmail messages → update tracker → create calendar events → apply labels.

### Nodes

```
[Gmail Trigger]
    ↓
[Filter: is job label?]
    ↓
[Normalize Email]
    ↓
[Claude Call]
    ↓
[IF: is_job_related = false] → [Stop / Gmail: Add label "job-ignored"]
    ↓ (true)
[DB Upsert]
    ↓
[IF: interview_date present] → [Google Calendar: Create/Update Event]
    ↓
[Gmail: Add label based on category]
    ↓
[IF: priority = high] → [Telegram: Send notification]
```

### Gmail Trigger config
- **Event:** Message Received  
- **Filters:** Label = `job` OR Label = `hiring` (configure in Gmail first)  
- **Fields to extract:** `id`, `threadId`, `from`, `subject`, `date`, `body` (plain text preferred)

### Normalize Email node (Set node or Code node)
```json
{
  "input_source": "email",
  "source_detail": "email",
  "email_account_id": "gmail_main",
  "email_address": "{{ $env.GMAIL_ADDRESS }}",
  "email_provider": "gmail",
  "subject": "{{ $json.subject }}",
  "date": "{{ $json.date }}",
  "raw_text": "{{ $json.body }}",
  "raw_meta": {
    "thread_id": "{{ $json.threadId }}",
    "message_id": "{{ $json.id }}",
    "sender": "{{ $json.from }}"
  }
}
```

### Gmail label mapping

| category | Label to apply |
|----------|---------------|
| interview_invite | `job/interview` |
| offer | `job/offer` |
| rejection | `job/rejected` |
| test_task | `job/test-task` |
| newsletter | `job/newsletter` |
| other / follow_up | `job/active` |

### Google Calendar event
- **Calendar:** "Job Interviews" (dedicated calendar)
- **Title:** `[company_name] — [job_title] interview`
- **Start:** `interview_date`
- **Duration:** 1 hour (default)
- **Description:** `summary` + link to source email
- **Update if exists:** match by `job_thread_key` in event description

### Rejection side effects (category = "rejection")

Triggered when LLM returns `category: "rejection"`. Runs in parallel after DB Upsert.

```
[IF: category = "rejection"]
    ↓
    ├─→ [Notion: Update Bewerbungen]
    │       Search by Unternehmen = company_name
    │       → set Status = "Abgelehnt"
    │       → append to Notizen: "Absage erhalten: {{ date }}"
    │
    └─→ [Google Calendar: Remove interview event]
            Search events in "Job Interviews" calendar
            where title contains company_name OR description contains job_thread_key
            → Delete event if found (or rename to "❌ [original title]" if prefer to keep)
    ↓
[Telegram: Absage notification (optional)]
    "❌ Absage: {{ company_name }} — {{ job_title }}"
```

**Notion API call (n8n HTTP Request node):**
```
PATCH https://api.notion.com/v1/pages/{{ page_id }}
Headers: Authorization: Bearer {{ NOTION_TOKEN }}, Notion-Version: 2022-06-28
Body:
{
  "properties": {
    "Status": { "select": { "name": "Abgelehnt" } },
    "Notizen": { "rich_text": [{ "text": { "content": "{{ existing_notizen }}\nAbsage erhalten: {{ email_date }}" } }] }
  }
}
```

To find the page_id: first call `POST https://api.notion.com/v1/databases/387e9707-d991-8163-8a85-000b44201f36/query` with filter `{ "filter": { "property": "Unternehmen", "title": { "contains": "{{ company_name }}" } } }`.

**Google Calendar search:**
Use Google Calendar API (n8n HTTP node or Calendar node):
`GET /calendars/primary/events?q={{ company_name }}&timeMin={{ now }}&singleEvents=true`
→ Filter results where event title or description contains `company_name`
→ `DELETE /calendars/primary/events/{{ event_id }}`

**Fallback if Notion page not found:** Log `company_name` + `email_date` to `job_events.parsed_json` under key `rejection_unmatched: true`. Do not block the main flow.

### Error handling
- On Claude API error: retry 2×, then route to "Error" Gmail label + Telegram alert.
- On DB error: log to `job_events.parsed_json` anyway (raw log preserved).
- On Notion update error: log to DB, continue — non-blocking.
- On Calendar delete error: log to DB, continue — non-blocking.

---

## Flow 1b — Email Flow (mail.de / IMAP)

**Purpose:** Parse job-related emails from mail.de via IMAP → same pipeline as Gmail flow.

### Key differences from Gmail Flow

| Aspect | Gmail Flow | mail.de Flow |
|--------|-----------|-------------|
| Trigger | Gmail Trigger (API) | IMAP node (scheduled polling) |
| `email_account_id` | `"gmail_main"` | `"mailde_main"` |
| `email_provider` | `"gmail"` | `"imap"` |
| `email_address` | Gmail address | mail.de address |
| Thread ID | `threadId` from Gmail API | Construct from `Message-ID` header |
| Label actions | Gmail API labels | Not applicable (IMAP — mark as read only) |

### Nodes

```
[Schedule Trigger (every N minutes)]
    ↓
[IMAP: Fetch unseen emails from mail.de]
    ↓
[Filter: subject/sender contains job keywords]
    ↓
[Normalize Email (mail.de)]
    ↓
[Claude Call]  ← shared
    ↓
[IF: is_job_related = false] → [IMAP: Mark as Read, Stop]
    ↓ (true)
[DB Upsert]  ← shared
    ↓
[IF: interview_date present] → [Google Calendar: Create/Update Event]
    ↓
[IMAP: Mark as Read]
    ↓
[IF: priority = high] → [Telegram: Send notification]
```

### IMAP node config
- **Host:** `imap.mail.de`  
- **Port:** 993 (SSL)  
- **Mailbox:** `INBOX`  
- **Filter:** unseen only  
- **Format:** `text/plain` preferred, fallback `text/html` → strip tags

### Schedule recommendation
- Poll every 15 minutes during working hours (07:00–22:00 UTC)
- Every 60 minutes overnight

### Normalize Email (mail.de)
```json
{
  "input_source": "email",
  "source_detail": "email",
  "email_account_id": "mailde_main",
  "email_address": "{{ $env.MAILDE_ADDRESS }}",
  "email_provider": "imap",
  "subject": "{{ $json.subject }}",
  "date": "{{ $json.date }}",
  "raw_text": "{{ $json.text }}",
  "raw_meta": {
    "message_id": "{{ $json.messageId }}",
    "sender": "{{ $json.from }}"
  }
}
```

Note: IMAP doesn't provide a thread_id natively. `job_thread_key` will be derived by Claude from `company_id` + subject hash, or by n8n from `In-Reply-To` / `References` headers if available.

### Rejection side effects

Same as Flow 1 — see "Rejection side effects" section above. Applied identically: Notion update + Calendar delete + optional Telegram notification.

### Error handling
- IMAP connection failure: retry 3×, then Telegram alert.
- Same Claude error handling as Gmail flow.
- Notion/Calendar errors on rejection: non-blocking, logged to DB.

---

## Flow 2 — Scraper Flow (Firecrawl)

**Purpose:** Scheduled scraping of job pages → normalize → parse → persist.

### Nodes

```
[Schedule Trigger (cron)]
    ↓
[Read scrape targets] ← (Google Sheets or static list in n8n)
    ↓
[HTTP: Firecrawl /crawl or /scrape]
    ↓
[Wait: Poll /crawl/{id} until status=completed] (or use webhook callback)
    ↓
[Split into individual job items]
    ↓
[Normalize Scraped Item]
    ↓
[Claude Call]
    ↓
[IF: is_job_related = false] → [Skip]
    ↓ (true)
[DB Upsert]
    ↓
[Google Sheets: Append/Update row in Applications sheet]
```

### Schedule
- Default: every day at 08:00 UTC  
- For active search: every 4 hours

### Firecrawl API call
```
POST https://api.firecrawl.dev/v1/crawl
{
  "url": "{{ $json.target_url }}",
  "limit": 50,
  "scrapeOptions": {
    "formats": ["markdown", "links"],
    "onlyMainContent": true
  }
}
```
Then poll `GET /v1/crawl/{id}` every 30s until `status: "completed"`.

### Normalize Scraped Item
```json
{
  "input_source": "scraped",
  "source_detail": "scraped_json",
  "subject": "{{ $json.metadata.title }}",
  "date": null,
  "raw_text": "{{ $json.markdown }}",
  "raw_meta": {
    "url": "{{ $json.metadata.sourceURL }}"
  }
}
```

### Dedup check (before Claude call)
```sql
SELECT id FROM jobs WHERE job_id_fuzzy = {{ computed_fuzzy_id }};
```
If found AND `updated_at > NOW() - INTERVAL '24 hours'` → skip (already fresh).

### Error handling
- Firecrawl timeout: log URL to error sheet, continue with next target.
- Claude error: retry 2×, skip item, log to error sheet.

---

## Flow 3 — Manual Flow

**Purpose:** Accept pasted job descriptions or post-call notes via webhook or n8n form.

### Nodes

```
[Webhook / n8n Form trigger]
    ↓
[Validate: raw_text not empty]
    ↓
[Normalize Manual Input]
    ↓
[Claude Call]
    ↓
[IF: is_job_related = false] → [Return error response to user]
    ↓ (true)
[DB Upsert]
    ↓
[Return success JSON to caller]
    ↓
[IF: interview_date present] → [Google Calendar: Create Event]
```

### Webhook / Form fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `raw_text` | textarea | yes | Job description or post-call note |
| `subject` | text | no | Optional: job title or email subject |
| `source_url` | text | no | URL if from a website |
| `category_hint` | select | no | Hint: job_posting / manual_note / other |

### Normalize Manual Input
```json
{
  "input_source": "manual",
  "source_detail": "manual_text",
  "subject": "{{ $json.subject || null }}",
  "date": "{{ new Date().toISOString() }}",
  "raw_text": "{{ $json.raw_text }}",
  "raw_meta": {
    "url": "{{ $json.source_url || null }}",
    "category_hint": "{{ $json.category_hint || null }}"
  }
}
```

### Response (success)
```json
{
  "status": "ok",
  "job_id_fuzzy": "{{ $json.job_event.job_id_fuzzy }}",
  "stage": "{{ $json.job_event.stage }}",
  "category": "{{ $json.job_event.category }}",
  "summary": "{{ $json.job_event.summary }}"
}
```

---

## Flow 4 — Document Generation (Anschreiben + Lebenslauf)

**Purpose:** On-demand generation of a tailored cover letter (Anschreiben) and CV highlights for a specific vacancy. Triggered manually per job, not automatically.

**Design principle:** Claude generates text only (Markdown). Google Docs handles formatting and export. No binary conversion in n8n. User edits in Google Docs, exports to PDF/DOCX/ODT as needed — standard for German HR.

### Trigger

Google Sheets button (Apps Script) sends a POST to the n8n webhook with `job_id_fuzzy`. Alternatively: a Telegram bot command `/generate <job_id_fuzzy>`.

```
POST {{ $env.N8N_WEBHOOK_BASE }}/webhook/generate-docs
Body: { "job_id_fuzzy": "acme-solutions__senior-backend-engineer__berlin-germany" }
```

HMAC-SHA256 webhook auth applies (same as Manual Flow).

### Nodes

```
[Webhook trigger: /generate-docs]
    ↓
[Validate: job_id_fuzzy present]
    ↓
[Postgres: SELECT job data]
    ↓
[Google Drive: Fetch base CV (Markdown template)]
    ↓
[Claude: Generate Anschreiben + CV highlights]
    ↓
[Google Docs: Create document in Drive]
    ↓
[Telegram: Send doc link + job summary]
    ↓
[Google Sheets: Update "docs_ready" column with Drive link]
```

### Postgres query
```sql
SELECT
  company_name, job_title, location, work_mode, seniority,
  salary_min, salary_max, salary_currency, salary_period,
  tech_stack, key_requirements, summary, stage
FROM jobs
WHERE job_id_fuzzy = $1 AND tenant_id = $2;
```

### Base CV storage

Stored as a **Markdown file** in Google Drive at a fixed path, e.g.:  
`/JobRadar/templates/base-lebenslauf.md`

Contains: personal info, education, work history, skills, languages — in structured Markdown sections. Claude reads this as plain text input.

### Claude prompt (document generation)

This is a **separate system prompt** (not prompt-system.txt — that's for parsing).  
Stored at: `spec/prompt-docgen.txt`

Input to Claude:
```json
{
  "job": {
    "company_name": "...",
    "job_title": "...",
    "location": "...",
    "tech_stack": [...],
    "key_requirements": [...],
    "work_mode": "...",
    "seniority": "...",
    "salary_min": ...,
    "summary": "..."
  },
  "base_cv_markdown": "{{ full text of base-lebenslauf.md }}",
  "language": "de"
}
```

Claude output (Markdown):
```
## Anschreiben

[Personalized cover letter in German, ~300–400 words]

---

## Lebenslauf — Angepasste Highlights

[Reordered/highlighted skills and experience sections tailored to this role]
[Base CV structure preserved; only emphasis and ordering adjusted]
```

Claude does **not** rewrite the full CV — it adjusts emphasis and adds a tailored summary paragraph. This keeps output compact and tokens low.

### Google Docs node

**Node type:** Google Docs (n8n built-in)  
**Operation:** Create document  
**Title:** `Anschreiben — {{ company_name }} — {{ job_title }}`  
**Content:** Claude's Markdown output (converted to plain text / basic formatting)  
**Folder:** `/JobRadar/applications/{{ company_id }}/`

The folder is auto-created if missing via Google Drive node.

### Output

- Google Doc created in Drive: editable, exportable to PDF/DOCX/ODT by user
- Telegram message: doc link + one-line summary (company, role, date)
- Google Sheets: Drive link written to column `docs_url`, status `docs_ready = true`

### Token estimate

- Base CV: ~800–1200 tokens (Markdown)
- Job data: ~200–400 tokens (structured fields, not raw email)
- Output Anschreiben + highlights: ~600–900 tokens
- **Total per generation: ~1600–2500 tokens** — negligible cost

### Error handling

- Job not found in DB → 404 response, Telegram alert
- Google Drive fetch error → Telegram alert with fallback: use hardcoded template stub
- Claude error: retry 2×, then Telegram alert with error details
- Google Docs creation error: save Markdown output to Telegram as fallback

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key (used by all LLM call nodes) |
| `JOBRADAR_SYSTEM_PROMPT` | Full system prompt from `spec/prompt-system.txt` (single-line, loaded at n8n startup) |
| `FIRECRAWL_API_KEY` | Firecrawl API key |
| `GMAIL_ADDRESS` | Gmail address (written to `email_address` field in normalize) |
| `MAILDE_ADDRESS` | mail.de address (written to `email_address` field in normalize) |
| `MAILDE_IMAP_PASSWORD` | mail.de IMAP password |
| `POSTGRES_HOST` | DB host |
| `POSTGRES_DB` | DB name |
| `POSTGRES_USER` | DB user |
| `POSTGRES_PASSWORD` | DB password |
| `TELEGRAM_BOT_TOKEN` | For notifications (optional) |
| `TELEGRAM_CHAT_ID` | For notifications (optional) |

---

---

## Flow 5 — Job APIs (Combined)

**File:** `n8n/job-apis-flow-api.json`  
**Purpose:** Fetch jobs from 3 free APIs in parallel → merge → normalize → LLM parse → DB upsert → Telegram alert for high-priority jobs.

### Schedule
- **04:00 CET daily** (3h before Daily Digest)

### Sources (in parallel)

| API | URL | Response shape |
|-----|-----|----------------|
| Arbeitnow | `https://www.arbeitnow.com/api/job-board-api?page=1` | `{ data: [...] }` |
| Remotive | `https://remotive.com/api/remote-jobs?search=automation+engineer&limit=50` | `{ jobs: [...] }` |
| RemoteOK | `https://remoteok.com/api?tags=automation` | `[{legal}, {job1}, ...]` — skip index 0 |

### Node structure
```
Schedule 04:00
  ├─→ Arbeitnow: Fetch Jobs → Flatten: Arbeitnow ─┐
  ├─→ Remotive: Fetch Jobs  → Flatten: Remotive  ─┤→ Merge (append, 3 inputs)
  └─→ RemoteOK: Fetch Jobs  → Flatten: RemoteOK  ─┘
        ↓
    Normalize: API Job  (source-aware: arbeitnow/remotive/remoteok)
        ↓
    Dedup Check  (skip if source_url seen < 24h ago)
        ↓
    IF: not already processed
      ↓ true                ↓ false
  Skip Security Checks   Already Processed: Skip (NoOp)
        ↓
    LLM Call (OpenRouter/Qwen3)
        ↓
    Parse LLM Response  (strip <think>, validate)
        ↓
    IF: is_job_related
      ↓ yes              ↓ no
  Prepare DB Params   Not Job Related: Stop (NoOp)
        ↓
    DB: Write All  (companies + employers + jobs + job_events)
        ↓
    IF: priority = high
      ↓ yes    ↓ no
  Telegram: Job Alert   (end)
```

### Key design notes
- `source_label` tag added by each Flatten node → flows through Normalize → Prepare DB → stored in `job_events.source_detail` as `arbeitnow_api` / `remotive_api` / `remoteok_api`
- `sender_risk_level = 'low'` for all API sources (trusted, no user-submitted content)
- RemoteOK: requires `User-Agent` header; `[0]` is legal notice — filtered in Flatten node
- Dedup key: `source_url` permalink unique per job

---

## Flow 6 — Daily Digest

**File:** `n8n/daily-digest-flow-api.json`  
**Purpose:** Every morning — query DB for top relevant jobs discovered in the last 24h, send one formatted Telegram message.

### Schedule
- **07:00 CET daily** (3h after API/scraper flows finish)

### Node structure
```
Schedule 07:00
    ↓
DB: Fetch TOP-5 Jobs  (Postgres SELECT with LATERAL JOIN)
    ↓
Format Digest Message  (Code node — aggregates all rows, returns [] if empty)
    ↓
Telegram: Send Digest
```

### DB query logic
```sql
SELECT j.job_title, c.name AS company_name, j.location,
       j.work_mode, j.priority, j.source_url, j.summary,
       COALESCE((ev.parsed_json->>'relevance_score')::int, 0) AS relevance_score
FROM jobs j
JOIN companies c ON c.company_id = j.company_id
JOIN LATERAL (
  SELECT parsed_json FROM job_events WHERE job_id = j.id
  ORDER BY created_at DESC LIMIT 1
) ev ON TRUE
WHERE j.created_at >= NOW() - INTERVAL '24 hours'
  AND COALESCE((ev.parsed_json->>'relevance_score')::int, 0) >= 80
ORDER BY relevance_score DESC
LIMIT 5;
```

Note: `relevance_score` is stored in `job_events.parsed_json` (LLM output), not as a column in `jobs`. Retrieved via LATERAL JOIN on the latest event per job.

### Telegram message format (HTML)
```
📊 JobRadar — Daily Digest
Top jobs discovered in the last 24h

🥇 Senior Automation Engineer
   🏢 TechCorp | 📍 Berlin (Remote)
   ⭐ Relevance: 95/100
   💬 Building n8n-based automation for B2B SaaS...
   🔗 View posting

🥈 AI/ML Engineer
   🏢 StartupXYZ | 📍 Worldwide (remote)
   ⭐ Relevance: 88/100
   ...

📅 10.06.2026 | 3 jobs matched
```

If 0 jobs qualify (relevance >= 80, created in last 24h) — no message is sent.

---

## Backup Script

**File:** `scripts/backup.sh`  
**Deploy to VPS:** `/home/kirill/backup.sh`

### Deploy steps (via Hetzner Console)
```bash
# 1. Paste script content into /home/kirill/backup.sh
nano /home/kirill/backup.sh   # paste, save

# 2. Make executable
chmod +x /home/kirill/backup.sh

# 3. Create backup directory
mkdir -p /home/kirill/backups

# 4. Test run
/home/kirill/backup.sh

# 5. Add to crontab (3x/day: 08:00, 14:00, 22:00 CET = UTC+2 → 06:00, 12:00, 20:00 UTC)
crontab -e
# Add: 0 6,12,20 * * * /home/kirill/backup.sh --quiet
```

### What the script does
- `pg_dump jobradar` from `n8n-automation-postgres-1` container
- Compresses with gzip → `/home/kirill/backups/jobradar_YYYY-MM-DD_HH-MM.sql.gz`
- Keeps last 7 backups (rotates older ones)
- Logs to syslog (`logger -t jobradar-backup`)
- Exits with error if container not running or dump fails

### Restore
```bash
gunzip -c /home/kirill/backups/jobradar_2026-06-10_06-00.sql.gz \
  | docker exec -i n8n-automation-postgres-1 psql -U hub jobradar
```

---

## Open Questions / TODOs

- [ ] Firecrawl: polling vs webhook callback — decide before implementation.
- [ ] Scrape target list: static JSON in n8n vs Google Sheets config tab?
- [ ] Gmail label structure: auto-create labels via Gmail API on first run?
- [ ] DB: store `raw_text` inline or offload to S3 for large emails?
- [ ] Dedup strategy: n8n IF node check vs Postgres `ON CONFLICT` only?
- [ ] Telegram notification threshold: only `priority=high`, or all new jobs?
