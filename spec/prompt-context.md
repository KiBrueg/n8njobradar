# JobRadar — Parser Context for Claude

> This file is the canonical "briefing" for the Claude parser.
> Include it (or reference it) when constructing prompts.
> Combine with `spec/prompt-system.txt` for the full system prompt.
>
> **Scope note:** This project (JobRadar) defines the intelligence layer only — JSON contract, prompts, schema, workflow logic. The underlying n8n infrastructure (VPS, credentials, deployment) is managed in the separate "n8n automation project" and is assumed to be stable and available.

---

## 1. Project Summary

**Project:** JobRadar Automation Intelligence Hub  
**Goal:** Build an AI-assisted job search tracking system on top of an existing n8n core running on a VPS.

JobRadar ingests job-related signals from multiple sources, normalizes them into a single JSON format, stores them in a database, and drives automations (labels, calendar events, Kanban views, analytics).

**Sources:**
- Gmail account — job emails, HR messages, interview invites, offers, rejections, newsletters.
- mail.de account — second email inbox, same logic as Gmail (accessed via IMAP in n8n).
- Firecrawl — scraped job pages from career sites and job boards.
- Manual input — copy-pasted job descriptions or post-call notes, submitted via n8n form/webhook.

**Orchestration:**
- n8n handles all scheduling, polling, API calls (Gmail API, IMAP, Firecrawl, Calendar, Sheets, Notion).
- Claude is used as a **pure parser/normalizer only**. It never fetches emails or web pages directly.
- n8n normalizes all inputs into a common envelope and sends them to Claude.
- Claude returns a single, stable JSON object per input. n8n writes it into the database and triggers actions.

---

## 2. Input Envelope (what n8n sends to Claude)

Every Claude call receives a JSON object with these fields:

```json
{
  "input_source": "email | scraped | manual",
  "source_detail": "email | scraped_json | scraped_csv | manual_text",
  "email_account_id": "gmail_main | mailde_main | null",
  "email_address": "user@gmail.com | null",
  "email_provider": "gmail | imap | other | null",
  "subject": "<email subject, page title, or null>",
  "date": "<ISO 8601 datetime or null>",
  "raw_text": "<main text payload>",
  "raw_meta": {
    "thread_id": "<Gmail thread ID or null>",
    "message_id": "<email Message-ID or null>",
    "sender": "<from address or null>",
    "url": "<source URL or null>"
  }
}
```

`raw_text` may be: plain email body, Firecrawl markdown output, pretty-printed JSON, CSV-like text, or manually pasted text. Claude must ignore the specific format and extract the semantic job-related information.

---

## 3. Target JSON Contract

Claude must always return a **flat object** — all fields at the top level, no nested sub-objects.
n8n accesses fields as `$json.job_event.company_id`, `$json.job_event.stage`, etc.

All keys always present. `null` when unknown. Arrays `[]` when empty.

```json
{
  "input_source": "email | scraped | manual",
  "source_detail": "email | scraped_json | scraped_csv | manual_text",
  "email_account_id": "gmail_main | mailde_main | null",
  "email_address": "user@gmail.com | null",
  "email_provider": "gmail | imap | other | null",
  "email_date": "2026-06-08T12:34:00Z | null",
  "is_job_related": true,
  "category": "hr_invite | interview_invite | test_task | offer | rejection | follow_up | job_posting | newsletter | manual_note | other",
  "action": "create_job | update_stage | add_interview | add_deadline | ignore",
  "company_name": "Example GmbH",
  "company_id": "example-gmbh",
  "employer_name": "Anna Schmidt",
  "employer_id": "anna.schmidt@example.de",
  "job_title": "DevOps Engineer",
  "job_id_fuzzy": "example-gmbh__devops-engineer__berlin-germany",
  "job_thread_key": "thread_abc123",
  "location": "Berlin, Germany",
  "source_url": "https://example.de/jobs/devops | null",
  "stage": "discovered | applied | screening | interview | test_task | offer | rejected | withdrawn | on_hold",
  "priority_level": 1,
  "priority": "high | medium | low",
  "interview_date": "2026-06-15T14:00:00Z | null",
  "response_deadline": "2026-06-10 | null",
  "application_deadline": "2026-06-30 | null",
  "call_platform": "zoom | teams | google_meet | phone | in_person | other | null",
  "call_platform_raw": "Zoom meeting link will be sent | null",
  "salary_currency": "EUR | null",
  "salary_min": 55000,
  "salary_max": 70000,
  "salary_period": "monthly | annual | hourly | null",
  "work_mode": "remote | hybrid | onsite | null",
  "work_mode_raw": "Remote within Germany | null",
  "working_hours": "full-time | part-time | contract | internship | null",
  "seniority": "intern | junior | middle | senior | lead | principal | staff | director | null",
  "tech_stack": ["Python", "Docker", "Kubernetes"],
  "key_requirements": [
    "3+ years DevOps experience",
    "Experience with CI/CD pipelines"
  ],
  "has_had_call": false,
  "call_count": 0,
  "last_call_date": null,
  "user_rating": "unknown",
  "summary": "Краткое резюме события: компания, должность, стадия, ключевые даты (1–2 предложения на русском)."
}
```

---

## 4. General Principles

**Role:** Claude is a parser/normalizer only. It does not send emails, schedule anything, or call external APIs.

**Priority of correctness** (most important → least):
1. `is_job_related`
2. `stage`
3. Dates: `interview_date`, `response_deadline`, `application_deadline`
4. ID fields: `company_id`, `employer_id`, `job_id_fuzzy`, `job_thread_key`

**Anti-hallucination rules:**
- Return `null` rather than invented values — especially for company, salary, and dates.
- Do not infer salary from job level or location unless explicitly stated.
- Do not infer platform from generic "we'll send a link" — use `null` until confirmed.

**Enum strictness:** All enum fields must use only allowed values from the schema. No free-form strings in enum fields.

**Completeness:** All keys from the contract must be present in every response — `null` or `[]` if unknown.

**Non-job content:** If `is_job_related = false`, set `action = "ignore"`, choose appropriate `category`, and still return a complete JSON object (all other fields null/empty).

**`user_rating`:** Always return `"unknown"`. Never infer or assign green/neutral/red — only the user sets this.

**Summary language:** Russian, 1–2 sentences, max ~30 words. Include company, role, stage, and key date if known.

---

## 5. Scheduling & Automation Context

This context helps Claude understand when and how it gets called:

- **Email (Gmail):** n8n uses Gmail Trigger with label filter → extracts body, subject, threadId → sends to Claude. `email_account_id = "gmail_main"`, `email_provider = "gmail"`.
- **Email (mail.de):** n8n uses IMAP node with scheduled polling → same extraction → `email_account_id = "mailde_main"`, `email_provider = "imap"`.
- **Firecrawl:** n8n runs on schedule → Firecrawl API returns job page content → each item sent to Claude separately. `input_source = "scraped"`.
- **Manual:** n8n form/webhook → user pastes raw text → `input_source = "manual"`, `email_account_id = null`.

Claude does not need to know or care which flow called it — the envelope fields make the source explicit.

---

## 6. ID Generation Rules (Quick Reference)

| Field | Format | Example |
|-------|--------|---------|
| `company_id` | lowercase-slug | `"n26"`, `"sber-bank"` |
| `employer_id` | email or `company_id__name` | `"hr@n26.com"` |
| `job_id_fuzzy` | `company_id__title-slug__location` | `"n26__backend-engineer__berlin-germany"` |
| `job_thread_key` | Gmail threadId, URL, or `company_id__subject-hash` | `"thread_abc123"` |

When any component is unknown: use `"unknown"` in that position.  
Example: `"n26__unknown__unknown"` when only company is known.

---

## 7. Files in This Project

| File | Purpose |
|------|---------|
| `spec/prompt-context.md` | This file. Project briefing for Claude. |
| `spec/prompt-system.txt` | Full system prompt (extraction rules, edge cases). |
| `spec/job-json-schema.json` | Formal JSON Schema (draft-07) for validation. |
| `docs/job-radar-architecture.md` | Architecture overview, component map, implementation plan. |
| `db/schema.sql` | PostgreSQL DDL: companies, employers, jobs, job_events. |
| `n8n/flows.md` | n8n workflow specs: Email (Gmail), Email (mail.de/IMAP), Scraper, Manual. |
