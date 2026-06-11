# Toolstack Reference

> Полный список инструментов, доступных в рамках проекта JobRadar и смежных задач.
> Обновлено: 2026-06-08

---

## AI & Agents

| Инструмент | Роль в проекте |
|-----------|---------------|
| **Claude** (Projects, Artifacts, Live Artifacts) | Основной AI: парсинг писем/вакансий, проектирование схем и промтов |
| **Claude in Chrome** (Beta) | Браузерный агент: скрейпинг, работа с веб-интерфейсами без API |
| **Hermes** (Agent) | Автономный агент для многошаговых задач |
| **Cline** (VS Code extension) | AI-ассистент в редакторе, работа с кодом и файлами |
| **OpenRouter** | Роутинг между моделями (fallback, cost optimization) |
| **Perplexity** | Веб-поиск и быстрый research |

---

## Automation & Orchestration

| Инструмент | Роль в проекте |
|-----------|---------------|
| **n8n** (self-hosted, VPS) | Ядро всей автоматизации: триггеры, флоу, интеграции |
| **Firecrawl** | Скрейпинг карьерных страниц и job-бордов → markdown/JSON для Claude |
| **Telegram Bots** | Уведомления, команды, ручной ввод через чат |

---

## Development & Infrastructure

| Инструмент | Роль в проекте |
|-----------|---------------|
| **VPS** | Хостинг n8n, Postgres, Docker-контейнеров |
| **Docker** | Контейнеризация сервисов на VPS |
| **VS Code** | Разработка, конфигурация, работа с файлами проекта |

---

## Data & Storage

| Инструмент | Роль в проекте |
|-----------|---------------|
| **Postgres** | Основная БД: companies, employers, jobs, job_events |
| **Google Sheets** | Пользовательская витрина: Application Tracker таблица |
| **Notion / Trello** | Kanban-доска для трекинга стадий |
| **Google Calendar** | Автоматические события по interview_date и дедлайнам |

---

## Communication & Input Sources

| Инструмент | Роль в проекте |
|-----------|---------------|
| **Gmail** | Основной email-источник (Gmail API, `email_account_id: "gmail_main"`) |
| **mail.de** | Второй email-источник (IMAP, `email_account_id: "mailde_main"`) |

---

## Utilities

| Инструмент | Роль в проекте |
|-----------|---------------|
| **Snapsum** | Быстрые summary из контента |
| **Snapfile** | Работа с файлами/документами |
| **Textcleaner** | Очистка и нормализация текста перед передачей в AI |

---

## Потенциальные дополнения (не в списке, но логично иметь)

| Инструмент | Зачем может понадобиться |
|-----------|------------------------|
| **Redis** | Кеширование, dedup-очередь для scraped jobs (если Postgres не хватает) |
| **MinIO / S3** | Object storage для raw email body, если не хотим хранить в Postgres |
| **Grafana** | Мониторинг n8n workflow errors, DB metrics |
| **Make (ex-Integromat)** | Резервный оркестратор, если n8n недоступен |
| **LinkedIn API / Proxycurl** | Обогащение данных о компаниях/рекрутерах |

---

## Связи между инструментами (в контексте JobRadar)

```
Gmail / mail.de
    ↓ (n8n trigger)
n8n → Claude API → Postgres
                 → Google Sheets
                 → Google Calendar
                 → Telegram Bot

Firecrawl (web)
    ↓ (n8n HTTP)
n8n → Claude API → Postgres → Google Sheets

Manual (Telegram Bot / n8n Form)
    ↓
n8n → Claude API → Postgres
```
