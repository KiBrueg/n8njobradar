# JobRadar Automation Intelligence Hub — Architecture

> **Status:** Draft v1  
> **Last updated:** 2026-06-08  
> **Author:** Kirill Brüggemann  

---

## 0. Project Boundary

This document describes the **JobRadar intelligence layer only**.

The automation infrastructure (n8n VPS, credentials, deployment, generic trigger/LLM/DB patterns) is defined in the separate **"n8n automation project"**. This project assumes that core is stable and available.

**In scope here:** JSON contract, system prompts, Postgres schema, logical workflow design.  
**Out of scope here:** n8n installation, credential setup, VPS ops, generic automation patterns.

See `CLAUDE.md` for the full boundary definition.

---

## 1. Overview

**Name:** JobRadar Automation Intelligence Hub  
**Goal:** Автоматизировать сбор, разбор и трекинг job-информации из нескольких источников в единую структурированную систему с минимальным ручным вводом.

Система:
- считывает сигналы о вакансиях из Gmail, Firecrawl и ручного ввода;
- нормализует их через Claude в единый JSON-контракт;
- сохраняет в Postgres и "витрины" (Google Sheets, Notion);
- триггерит побочные действия: метки Gmail, события Google Calendar, Kanban-карточки.

Строится поверх существующего n8n-ядра на VPS. n8n и VPS — внешние зависимости, не часть этого проекта.

---

## 2. Sources & Data Flow

### Источники

| # | Источник | Что приходит | Trigger |
|---|----------|-------------|---------|
| 1 | **Gmail** | HR-письма, инвайты, офферы, отказы, рассылки | Gmail Trigger (label filter) |
| 1b | **mail.de (IMAP)** | То же, второй email-аккаунт | IMAP Trigger |
| 2 | **Firecrawl** | JSON/CSV с карьерных страниц и job-бордов | Schedule → Firecrawl API |
| 3 | **Manual input** | Копи-паст текста, заметки после созвона | Webhook / n8n Form |
| 4 | **Document Generation** | On-demand: Anschreiben + Lebenslauf для конкретной вакансии | Manual trigger (Google Sheets button / Telegram command) |

### Унифицированный пайплайн (для всех источников)

```
[Source] → [Normalize in n8n] → [Claude API] → [Persist] → [Actions]
```

**Normalize** — привести к общему envelope:
```json
{
  "input_source": "email|scraped|manual",
  "source_detail": "email|scraped_json|scraped_csv|manual_text",
  "subject": "...",
  "date": "ISO8601",
  "raw_text": "...",
  "raw_meta": {}
}
```

**Claude** — возвращает строгий JSON-контракт (см. `/spec/job-json-schema.json`).

**Persist** → Postgres (source of truth) + Google Sheets/Notion (user-facing views).

**Actions** → Google Calendar events, Gmail labels, Kanban updates.

### Flow 4 — Document Generation (отдельный пайплайн)

Flow 4 не является частью инgest-пайплайна. Это отдельная on-demand ветка поверх уже сохранённых данных:

```
[Manual trigger] → [Postgres: job data] → [Google Drive: base CV template]
    → [Claude: generate Anschreiben + CV highlights (Markdown)]
    → [Google Docs: create document in Drive]
    → [Telegram: share link] + [Google Sheets: update docs_url column]
```

Детали: `n8n/flows.md` → Flow 4.

---

## 3. JSON Contract (Key Fields)

Полная схема: `/spec/job-json-schema.json`  
Системный промт: `/spec/prompt-system.txt`

Топ-уровень объекта:

```
context        — источник, категория, action
identity       — company_id, employer_id, job_id_fuzzy, job_thread_key
process        — stage, priority_level, priority
dates          — interview_date, response_deadline, application_deadline
call           — call_platform, call_platform_raw
conditions     — salary, work_mode, working_hours, seniority
requirements   — tech_stack[], key_requirements[]
tracking       — has_had_call, call_count, last_call_date, user_rating
summary        — краткое резюме на русском
```

Правила:
- Все ключи всегда присутствуют. `null` когда неизвестно.
- `user_rating` — только `"unknown"` из ИИ. Заполняет пользователь.
- Claude не принимает решений о дедупликации — только выставляет ключи.

---

## 4. System Components

### 4.1. AI Layer (Claude — этот проект)

**Ответственность:**
- Хранит спецификацию (JSON Schema, system prompt, архитектура, DB schema, flow notes).
- Парсит входные данные → возвращает Job JSON.
- **Не** вызывает Gmail/Firecrawl/Calendar напрямую — это делает n8n.

**Артефакты:**
```
/spec/job-json-schema.json   — JSON Schema контракта
/spec/prompt-system.txt      — системный промт для Claude
/docs/job-radar-architecture.md  — этот документ
/db/schema.sql               — DDL таблиц Postgres
/n8n/flows.md                — описание воркфлоу
```

### 4.2. Orchestration Layer (n8n on VPS)

**Ответственность:** интеграция источников, вызов Claude, запись в БД, side effects.

Три воркфлоу (детали в `/n8n/flows.md`):

| Flow | Trigger | Steps |
|------|---------|-------|
| **Email Flow** | Gmail label trigger | Gmail → Normalize → Claude → DB → Calendar → Labels |
| **Scraper Flow** | Schedule (cron) | Firecrawl job → Poll → Results → Claude → DB/Sheets |
| **Manual Flow** | Webhook / Form | Raw text → Normalize → Claude → DB/Sheets |

### 4.3. Storage & Views

**Postgres (source of truth):**
```
companies     — company_id, name, base_domain
employers     — employer_id, company_id, name
jobs          — job_id, job_id_fuzzy, employer_id, title, salary, work_mode, ...
job_events    — id, job_id, stage, priority, dates, source, raw_reference
```
Полный DDL: `/db/schema.sql`

**Views (user-facing):**
- **Google Sheets / Notion DB** — таблица Applications: Company, Role, Stage, Priority, Dates, Salary, Rating.
- **Kanban (Notion/Trello)** — колонки = Stage, карточки = Job.
- **Google Calendar** — события по `interview_date`, `response_deadline`, `application_deadline`.

---

## 5. Non-Goals & Constraints

- **Нет auto-apply** на текущем этапе — только трекинг и организация.
- **Claude не дедуплицирует** — выставляет ключи (`job_id_fuzzy`, `job_thread_key`), логика — в n8n/DB.
- **`user_rating` не выставляется ИИ** — всегда `"unknown"`, только пользователь меняет.
- **Один человек** должен уметь развернуть и поддерживать всю систему.
- **Стабильный JSON-контракт** — изменения версионируются, workflow'ы не должны ломаться от апдейта полей.

---

## 6. Implementation Plan

### Stage 1 — Schema & Prompt
1. Финализировать `spec/job-json-schema.json`.
2. Финализировать `spec/prompt-system.txt`.
3. Протестировать на реальных данных: 5–10 job-писем, 5–10 вакансий из Firecrawl, 3–5 "мусорных" писем.

### Stage 2 — DB & Views
1. Создать таблицы в Postgres по `db/schema.sql`.
2. Настроить связи: `job_events ↔ jobs` по `job_id_fuzzy` / `job_thread_key`.
3. Настроить Google Sheets / Notion как витрину (опционально на старте).

### Stage 3 — n8n Flows
1. Email Flow: Gmail Trigger → Normalize → Claude → DB → Calendar → Labels.
2. Scraper Flow: Schedule → Firecrawl → Normalize → Claude → DB.
3. Manual Flow: Webhook/Form → Normalize → Claude → DB.

### Stage 4 — UX & Iteration
1. Настроить Kanban (Notion/Trello) и Google Sheets Application Tracker.
2. Подкрутить промт/схему по реальным данным (особенно date extraction, platform detection).
3. Добавить Telegram-уведомления при смене stage или появлении нового инвайта.

---

## 7. Open Questions

- ~~Postgres vs MongoDB~~ → **Решено: Postgres** (строгая схема = стабильный контракт).
- Хранить `raw_text` inline или в blob storage? → `raw_storage_ref` поле добавлено в `job_events`; Telegram-канал как хранилище — жизнеспособный вариант.
- Firecrawl — polling vs webhook callback? → **Polling** по умолчанию (проще), webhook при промышленном объёме.
- Дедупликация — n8n IF node или Postgres? → **Оба**: n8n делает дешёвый pre-check, Postgres `ON CONFLICT` — финальный барьер.

---

## 8. Security & Scale

> Детальный security checklist: `docs/security.md`

### Ключевые решения

| Область | Решение |
|---------|---------|
| **Secrets** | n8n Credentials (encrypted) + `.env` на VPS (chmod 600) |
| **SQL Injection** | Parameterized queries везде. Строковая интерполяция в SQL — запрещена. |
| **Input validation** | raw_text cap 32KB перед Claude; enum validation перед DB write |
| **Webhook auth** | HMAC-подпись (SHA-256) или статический секрет в заголовке |
| **PII** | raw_text — PII. Очищается через `purge_old_raw_text()` после 90 дней. Telegram-логи без тела письма. |
| **DB access** | Минимальные права: `jobradar_app` (rw, без DELETE на job_events), `jobradar_readonly` (r) |
| **Multi-tenancy** | `tenant_id` на всех таблицах. RLS включён (политика `allow_all` по умолчанию, меняется при добавлении второго тенанта) |
| **Connection pooling** | PgBouncer (transaction mode) перед Postgres |
| **Rate limiting** | Batch + Wait в n8n при bulk-обработке; exponential backoff при 429/529 от Claude |
| **Audit log** | `job_events` — append-only. Без UPDATE/DELETE. `parsed_json` хранится вечно. |
| **Network** | Postgres порт 5432 закрыт для внешних. n8n за HTTPS reverse proxy (Nginx + Let's Encrypt). |
| **Docker** | Non-root контейнеры. n8n workflow JSON-экспорты очищены от секретов перед git. |

### Portfolio/Enterprise readiness

Проект проектируется на уровень **small-business / agency deployment**:

- Один разработчик может развернуть систему с нуля по документации за день.
- При добавлении второго пользователя: включить RLS-политики + добавить `tenant_id` в n8n SET-команду.
- При росте нагрузки: подключить PgBouncer + Redis-очередь для async Claude calls.
- Код и схемы версионированы (`schema_versions` таблица). Миграции — явные SQL-файлы.
