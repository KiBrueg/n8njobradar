# JobRadar Automation Intelligence Hub — Project Context for Claude

## What this project IS

This project defines the **job-search intelligence layer** of a larger automation system:

- The **JSON contract** for all job-related data (one stable schema for all sources).
- The **system prompt(s)** for parsing and classifying job-related text via Claude.
- The **data model** (Postgres tables: companies, employers, jobs, job_events).
- The **logical workflow design** for how n8n should call the AI and store results.

## What this project is NOT

This project does NOT define:
- General n8n infrastructure or VPS setup.
- Credential configuration (Gmail OAuth, IMAP, Google APIs, Postgres connections).
- Generic n8n patterns for deploying or running workflows.
- Any automation layer that is not specific to job tracking.

This project is **self-contained** — it can be deployed to any n8n instance without depending on any other project. See `docs/deploy.md` for the full deployment guide and `.env.example` for all required environment variables.

## Deployment assumptions

- n8n instance is running on VPS, accessible and healthy.
- Credentials configured in n8n: Gmail OAuth, IMAP (mail.de), Google Calendar API, Postgres, OpenRouter API key.
- Generic pattern exists: `Trigger → Normalize → LLM call (HTTP) → DB write → Side effects`.
- Postgres database is reachable from n8n via the standard Postgres node.
- All env vars (`OPENROUTER_API_KEY`, `POSTGRES_*`, `GMAIL_ADDRESS`, `MAILDE_ADDRESS`, etc.) are managed in the n8n core project.

## Scope of work in THIS project

When Claude is working here, focus on:

1. **Schema** — Is the JSON contract complete? Are all fields clearly typed and documented?
2. **Prompts** — Do the system prompt and extraction rules produce correct, stable output?
3. **DB model** — Do the Postgres tables correctly represent the data the AI returns?
4. **Workflow logic** — Is the mapping from input source → normalize → AI → DB → side effects correct and complete? (Not HOW to deploy — WHAT the logic should be.)

## Key files

| File | Purpose |
|------|---------|
| `spec/prompt-context.md` | Briefing file for Claude: project summary + JSON contract + principles |
| `spec/prompt-system.txt` | Full system prompt for the Claude parser node |
| `spec/job-json-schema.json` | Formal JSON Schema (draft-07) for contract validation |
| `docs/job-radar-architecture.md` | Architecture overview and implementation plan |
| `db/schema.sql` | Postgres DDL: companies, employers, jobs, job_events |
| `n8n/flows.md` | Logical workflow designs for Gmail, mail.de, Firecrawl, Manual flows |

## Design Philosophy

This project is built to **portfolio + small-business grade**:

- **Portfolio:** Clean architecture, documented decisions, reproducible setup — something an employer can read and immediately understand the engineering level.
- **Scalable:** Multi-tenant-ready DB schema (tenant_id), stateless AI parser, connection pooling, idempotent upserts — can be adapted for a company or SaaS without a rewrite.
- **Secure by default:** No hardcoded secrets, parameterized queries only, input size limits, webhook signature validation, PII-aware logging, RLS stubs in Postgres.

When proposing any solution, apply these standards:
- Prefer **explicit over implicit** (all JSON fields always present, no silent defaults).
- Prefer **idempotent operations** (ON CONFLICT, upserts — safe to retry).
- **Never log PII** (email bodies, names, addresses) in plain text to external systems.
- **Parameterized queries only** — no string interpolation into SQL.
- Document the **why** behind non-obvious decisions.

See `docs/security.md` for the full security checklist.

## Security checkpoints — MANDATORY

Run these checks at two moments in every coding task:

### Mid-task checkpoint (after writing code, before moving on)
Before finishing any node, function, or file — scan what was just written:
- [ ] Hardcoded secrets? (API keys, passwords, tokens, IPs, emails) → move to `$env.*`
- [ ] String interpolation into SQL? → replace with parameterized query
- [ ] PII written to logs or external systems? → remove or mask
- [ ] User-controlled input passed unsanitized to LLM, SQL, or shell? → add check
- [ ] New file about to be saved — does it contain personal data (real name, email, address, phone, VPS IP)?

### Final checkpoint (before session ends or task is "done")
Run a quick grep before wrapping up:
```bash
grep -rn --include="*.json" --include="*.md" --include="*.yaml" --include="*.txt" --include="*.sh" \
  -E "(sk-[a-z0-9]{20,}|password\s*=|@gmail\.com|@mail\.de|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})" \
  . --exclude-dir=".claude" --exclude-dir="sessions" 2>/dev/null
```
- [ ] No real API keys in any tracked file
- [ ] No real VPS IP or hostname in tracked files
- [ ] No personal email, phone, or address in tracked files
- [ ] `.gitignore` covers all sensitive paths (`sessions/`, `.env*`, `spec/base-lebenslauf.yaml`, `NEXT_SESSION.md`)
- [ ] `README.md` and `docs/` contain only generic placeholders for infrastructure details

## Dev environment

- **IDE:** VS Code с расширениями: Remote SSH, Dev Containers, Claude in VS Code
- **VPS:** доступен через Remote SSH — редактировать файлы на сервере напрямую, без копипасты
- **Новые проекты:** предлагать `.devcontainer/devcontainer.json`
- **Написание/правка кода:** учитывать что среда может быть удалённой (Remote SSH) или контейнерной (Dev Container) — пути, терминалы и расширения работают в контексте сервера/контейнера, не локальной машины

## Operational constraints

Подтверждённые ограничения, обнаруженные в процессе разработки.

### LLM
- **LLM — OpenRouter / Qwen3, не Anthropic.** Модель: `qwen/qwen3-30b-a3b-instruct-2507`, ключ: `OPENROUTER_API_KEY`
- **Qwen3 выдаёт `<think>...</think>` блоки** перед JSON — Parse-нода обязана их стрипать:
  ```js
  raw.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  ```

### n8n API
- **При импорте флоу — только 4 поля:** `name`, `nodes`, `connections`, `settings`. Лишние поля дают 500.
- **Credentials нельзя задать через API** — подключать только в UI после импорта.

### VPS access
- **SSH порт 22 заблокирован с Windows** — вся работа с шеллом через Hetzner Console (браузер). `ssh`/`scp` с Windows не предлагать.
- **HTTP-вызовы к n8n API — только Windows PowerShell** (`Invoke-RestMethod`). curl из Linux sandbox возвращает 403.

### .env
- **Никогда не делать `echo KEY=value >> .env`** — создаёт дубли. Всегда использовать:
  ```bash
  grep -v KEY .env > .env.tmp && mv .env.tmp .env && echo 'KEY=value' >> .env
  ```

### PowerShell
- **`&&` не работает в PowerShell 5.1** — использовать `;` или отдельные вызовы.

## Git Safety Workflow

Применять в каждой сессии где есть изменения файлов.

- **Никогда не менять файлы без коммита** — незакоммиченные изменения = потеря при сбое
- **Никогда не коммитить напрямую в `main`** — только через ветки (`feat/`, `fix/`, `chore/`, `hotfix/`)
- **Всегда пушить в конце сессии** — локальный git не является бэкапом
- **Порядок нового проекта:** `.gitignore` → `git init` → `git status` → `git add .` → `commit` → `push`

### Флоу каждого коммита
```bash
git status          # что изменилось
git diff            # посмотреть изменения
git add .           # или конкретные файлы
git diff --staged   # финальная проверка перед коммитом
git commit -m "..."
```

### Формат сообщений коммитов
- `feat:` — новая функциональность
- `fix:` — исправление бага
- `refactor:` — рефакторинг без изменения поведения
- `chore:` — обслуживание, зависимости, конфиг
- `docs:` — документация
- `snapshot:` — сохранение промежуточного состояния

### Принцип атомарных коммитов
Одно изменение = один коммит. Не смешивать несвязанные правки в один коммит.

### Recovery
```bash
git restore <file>          # отменить изменения в файле
git log --oneline           # история коммитов
git checkout <hash> <file>  # восстановить файл из конкретного коммита
git revert <hash>           # отменить коммит (создаёт новый коммит)
```

### Переключение контекста
```bash
git stash       # сохранить незакоммиченные изменения
git stash pop   # восстановить
```

## .gitignore Rules

- `.gitignore` создаётся **ДО первого `git add .`** — иначе секреты попадут в историю
- Всегда запускать `git status` перед каждым коммитом и проверять список файлов
- Если `.env` случайно закоммичен **локально** (не запушен): `git rm --cached .env` → добавить в `.gitignore` → коммит
- Если `.env` уже **запушен**: считать ключи скомпрометированными → ротировать все секреты немедленно

Текущий `.gitignore` этого проекта закрывает: `sessions/`, `.env*`, `spec/base-lebenslauf.yaml`, `NEXT_SESSION.md`, `.claude/`, `outputs/`

## Sources handled by JobRadar

| Source | `input_source` | `email_account_id` | Protocol |
|--------|---------------|-------------------|---------|
| Gmail | `email` | `gmail_main` | Gmail API (n8n Gmail node) |
| mail.de | `email` | `mailde_main` | IMAP (n8n IMAP node) |
| Firecrawl | `scraped` | `null` | Firecrawl API → n8n HTTP |
| Manual | `manual` | `null` | n8n Webhook / Form |
